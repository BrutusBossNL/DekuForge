// Original half-precision vector sign operation; input/output are raw lane bits.
#pragma once
#include <stdint.h>

static inline __uint128_t df_negate_half_vector(__uint128_t bits, int wide) {
    const uint64_t sign = UINT64_C(0x8000800080008000);
    __uint128_t result = bits ^ ((__uint128_t)sign | ((__uint128_t)sign << 64));
    return wide ? result : (__uint128_t)(uint64_t)result;
}
