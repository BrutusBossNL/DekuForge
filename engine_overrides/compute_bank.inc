// NVN2 compute bank ABI: dispatch dimensions, inline constants, then resource
// tables described by control-section counts. No game-specific bytes are used.
static int df_compute_bank(VkExec *ex, int stage, uint8_t *bank, size_t capacity) {
    const uint8_t *control, *code;
    uint32_t code_size;
    if ((stage != 3 && stage != 4 && stage != 5) || !ex->prog || !find_stage(ex->prog, stage, &control, &code, &code_size)
        || !df_control_ampere(control)) return 0;
    if (stage == 3 || stage == 4) {
        // NVN2 task and mesh stages have their own fixed storage tables.
        size_t start = stage == 3 ? 0x670 : 0x770;
        if (start + 16 * 16 > capacity) rt_fatal("Mesh constant bank is too small");
        memset(bank, 0, capacity);
        for (unsigned i = 0; i < 16; i++) {
            const p_bind_buf *source = &ex->ssbo[stage][i];
            uint32_t bytes = (uint32_t)source->size;
            memcpy(bank + start + i * 16, &source->addr, 8);
            memcpy(bank + start + i * 16 + 8, &bytes, 4);
        }
        return 1;
    }
    unsigned uniforms = control[0xb1], storage = control[0xb2];
    unsigned other = control[0xb3] + control[0xb6];
    unsigned end = df_control_word(control, 0xb8) >> 16;
    unsigned tables = 16 * (uniforms + storage) + 8 * other;
    if (uniforms > 18 || storage > 16 || end < tables || end > capacity)
        rt_fatal("Invalid NVN2 compute resource table");
    unsigned start = uniforms + storage ? end - tables : 1040;
    if (start < 16 || start > capacity) rt_fatal("Invalid NVN2 constant span");
    memset(bank, 0, capacity);
    // NVN2 reserves word zero; workgroup counts occupy c0[4], c0[8], c0[12].
    memcpy(bank + 4, c0_dim, 12);
    size_t constants = start - 16;
    if (constants > 1024) constants = 1024;
    memcpy(bank + 16, ex->df_compute_constants, constants);
    for (unsigned i = 0; i < uniforms + storage; i++) {
        const p_bind_buf *source = i < uniforms ? &ex->ubo[5][i] : &ex->ssbo[5][i - uniforms];
        size_t at = start + i * 16;
        if (at + 12 > capacity) rt_fatal("NVN2 resource table overflow");
        memcpy(bank + at, &source->addr, 8);
        uint32_t bytes = (uint32_t)source->size;
        memcpy(bank + at + 8, &bytes, 4);
    }
    return 1;
}

int df_resource_slot(const VkExec *ex, int stage, int kind, const GfxShaderRes *resource) {
    if (stage != 5 || resource->cbuf_slot != 0 || (kind != GFX_RES_TEX && kind != GFX_RES_IMG))
        return resource->slot;
    const uint8_t *control, *code;
    uint32_t bytes;
    if (!ex->prog || !find_stage(ex->prog, stage, &control, &code, &bytes) || !df_control_ampere(control))
        return resource->slot;
    int textures = control[0xb3], images = control[0xb6];
    int end = (int)(df_control_word(control, 0xb8) >> 16);
    int first = end - 8 * (textures + images);
    int count = textures;
    if (kind == GFX_RES_IMG) { first += 8 * textures; count = images; }
    int offset = (resource->handle & 0x3fff) * 4 - first;
    return first >= 0 && offset >= 0 && offset % 8 == 0 && offset / 8 < count ? offset / 8 : -1;
}
