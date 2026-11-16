// Publish GPU-written log bytes to the host before signalling the submission.
void df_global_host_barrier(VkCommandBuffer cb) {
    if (cur && cur->df_checks) {
        VkMemoryBarrier2 barrier = {.sType=VK_STRUCTURE_TYPE_MEMORY_BARRIER_2,
            .srcStageMask=VK_PIPELINE_STAGE_2_ALL_COMMANDS_BIT, .srcAccessMask=VK_ACCESS_2_SHADER_WRITE_BIT,
            .dstStageMask=VK_PIPELINE_STAGE_2_HOST_BIT, .dstAccessMask=VK_ACCESS_2_HOST_READ_BIT};
        VkDependencyInfo dependency = {.sType=VK_STRUCTURE_TYPE_DEPENDENCY_INFO,
            .memoryBarrierCount=1, .pMemoryBarriers=&barrier};
        vkCmdPipelineBarrier2(cb, &dependency);
    }
    if (!cur || !cur->df_log) return;
    // All three commands must use vk_rec's wrappers. Mixing the legacy direct
    // barrier with an asynchronously recorded copy races on the command pool.
    VkMemoryBarrier2 barrier = {.sType = VK_STRUCTURE_TYPE_MEMORY_BARRIER_2,
        .srcStageMask = VK_PIPELINE_STAGE_2_ALL_COMMANDS_BIT,
        .dstStageMask = VK_PIPELINE_STAGE_2_TRANSFER_BIT,
        .srcAccessMask = VK_ACCESS_2_SHADER_WRITE_BIT, .dstAccessMask = VK_ACCESS_2_TRANSFER_READ_BIT};
    VkDependencyInfo dependency = {.sType = VK_STRUCTURE_TYPE_DEPENDENCY_INFO,
        .memoryBarrierCount = 1, .pMemoryBarriers = &barrier};
    vkCmdPipelineBarrier2(cb, &dependency);
    VkBufferCopy copy = {.srcOffset = 0, .dstOffset = cur->df_log_readback.offset, .size = cur->df_log_info.range};
    vkCmdCopyBuffer(cb, cur->df_log_info.buffer, cur->df_log_readback.buffer, 1, &copy);
    barrier.srcStageMask = VK_PIPELINE_STAGE_2_TRANSFER_BIT;
    barrier.dstStageMask = VK_PIPELINE_STAGE_2_HOST_BIT;
    barrier.srcAccessMask = VK_ACCESS_2_TRANSFER_WRITE_BIT;
    barrier.dstAccessMask = VK_ACCESS_2_HOST_READ_BIT;
    vkCmdPipelineBarrier2(cb, &dependency);
}

static void df_global_complete(CbRes *resources) {
    if (resources->df_checks) {
        const uint32_t *check = resources->df_checks;
        if (check[19]) {
            uint32_t count = check[18] < 512 ? check[18] : 512;
            rt_log("Mesh position batch: %u captured, %u requested", count, check[18]);
            for (uint32_t i = 0; i < count; i++) {
                const uint32_t *record = check + 20 + i * 8;
                rt_log("Mesh position bits: shader %08x group %u first %u primitives %u xyzw %08x %08x %08x %08x",
                    record[0], record[1], record[2], record[3], record[4], record[5], record[6], record[7]);
            }
        }
        if (check[0] == 2)
            rt_fatal("Mesh output bounds: kind %u, value %u, limit %u, group %u, lane %u, shader %08x stage %u",
                check[1], check[2], check[3], check[4], check[6], check[8], check[9]);
        static uint32_t largest_task;
        if (check[5] > largest_task) {
            largest_task = check[5];
            rt_log("Mesh task emission maximum: %u groups", largest_task);
        }
        if (check[17]) {
            static uint32_t maximum_primitives, samples;
            if (check[11] > maximum_primitives) {
                maximum_primitives = check[11];
                rt_log("Mesh output maximum: %u primitives", maximum_primitives);
            }
            if (check[10] == 2 && samples++ < 32) {
                float position[4];
                memcpy(position, check+12, sizeof position);
                rt_log("Mesh output sample: shader %08x, position (%g, %g, %g, %g), batch maximum %u primitives",
                    check[16], position[0], position[1], position[2], position[3], check[11]);
            }
        }
    }
    if (!resources->df_log) return;
    if (resources->df_log[0]) {
        static int reported;
        if (!reported) { rt_log("Raw global write log overflow: invalidating mapped ranges"); reported = 1; }
        // A full hash set must not hide a write. Fall back to the mapped ranges.
        uint64_t ranges[4095][2];
        size_t count = df_global_ranges(ranges, 4095);
        for (size_t i = 0; i < count; i++) vk_gpu_written(ranges[i][0], ranges[i][1] - ranges[i][0]);
        return;
    }
    for (unsigned i = 1; i <= 65536; i++) {
        uint32_t page = resources->df_log[i];
        if (page) vk_gpu_written((uint64_t)page << 12, 4096);
    }
}
