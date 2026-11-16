// DekuForge static guest ABI: 39-bit virtual addresses, instruction TBI disabled.
// Address signing keys are disabled (SCTLR.EnIA/EnIB=0); the generic key is zero.
#pragma once
#include <stdint.h>

static inline uint64_t df_strip_instruction_pac(uint64_t pointer) {
    const uint64_t low = (UINT64_C(1) << 39) - 1;
    return (pointer & low) | ((pointer & (UINT64_C(1) << 55)) ? ~low : 0);
}
