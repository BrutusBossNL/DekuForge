// Snapshot the disjoint guest ranges addressable by physical-pointer shaders.
// Split at overlapping pool boundaries and virtual mapping transitions; resolve
// each interval through the same priority rules as ordinary buffer bindings.
static int df_address_compare(const void *a, const void *b) {
    uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;
    return (x > y) - (x < y);
}

static size_t df_global_snapshot(uint64_t (*out)[2], size_t capacity,
                                 uint64_t (*addresses)[4], uint64_t *generation) {
    enum { MAX_BOUNDARIES = 65536 };
    uint64_t *boundaries = malloc(MAX_BOUNDARIES * sizeof *boundaries);
    if (!boundaries) rt_fatal("Cannot allocate global memory map boundaries");
    size_t result = 0;
    {
        size_t count = 0;
        plat_mutex_lock_shared(&pool_lock);
        if (shadow_on) rt_fatal("Raw global memory requires native host memory import");
        for (int i = 0; i < pool_index.n; i++) {
            const pidx_ent *entry = &pool_index.e[i];
            PoolRec *pool = entry->buf;
            if (count + 2 > MAX_BOUNDARIES) rt_fatal("Global memory boundary limit exceeded");
            boundaries[count++] = entry->lo;
            boundaries[count++] = entry->hi;
            if (pool->kind != POOL_VIRT) continue;
            for (uint64_t page = 1; page < pool->npages; page++) {
                VPage before = pool->pt[page - 1], after = pool->pt[page];
                if (before.phys == after.phys && (!after.phys || before.off + NVN_VPOOL_PAGE == after.off)) continue;
                if (count == MAX_BOUNDARIES) rt_fatal("Global memory boundary limit exceeded");
                boundaries[count++] = pool->lo + page * NVN_VPOOL_PAGE;
            }
        }
        qsort(boundaries, count, sizeof *boundaries, df_address_compare);
        result = 0;
        VkBuffer previous = VK_NULL_HANDLE;
        uint64_t previous_end = 0;
        for (size_t i = 0; i + 1 < count; i++) {
            uint64_t lo = boundaries[i], hi = boundaries[i + 1];
            if (hi <= lo) continue;
            VkMemSpan span;
            if (!df_resolve_under_lock(lo, 1, &span)) { previous = VK_NULL_HANDLE; continue; }
            if (hi - lo > span.avail) hi = lo + span.avail;
            if (result && out[result - 1][1] == lo && previous == span.buffer && previous_end == span.offset) {
                out[result - 1][1] = hi;
                if (addresses) addresses[result - 1][1] = hi;
            } else {
                if (result == capacity) rt_fatal("Global memory table exceeds shader ABI capacity");
                if (addresses) {
                    VkBufferDeviceAddressInfo query = {.sType = VK_STRUCTURE_TYPE_BUFFER_DEVICE_ADDRESS_INFO,
                        .buffer = span.buffer};
                    VkDeviceAddress address = vkGetBufferDeviceAddress(vk_ctx()->device, &query);
                    if (!address) rt_fatal("Global memory pool has no device address");
                    addresses[result][0] = lo;
                    addresses[result][1] = hi;
                    addresses[result][2] = address + span.offset - lo;
                    addresses[result][3] = 0;
                    VK_MEM_BOUND(span);
                }
                out[result][0] = lo; out[result++][1] = hi;
            }
            previous = span.buffer;
            previous_end = span.offset + hi - lo;
        }
        if (generation) *generation = vk_mem_gen();
        plat_mutex_unlock_shared(&pool_lock);
    }
    free(boundaries);
    return result;
}

size_t df_global_ranges(uint64_t (*out)[2], size_t capacity) {
    return df_global_snapshot(out, capacity, NULL, NULL);
}

size_t df_global_address_map(uint64_t (*out)[4], size_t capacity, uint64_t *generation) {
    if (!capacity || capacity > 4095) rt_fatal("Invalid global address map capacity");
    uint64_t (*ranges)[2] = malloc(capacity * sizeof *ranges);
    if (!ranges) rt_fatal("Cannot allocate global address snapshot");
    size_t count = df_global_snapshot(ranges, capacity, out, generation);
    free(ranges);
    return count;
}
