// Match direct fragment inputs to the primitive-rate outputs of a mesh module.
static uint32_t df_mesh_primitive_mask(const uint32_t *code, uint64_t words) {
    if (words < 5 || code[3] > 1048576) return 0;
    uint32_t bound = code[3], mask = 0;
    uint8_t *locations = malloc(bound), *primitive = calloc(bound, 1);
    if (!locations || !primitive) rt_fatal("mesh interface: allocation failed");
    memset(locations, 255, bound);
    for (uint64_t i = 5; i < words;) {
        uint32_t count = code[i] >> 16, op = code[i] & 65535;
        if (!count || count > words - i) rt_fatal("mesh interface: malformed module");
        if (op == 71 && count >= 3 && code[i+1] < bound) {
            if (code[i+2] == 30 && count == 4 && code[i+3] < 32) locations[code[i+1]] = code[i+3];
            if (code[i+2] == 5271) primitive[code[i+1]] = 1;
        }
        i += count;
    }
    for (uint32_t i = 0; i < bound; ++i)
        if (primitive[i] && locations[i] < 32) mask |= 1u << locations[i];
    free(locations); free(primitive);
    return mask;
}

static uint32_t *df_fragment_primitive_inputs(const uint32_t *code, uint64_t words,
                                             uint32_t mask, uint64_t *out_words) {
    if (!mask || words < 5 || code[3] > 1048576) return NULL;
    uint32_t bound = code[3];
    uint8_t *locations = malloc(bound), *inputs = calloc(bound, 1), *decorated = calloc(bound, 1), *globals = calloc(bound, 1);
    if (!locations || !inputs || !decorated || !globals) rt_fatal("mesh interface: allocation failed");
    memset(locations, 255, bound);
    int capability = 0, extension = 0, entry_count = 0, in_function = 0;
    for (uint64_t i = 5; i < words;) {
        uint32_t count = code[i] >> 16, op = code[i] & 65535;
        if (!count || count > words - i) rt_fatal("mesh interface: malformed fragment module");
        if (op == 17 && count == 2 && code[i+1] == 5283) capability = 1;
        if (op == 15) ++entry_count;
        if (op == 54) in_function = 1;
        if (op == 59 && count >= 4 && code[i+2] < bound && !in_function) globals[code[i+2]] = 1;
        if (op == 10 && count >= 6 && !memcmp(code+i+1, "SPV_EXT_mesh_shader", 20)) extension = 1;
        if (op == 59 && count >= 4 && code[i+2] < bound && code[i+3] == 1) inputs[code[i+2]] = 1;
        if (op == 71 && count >= 3 && code[i+1] < bound) {
            if (code[i+2] == 30 && count == 4 && code[i+3] < 32) locations[code[i+1]] = code[i+3];
            if (code[i+2] == 5271) decorated[code[i+1]] = 1;
        }
        i += count;
    }
    uint32_t additions = 0;
    for (uint32_t i = 0; i < bound; ++i) {
        inputs[i] = inputs[i] && locations[i] < 32 && (mask & (1u << locations[i])) && !decorated[i];
        additions += inputs[i];
    }
    free(locations); free(decorated);
    if (!additions) { free(inputs); free(globals); return NULL; }
    if (entry_count != 1) rt_fatal("mesh interface: expected a single entry point");
    uint32_t *result = malloc((words + bound + additions*3 + 8) * sizeof(uint32_t));
    if (!result) rt_fatal("mesh interface: module allocation failed");
    memcpy(result, code, 5*sizeof(uint32_t));
    // Mesh interface decorations require 1.4, whose entry interface must also
    // list non-IO global variables used by the entry point (e.g. descriptors).
    if (result[1] < 0x10400) result[1] = 0x10400;
    uint64_t at = 5;
    if (!capability) { result[at++] = (2u<<16)|17; result[at++] = 5283; }
    int extension_done = extension, annotations_done = 0;
    for (uint64_t i = 5; i < words;) {
        uint32_t count = code[i] >> 16, op = code[i] & 65535;
        if (!extension_done && op != 17 && op != 10) {
            result[at++] = (6u<<16)|10;
            memcpy(result+at, "SPV_EXT_mesh_shader", 20); at += 5;
            extension_done = 1;
        }
        if (!annotations_done && op >= 19 && op <= 39) {
            for (uint32_t id = 0; id < bound; ++id) if (inputs[id]) {
                result[at++] = (3u<<16)|71; result[at++] = id; result[at++] = 5271;
            }
            annotations_done = 1;
        }
        if (op == 15 && code[1] < 0x10400) {
            uint32_t first = 3;
            while (first < count) {
                uint32_t word = code[i+first++];
                if (!(word & 255) || !(word & 0xff00) || !(word & 0xff0000) || !(word & 0xff000000)) break;
            }
            for (uint32_t j = first; j < count; ++j)
                if (code[i+j] < bound) globals[code[i+j]] = 0;
            uint64_t start = at;
            memcpy(result+at, code+i, count*sizeof(uint32_t)); at += count;
            for (uint32_t id = 0; id < bound; ++id) if (globals[id]) result[at++] = id;
            if (at-start > 65535) rt_fatal("mesh interface: entry point too large");
            result[start] = (uint32_t)(at-start)<<16 | 15;
        } else {
            memcpy(result+at, code+i, count*sizeof(uint32_t)); at += count;
        }
        i += count;
    }
    free(inputs); free(globals);
    if (!annotations_done) rt_fatal("mesh interface: fragment module has no types");
    *out_words = at;
    return result;
}
