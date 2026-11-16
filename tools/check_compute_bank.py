"""Compile and exercise the NVN2 compute-bank adapter with synthetic metadata."""
import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    args = parser.parse_args()
    output = ROOT / "build" / "validation-compute-bank"
    output.mkdir(parents=True, exist_ok=True)
    source = output / "check.c"
    source.write_text(r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "nvn2_control.h"
typedef struct { int stage, index; uint64_t addr, size; } p_bind_buf;
typedef struct { int cbuf_slot, slot, handle; } GfxShaderRes;
enum { GFX_RES_TEX = 2, GFX_RES_IMG = 3 };
typedef struct { void *prog; uint8_t df_compute_constants[1024]; p_bind_buf ubo[6][18], ssbo[6][16]; } VkExec;
static uint8_t control[0x880];
static uint32_t c0_dim[3] = {7, 9, 11};
static int find_stage(void *p, int s, const uint8_t **c, const uint8_t **code, uint32_t *size) {
    *c = control; *code = NULL; *size = 0; return 1;
}
#define rt_fatal(...) abort()
#include "compute_bank.inc"
int main(void) {
    VkExec ex = {.prog = (void *)1};
    uint8_t bank[0xa00];
    uint32_t magic = 0x98761234, version = 0xc9, end = 64u << 16;
    memcpy(control, &magic, 4); memcpy(control + 4, &version, 4);
    control[0xb1] = control[0xb2] = 1;
    memcpy(control + 0xb8, &end, 4);
    memset(ex.df_compute_constants, 0x5a, 1024);
    ex.ubo[5][0] = (p_bind_buf){5, 0, 0x12340000, 512};
    ex.ssbo[5][0] = (p_bind_buf){5, 0, 0x56780000, 1024};
    assert(df_compute_bank(&ex, 5, bank, sizeof bank));
    assert(!memcmp(bank + 4, c0_dim, 12));
    assert(bank[0] == 0 && bank[1] == 0 && bank[2] == 0 && bank[3] == 0);
    for (int i = 16; i < 32; i++) assert(bank[i] == 0x5a);
    uint64_t address; uint32_t size;
    memcpy(&address, bank + 32, 8); assert(address == 0x12340000);
    memcpy(&size, bank + 40, 4); assert(size == 512);
    memcpy(&address, bank + 48, 8); assert(address == 0x56780000);
    memcpy(&size, bank + 56, 4); assert(size == 1024);
    assert(!df_compute_bank(&ex, 1, bank, sizeof bank));
    control[0xb1] = control[0xb2] = 0;
    assert(df_compute_bank(&ex, 5, bank, sizeof bank));
    assert(bank[1039] == 0x5a && bank[1040] == 0);
    control[0xb3] = 4; control[0xb6] = 2;
    end = 208u << 16; memcpy(control + 0xb8, &end, 4);
    GfxShaderRes tex = {0, -1, 46}, img = {0, -1, 50};
    assert(df_resource_slot(&ex, 5, GFX_RES_TEX, &tex) == 3);
    assert(df_resource_slot(&ex, 5, GFX_RES_IMG, &img) == 1);
    ex.ssbo[3][0] = (p_bind_buf){3, 0, 0xabcdef00, 128};
    ex.ssbo[4][15] = (p_bind_buf){4, 15, 0xfeed0000, 256};
    assert(df_compute_bank(&ex, 3, bank, sizeof bank));
    memcpy(&address, bank + 0x670, 8); assert(address == 0xabcdef00);
    memcpy(&size, bank + 0x678, 4); assert(size == 128);
    assert(df_compute_bank(&ex, 4, bank, sizeof bank));
    memcpy(&address, bank + 0x860, 8); assert(address == 0xfeed0000);
    memcpy(&size, bank + 0x868, 4); assert(size == 256);
    return 0;
}
''', encoding="utf-8")
    executable = output / "check.exe"
    subprocess.run([str(args.compiler), "-O2", "-I", str(ROOT / "engine_overrides"),
                    str(source), "-o", str(executable)], check=True)
    subprocess.run([str(executable)], check=True, timeout=10)
    print("Compute bank: dispatch, inline constants, UBO/SSBO boundaries and legacy-stage isolation passed")


if __name__ == "__main__":
    main()
