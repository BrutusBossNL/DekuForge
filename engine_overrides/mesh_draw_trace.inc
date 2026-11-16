// Optional GPU-side copies of indirect records for device-loss diagnosis.
// Values after device loss are diagnostic only, never used to alter a draw.
static struct {
    VkBuffer buffer;
    VmaAllocation allocation;
    volatile uint32_t *words;
    uint64_t next, serial[256], address[256];
} df_mesh_trace;

static void df_mesh_trace_copy(VkExec *ex, const VkMemSpan *source, uint64_t address) {
    static int enabled = -1;
    if (enabled < 0) enabled = getenv("DEKUFORGE_TRACE_MESH_COUNTS") != NULL;
    if (!enabled) return;
    if (!df_mesh_trace.buffer) {
        VkBufferCreateInfo create = {.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
            .size=256*8, .usage=VK_BUFFER_USAGE_TRANSFER_DST_BIT};
        VmaAllocationCreateInfo allocation = {.usage=VMA_MEMORY_USAGE_AUTO_PREFER_HOST,
            .flags=VMA_ALLOCATION_CREATE_HOST_ACCESS_RANDOM_BIT|VMA_ALLOCATION_CREATE_MAPPED_BIT,
            .requiredFlags=VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT};
        VmaAllocationInfo info;
        if (vmaCreateBuffer(vk_ctx()->vma, &create, &allocation, &df_mesh_trace.buffer,
                            &df_mesh_trace.allocation, &info) != VK_SUCCESS)
            rt_fatal("Cannot allocate indirect mesh diagnostic buffer");
        df_mesh_trace.words = info.pMappedData;
        memset(info.pMappedData, 0xff, 256*8);
    }
    uint64_t serial = ++df_mesh_trace.next;
    unsigned slot = (unsigned)(serial % 256);
    df_mesh_trace.serial[slot] = serial;
    df_mesh_trace.address[slot] = address;
    VkBufferCopy copy = {source->offset, slot*8, 8};
    vkCmdCopyBuffer(ex->cb, source->buffer, df_mesh_trace.buffer, 1, &copy);
}

void df_mesh_trace_report(void) {
    if (!df_mesh_trace.words) return;
    uint64_t end = df_mesh_trace.next;
    for (uint64_t serial = end > 16 ? end-15 : 1; serial <= end; serial++) {
        unsigned slot = (unsigned)(serial % 256);
        rt_log("mesh indirect diagnostic %llu address %llx: count %u first %u (post-loss snapshot)",
            (unsigned long long)df_mesh_trace.serial[slot],
            (unsigned long long)df_mesh_trace.address[slot],
            df_mesh_trace.words[slot*2], df_mesh_trace.words[slot*2+1]);
    }
}

static void df_mesh_trace_shutdown(void) {
    if (df_mesh_trace.buffer)
        vmaDestroyBuffer(vk_ctx()->vma, df_mesh_trace.buffer, df_mesh_trace.allocation);
    memset(&df_mesh_trace, 0, sizeof df_mesh_trace);
}
