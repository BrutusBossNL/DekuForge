// DekuForge NVN2 control adaptation. Field layout follows the MIT-documented
// nxnative/MacNativeGames NVN2 v0xc9 ABI (see THIRD_PARTY_NOTICES.md).
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>

static inline uint32_t df_control_word(const void *p, unsigned offset) {
    uint32_t value; memcpy(&value, (const uint8_t *)p + offset, 4); return value;
}
static inline int df_control_ampere(const void *p) {
    return p && df_control_word(p, 0) == 0x98761234u && df_control_word(p, 4) == 0xc9;
}
static inline int df_nvn2_normalize(uint8_t output[0x880], const uint8_t *control,
                                   size_t control_size, const uint8_t *code, size_t code_size) {
    if (!control || control_size < 8 || !df_control_ampere(control)) return 0;
    if (control_size < 0xd8 || !code || code_size < 4) return -1;
    uint32_t inst = df_control_word(control, 0x38), c1 = df_control_word(control, 0x40);
    uint32_t total = df_control_word(control, 0x44), stage;
    if (!inst || inst > c1 || c1 > total || total > code_size || total > (16u << 20)) return -1;
    if (control[0x56] == 5) stage = 5;
    else {
        static const uint32_t stages[] = {0, 0, 3, 4, 2, 1};
        uint32_t word = df_control_word(code, 0), type = (word >> 10) & 15;
        if (!(word & 31) || type >= 6 || inst < 0x80) return -1;
        // Native task/mesh controls retain a vertex/domain-style SPH. Their
        // explicit stage byte takes precedence over that legacy header type.
        stage = control[0x56] == 6 ? 3 : control[0x56] == 7 ? 4 : stages[type];
    }
    memset(output, 0, 0x880);
    memcpy(output, control, 0xd8);
    memcpy(output + 0x700, &c1, 4);
    memcpy(output + 0x704, &total, 4);
    memcpy(output + 0x714, &stage, 4);
    if (stage == 5) {
        memcpy(output + 0x748, control + 0x58, 12);
        memcpy(output + 0x754, control + 0x64, 4);
    }
    return 1;
}
