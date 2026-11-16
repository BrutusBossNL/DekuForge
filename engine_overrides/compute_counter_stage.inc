// Opt-in experiment: run a small, unaliased compute counter in device memory.
// Indirect dispatches and raw writes retain their original bindings. An extra
// opt-in permits raw reads only with a private remapped address table.
static int df_counter_direct;
typedef struct {
    VkDescriptorBufferInfo original;
    VkBuffer buffer;
    VmaAllocation allocation;
} DfCounterStage;
static DfCounterStage *df_counter_active;
static void df_counter_free(void *argument) {
    DfCounterStage *stage = argument;
    vmaDestroyBuffer(vk_ctx()->vma, stage->buffer, stage->allocation);
    free(stage);
}
static void df_counter_prepare(VkExec *ex, const VkPipeInfo *info, VkDescSlot *descriptors) {
    const char *enabled = getenv("DEKUFORGE_STAGE_COMPUTE_COUNTERS");
    if (!df_counter_direct || !enabled || strcmp(enabled, "1")) return;
    uint64_t maximum = 64;
    const char *limit = getenv("DEKUFORGE_STAGE_COMPUTE_COUNTER_MAX");
    if (limit && *limit) {
        char *end;
        unsigned long parsed = strtoul(limit, &end, 10);
        if (*end || parsed < 4 || parsed > 8192 || parsed % 4) return;
        maximum = parsed;
    }
    const char *raw_setting=getenv("DEKUFORGE_STAGE_COMPUTE_RAW_READS");
    int raw_allowed=raw_setting && !strcmp(raw_setting,"1");
    unsigned raw_index=0,raw_count=0;
    unsigned index = 0, chosen = 0, candidates = 0;
    for (unsigned i = 0; i < info->n_bindings; i++) {
        const VkPipeBinding *binding = &info->bindings[i];
        unsigned count = binding->count ? binding->count : 1;
        if (binding->kind == GFX_RES_SSBO) {
            if ((uint8_t)binding->res->cbuf_slot >= 254) {
                if(!raw_allowed || (uint8_t)binding->res->cbuf_slot!=255 ||
                    binding->res->handle || (binding->res->flags&1) || count!=1) return;
                raw_index=index;
                if(++raw_count>1) return;
                index+=count;
                continue;
            }
            VkDescriptorBufferInfo b = descriptors[index].buffer;
            if (count == 1 && (binding->res->flags & 1) && b.buffer &&
                b.range && b.range <= maximum && !(b.range % 4) && !(b.offset % 4)) {
                candidates++;
                chosen = index;
            }
        }
        index += count;
    }
    if (candidates != 1) {
        static unsigned rejected_reports;
        if(raw_count && rejected_reports++<4) {
            unsigned at=0;
            for(unsigned i=0;i<info->n_bindings;i++) {
                const VkPipeBinding *binding=&info->bindings[i];
                if(binding->kind==GFX_RES_SSBO && (binding->res->flags&1))
                    rt_log("DekuForge: raw writable counter excluded, %llu bytes at c%d+%#x",
                        (unsigned long long)descriptors[at].buffer.range,
                        binding->res->cbuf_slot,binding->res->handle*4);
                at+=binding->count ? binding->count : 1;
            }
        }
        return;
    }
    VkDescriptorBufferInfo source = descriptors[chosen].buffer;
    static unsigned raw_reports;
    int report_raw=raw_count && raw_reports++<8;
    if(report_raw) rt_log("DekuForge: raw counter candidate %llu bytes",(unsigned long long)source.range);
    index = 0;
    for (unsigned i = 0; i < info->n_bindings; i++) {
        const VkPipeBinding *binding = &info->bindings[i];
        unsigned count = binding->count ? binding->count : 1;
        if (binding->kind == GFX_RES_SSBO || binding->kind == GFX_RES_UBO) {
            for (unsigned j = 0; j < count; j++) {
                VkDescriptorBufferInfo other = descriptors[index+j].buffer;
                if (index+j != chosen && source.buffer == other.buffer &&
                    (other.range == VK_WHOLE_SIZE ||
                     (other.offset < source.offset + source.range && source.offset < other.offset + other.range))) {
                    if(report_raw) rt_log("DekuForge: raw counter overlaps binding %u, size %llu",index+j,(unsigned long long)other.range);
                    return;
                }
            }
        }
        index += count;
    }
    DfCounterStage *stage = calloc(1, sizeof *stage);
    if (!stage) return;
    VkBufferCreateInfo create = {.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
        .size = source.range, .usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT |
            VK_BUFFER_USAGE_TRANSFER_SRC_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT};
    if(raw_count) create.usage|=VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT;
    VmaAllocationCreateInfo allocation = {.usage = VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE,
        .requiredFlags = VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT};
    if (vmaCreateBuffer(vk_ctx()->vma, &create, &allocation, &stage->buffer, &stage->allocation, NULL) != VK_SUCCESS) {
        free(stage);
        return;
    }
    stage->original = source;
    VkDescriptorBufferInfo remapped={0};
    if(raw_count && !df_counter_raw_map(ex,descriptors[raw_index].buffer,source,stage->buffer,&remapped)) {
        if(report_raw) rt_log("DekuForge: raw counter address map could not be remapped");
        df_counter_free(stage);
        return;
    }
    VkBufferCopy copy = {source.offset, 0, source.range};
    vkCmdCopyBuffer(ex->cb, source.buffer, stage->buffer, 1, &copy);
    ex->recorded++;
    vk_exec_barrier(ex);
    descriptors[chosen].buffer = (VkDescriptorBufferInfo){stage->buffer, 0, source.range};
    if(raw_count) descriptors[raw_index].buffer=remapped;
    if(report_raw) rt_log("DekuForge: raw counter address map remapped for this dispatch");
    df_counter_active = stage;
    static unsigned reported;
    if (reported++ < 4) rt_log("DekuForge: experimental compute counter staging (%llu bytes)",
        (unsigned long long)source.range);
}
static void df_counter_finish(VkExec *ex) {
    DfCounterStage *stage = df_counter_active;
    df_counter_active = NULL;
    if (!stage) return;
    vk_exec_barrier(ex);
    VkBufferCopy copy = {0, stage->original.offset, stage->original.range};
    vkCmdCopyBuffer(ex->cb, stage->buffer, stage->original.buffer, 1, &copy);
    ex->recorded++;
    vk_exec_barrier(ex);
    vk_completion_add(ex->fence, df_counter_free, stage);
}
