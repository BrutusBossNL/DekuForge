// Raw-global shader ABI: 4096 sorted 32-byte address-map records, entry zero
// empty, unused entries beginning at UINT64_MAX. The companion write log is a
// 65536-slot hash set plus its overflow word, copied to host memory at completion.
static VkDescriptorBufferInfo df_mesh_checks_info(VkExec *ex) {
    RS.volatile_ = 1;
    CbRes *resources = cb_res(ex);
    if (!resources->df_checks) {
        static uint32_t mesh_group_limit;
        if (!mesh_group_limit) {
            VkPhysicalDeviceMeshShaderPropertiesEXT mesh = {.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_MESH_SHADER_PROPERTIES_EXT};
            VkPhysicalDeviceProperties2 properties = {.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2, .pNext=&mesh};
            vkGetPhysicalDeviceProperties2(vk_ctx()->phys, &properties);
            mesh_group_limit = mesh.maxMeshWorkGroupCount[0] < mesh.maxMeshWorkGroupTotalCount
                ? mesh.maxMeshWorkGroupCount[0] : mesh.maxMeshWorkGroupTotalCount;
            if (!mesh_group_limit) rt_fatal("Mesh workgroup limit is unavailable");
        }
        resources->df_checks_info.range = 20 * sizeof(uint32_t);
        resources->df_checks = (uint32_t *)scratch(ex, resources->df_checks_info.range,
            &resources->df_checks_info.buffer, &resources->df_checks_info.offset);
        memset(resources->df_checks, 0, resources->df_checks_info.range);
        resources->df_checks[7] = mesh_group_limit;
        const char *sample = getenv("DEKUFORGE_TRACE_MESH_OUTPUT");
        resources->df_checks[17] = sample && !strcmp(sample, "1");
    }
    return resources->df_checks_info;
}

static VkDescriptorBufferInfo df_global_info(VkExec *ex, const GfxShaderRes *resource) {
    if (vk_mirror_on) rt_fatal("NVN2 raw global memory currently requires memory=import");
    if (!vk_ctx()->has_buffer_device_address) rt_fatal("Raw global memory needs buffer device addresses");
    if (resource->handle > 1) rt_fatal("Unknown raw global memory binding");
    RS.volatile_ = 1;
    CbRes *resources = cb_res(ex);
    if (resource->handle) {
        // Pointer writes may invalidate any earlier uniform snapshot. The GPU
        // log identifies exact dirty pages once the submission has completed.
        vk_usnap_drop(0, UINT64_MAX);
        if (!resources->df_log) {
            resources->df_log_info.range = 65537 * sizeof(uint32_t);
            VkBufferCreateInfo create = {.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
                .size = resources->df_log_info.range,
                .usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_SRC_BIT};
            VmaAllocationCreateInfo allocation = {.usage = VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE,
                .flags = VMA_ALLOCATION_CREATE_HOST_ACCESS_SEQUENTIAL_WRITE_BIT | VMA_ALLOCATION_CREATE_MAPPED_BIT,
                .requiredFlags = VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT | VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT |
                                 VK_MEMORY_PROPERTY_HOST_COHERENT_BIT};
            VmaAllocationInfo info;
            VkResult result = vmaCreateBuffer(vk_ctx()->vma, &create, &allocation,
                &resources->df_log_info.buffer, &resources->df_log_alloc, &info);
            if (result != VK_SUCCESS) rt_fatal("Cannot allocate device-local global write log (%d)", (int)result);
            memset(info.pMappedData, 0, resources->df_log_info.range);
            resources->df_log_readback.range = resources->df_log_info.range;
            resources->df_log = (uint32_t *)scratch(ex, resources->df_log_info.range,
                &resources->df_log_readback.buffer, &resources->df_log_readback.offset);
        }
        return resources->df_log_info;
    }
    uint64_t generation = vk_mem_gen();
    if (resources->df_map_info.buffer && resources->df_map_gen == generation) return resources->df_map_info;
    size_t bytes = 4096 * 32;
    // Every physical-pointer access searches this table. Prefer host-visible
    // device memory so those dependent reads do not cross PCIe repeatedly.
    if (resources->nchunks == resources->cchunks)
        resources->chunks = grow(resources->chunks, &resources->cchunks, sizeof *resources->chunks);
    Chunk *chunk = &resources->chunks[resources->nchunks];
    memset(chunk, 0, sizeof *chunk);
    VkBufferCreateInfo create = {.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
        .size = bytes, .usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT};
    VmaAllocationCreateInfo allocation = {.usage = VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE,
        .flags = VMA_ALLOCATION_CREATE_HOST_ACCESS_SEQUENTIAL_WRITE_BIT | VMA_ALLOCATION_CREATE_MAPPED_BIT,
        .requiredFlags = VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT};
    VmaAllocationInfo info;
    VkResult result = vmaCreateBuffer(vk_ctx()->vma, &create, &allocation,
        &chunk->buf, &chunk->alloc, &info);
    if (result != VK_SUCCESS) rt_fatal("Cannot allocate global address map (%d)", (int)result);
    chunk->map = info.pMappedData;
    chunk->size = chunk->used = bytes;
    resources->nchunks++;
    VkBuffer buffer = chunk->buf;
    uint64_t *map = (uint64_t *)chunk->map;
    memset(map, 0, bytes);
    for (size_t i = 1; i < 4096; i++) map[i * 4] = UINT64_MAX;
    // Resolve ranges and their addresses under one pool lock. Re-resolving
    // after a range-only snapshot races with asynchronous pool registration.
    df_global_address_map((uint64_t (*)[4])(map + 4), 4095, &generation);
    resources->df_map_gen = generation;
    resources->df_map_info = (VkDescriptorBufferInfo){buffer, 0, bytes};
    return resources->df_map_info;
}
