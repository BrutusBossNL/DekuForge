// DekuForge: bounded constructor-state decoding for ordinary and PACIBSP prologues.
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>

static inline uint32_t df_word(const uint8_t *image, uint64_t offset) {
    uint32_t value;
    memcpy(&value, image + offset, sizeof value);
    return value;
}

static inline uint64_t df_ctor_flag_offset(const uint8_t *image, uint64_t size,
                                           uint64_t data_start, uint64_t text_end,
                                           uint64_t init) {
    if (text_end > size || data_start > size || init > text_end || text_end - init < 32)
        return 0;
    uint64_t position = init + (df_word(image, init) == 0xd503237fu ? 20 : 16);
    uint32_t page = df_word(image, position);
    if ((page & 0x9f000000u) != 0x90000000u) return 0;
    for (unsigned delta = 4; delta <= 8; delta += 4) {
        uint32_t load = df_word(image, position + delta);
        if ((load & 0xffc00000u) != 0xb9400000u || ((load >> 5) & 31) != (page & 31))
            continue;
        int64_t immediate = ((page >> 29) & 3) | (((page >> 5) & 0x7ffff) << 2);
        immediate = (immediate ^ (1 << 20)) - (1 << 20);
        int64_t target = (int64_t)(position & ~0xfffull) + immediate * 4096 + ((load >> 10) & 0xfff) * 4;
        if (target >= 0 && (uint64_t)target >= data_start && size >= 4 && (uint64_t)target <= size - 4)
            return (uint64_t)target;
    }
    return 0;
}
