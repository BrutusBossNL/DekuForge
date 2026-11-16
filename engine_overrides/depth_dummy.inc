// Bindless tables contain several texture types. Unused entries in the shadow
// array must still be valid depth descriptors; colour views are not compatible.
static struct { VkImage image; VmaAllocation alloc; VkImageView view; } df_depth_dummy[DV_COUNT];

static VkImageView df_shadow_dummy(int i) {
    if (df_depth_dummy[i].view) return df_depth_dummy[i].view;
    VkCtx *c = vk_ctx();
    VkImageCreateInfo create = {.sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO,
        .flags = dinfo[i].f, .imageType = dinfo[i].t, .format = VK_FORMAT_D32_SFLOAT,
        .extent = {1, 1, 1}, .mipLevels = 1, .arrayLayers = dinfo[i].layers,
        .samples = dinfo[i].s, .tiling = VK_IMAGE_TILING_OPTIMAL,
        .usage = VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT};
    VmaAllocationCreateInfo allocation = {.usage = VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE};
    if (vmaCreateImage(c->vma, &create, &allocation, &df_depth_dummy[i].image,
                      &df_depth_dummy[i].alloc, NULL) != VK_SUCCESS)
        rt_fatal("Cannot create depth stand-in for view type %d", i);
    VkImageSubresourceRange range = {VK_IMAGE_ASPECT_DEPTH_BIT, 0, 1, 0, dinfo[i].layers};
    VkImageViewCreateInfo view = {.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO,
        .image = df_depth_dummy[i].image, .viewType = dinfo[i].vt,
        .format = VK_FORMAT_D32_SFLOAT, .subresourceRange = range};
    if (vkCreateImageView(c->device, &view, NULL, &df_depth_dummy[i].view) != VK_SUCCESS)
        rt_fatal("Cannot create depth stand-in view");
    VkImageMemoryBarrier2 barrier = {.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER_2,
        .dstStageMask = VK_PIPELINE_STAGE_2_TRANSFER_BIT, .dstAccessMask = VK_ACCESS_2_TRANSFER_WRITE_BIT,
        .oldLayout = VK_IMAGE_LAYOUT_UNDEFINED, .newLayout = VK_IMAGE_LAYOUT_GENERAL,
        .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED, .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .image = df_depth_dummy[i].image, .subresourceRange = range};
    VkDependencyInfo dependency = {.sType = VK_STRUCTURE_TYPE_DEPENDENCY_INFO,
        .imageMemoryBarrierCount = 1, .pImageMemoryBarriers = &barrier};
    VkCommandBuffer command = vk_upload_begin();
    vkCmdPipelineBarrier2(command, &dependency);
    VkClearDepthStencilValue clear = {1.0f, 0};
    vkCmdClearDepthStencilImage(command, df_depth_dummy[i].image, VK_IMAGE_LAYOUT_GENERAL, &clear, 1, &range);
    barrier.oldLayout = VK_IMAGE_LAYOUT_GENERAL;
    barrier.srcStageMask = VK_PIPELINE_STAGE_2_TRANSFER_BIT;
    barrier.srcAccessMask = VK_ACCESS_2_TRANSFER_WRITE_BIT;
    barrier.dstStageMask = VK_PIPELINE_STAGE_2_ALL_COMMANDS_BIT;
    barrier.dstAccessMask = VK_ACCESS_2_SHADER_SAMPLED_READ_BIT;
    vkCmdPipelineBarrier2(command, &dependency);
    vk_upload_end();
    return df_depth_dummy[i].view;
}

static void df_shadow_dummy_shutdown(void) {
    VkCtx *c = vk_ctx();
    for (int i = 0; i < DV_COUNT; i++) if (df_depth_dummy[i].image) {
        vkDestroyImageView(c->device, df_depth_dummy[i].view, NULL);
        vmaDestroyImage(c->vma, df_depth_dummy[i].image, df_depth_dummy[i].alloc);
    }
    memset(df_depth_dummy, 0, sizeof df_depth_dummy);
}
