"""Exercise native interface reflection with synthetic SPIR-V declarations."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dekuforge.engine_workspace import stage_engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    args = parser.parse_args()
    text = (stage_engine() / "runtime/gfx_shader.c").read_text(encoding="utf-8")
    start = text.index("enum { OP_ENTRY_POINT")
    end = text.index("// Every gradient sample", start)
    output = ROOT / "build/validation-shader-interfaces"
    output.mkdir(parents=True, exist_ok=True)
    source = output / "check.c"
    source.write_text(r'''
#include <stdint.h>
#include <stdlib.h>
#include <assert.h>
enum { GFX_TYPE_FLOAT, GFX_TYPE_SINT, GFX_TYPE_UINT };
enum { GFX_STAGE_VS, GFX_STAGE_FS, GFX_STAGE_MS };
typedef struct { uint8_t type, comps, packed; } GfxShaderIo;
typedef struct { uint32_t *spirv; uint64_t words; uint32_t local[3], in_mask, out_mask;
    int stage; GfxShaderIo in[32], out[32]; } GfxShader;
''' + text[start:end] + r'''
int main(void) {
    // An input vec4[16] beginning at location zero consumes all 16 locations.
    uint32_t words[] = {0x07230203, 0x10000, 0, 16, 0,
        (4<<16)|71, 7, 30, 0,
        (3<<16)|22, 1, 32,
        (4<<16)|23, 2, 1, 4,
        (4<<16)|21, 3, 32, 0,
        (4<<16)|43, 3, 4, 16,
        (4<<16)|28, 5, 2, 4,
        (4<<16)|32, 6, 1, 5,
        (4<<16)|59, 6, 7, 1};
    GfxShader shader = {.spirv=words, .words=sizeof words/4, .stage=GFX_STAGE_FS};
    reflect_spirv(&shader);
    assert(shader.in_mask == 0xffff);
    for (int i=0;i<16;i++) assert(shader.in[i].comps == 4 && shader.in[i].type == GFX_TYPE_FLOAT);
    // The outer mesh per-vertex dimension does not consume extra locations.
    shader.in_mask=0; shader.stage=GFX_STAGE_MS;
    reflect_spirv(&shader);
    assert(shader.in_mask == 1);
    // Location ranges stay inside the runtime's 32-bit mask.
    words[8]=30; shader.in_mask=0; shader.stage=GFX_STAGE_FS;
    reflect_spirv(&shader);
    assert(shader.in_mask == 0xc0000000u);
    return 0;
}
''', encoding="utf-8")
    executable = output / "check.exe"
    subprocess.run([str(args.compiler), "-O2", str(source), "-o", str(executable)], check=True)
    subprocess.run([str(executable)], check=True, timeout=10)
    print("Native interface reflection: arrays, mesh dimensions and location bounds passed")


if __name__ == "__main__":
    main()
