// DekuForge portable Advanced SIMD byte dot products; integer arithmetic only.
#pragma once
#include <stdint.h>

static inline __uint128_t df_dot_bytes(__uint128_t accumulator, __uint128_t left,
                                      __uint128_t right, int wide, int is_unsigned) {
    __uint128_t result = 0;
    for (unsigned lane = 0; lane < (wide ? 4u : 2u); ++lane) {
        int32_t sum = 0;
        for (unsigned byte = 0; byte < 4; ++byte) {
            unsigned shift = lane * 32 + byte * 8;
            int32_t a = (uint8_t)(left >> shift), b = (uint8_t)(right >> shift);
            if (!is_unsigned) {
                if (a >= 128) a -= 256;
                if (b >= 128) b -= 256;
            }
            sum += a * b;
        }
        uint32_t value = (uint32_t)(accumulator >> (lane * 32)) + (uint32_t)sum;
        result |= (__uint128_t)value << (lane * 32);
    }
    return result;
}
