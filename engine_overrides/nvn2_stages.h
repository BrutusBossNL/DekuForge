// NVN2's public task/mesh stage numbers map to the runtime's unused tessellation
// slots, consistently with normalized program controls and Vulkan bindings.
#pragma once
static inline int df_nvn_stage(int stage) {
    return stage == 6 ? 3 : stage == 7 ? 4 : stage;
}
static inline int df_nvn_stage_mask(int mask) {
    return (mask & ~0xc0) | ((mask & 0x40) ? 0x08 : 0) | ((mask & 0x80) ? 0x10 : 0);
}
