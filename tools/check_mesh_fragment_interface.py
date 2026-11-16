"""Validate mesh/fragment primitive-rate adaptation with synthetic SPIR-V."""
import argparse
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--tools", type=Path, required=True)
    parser.add_argument("--point-fragment", type=Path, help="Optional local shader for point-input validation")
    args = parser.parse_args()
    folder = ROOT / "build/validation-mesh-fragment"
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / "check.c"
    source.write_text(r'''
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <assert.h>
#define rt_fatal(...) abort()
#include "mesh_fragment_interface.inc"
#include "mesh_point_interface.inc"
int main(int argc,char **argv) {
    assert(argc==4);
    FILE *f=fopen(argv[1],"rb"); assert(f);
    fseek(f,0,SEEK_END); long size=ftell(f); rewind(f);
    uint32_t *data=malloc(size); assert(fread(data,1,size,f)==(size_t)size); fclose(f);
    uint64_t words=0;
    if(!strncmp(argv[3],"0x",2)) {
        uint32_t *point=df_fragment_point_inputs(data,size/4,strtoul(argv[3],NULL,16),&words);assert(point);
        f=fopen(argv[2],"wb");assert(f);assert(fwrite(point,4,words,f)==words);fclose(f);
        free(data);free(point);return 0;
    }
    uint32_t *result=df_fragment_primitive_inputs(data,size/4,1,&words); assert(result);
    uint64_t again=0;
    assert(!df_fragment_primitive_inputs(result,words,1,&again));
    assert(df_mesh_primitive_mask(result,words)==1);
    uint64_t point_words=0;
    uint32_t *points=df_fragment_point_inputs(data,size/4,2,&point_words);assert(points);
    f=fopen(argv[3],"wb");assert(f);assert(fwrite(points,4,point_words,f)==point_words);fclose(f);free(points);
    points=df_fragment_point_inputs(result,words,2,&point_words);assert(points);
    free(result);result=points;words=point_words;
    f=fopen(argv[2],"wb"); assert(f); assert(fwrite(result,4,words,f)==words); fclose(f);
    free(data); free(result); return 0;
}
''', encoding="utf-8")
    fragment = folder / "input.frag"
    fragment.write_text('''#version 460
layout(location=0) in vec4 primitive_color;
layout(location=1) in vec4 vertex_color;
layout(location=0) out vec4 result_color;
layout(binding=0) uniform Settings { vec4 scale; } settings;
void main() { result_color=(primitive_color+vertex_color)*settings.scale; }
''', encoding="utf-8")
    environment = dict(os.environ)
    environment["PATH"] = os.pathsep.join([str(args.compiler.resolve().parent), str(args.tools.resolve()), environment.get("PATH", "")])
    exe, raw, fixed = folder / "check.exe", folder / "input.spv", folder / "output.spv"
    point_module = folder / "points.spv"
    commands = [
        [args.compiler, "-O2", "-I", ROOT / "engine_overrides", source, "-o", exe],
        [args.tools / "glslang.exe", "-V", "--target-env", "vulkan1.1", fragment, "-o", raw],
        [exe, raw, fixed, point_module],
        [args.tools / "spirv-val.exe", "--target-env", "vulkan1.2", fixed],
        [args.tools / "spirv-val.exe", "--target-env", "vulkan1.2", point_module],
    ]
    if args.point_fragment:
        local_output = folder / "local-point-fragment.spv"
        commands.extend([[exe, args.point_fragment, local_output, "0x20"],
                         [args.tools / "spirv-val.exe", "--target-env", "vulkan1.2", local_output]])
    for command in commands:
        result = subprocess.run(list(map(str, command)), env=environment, capture_output=True, timeout=60)
        if result.returncode:
            raise RuntimeError((result.stdout+result.stderr).decode(errors="replace"))
    print("Primitive-rate adaptation and point-sprite inputs validate in SPIR-V 1.3/1.4; repeated primitive adaptation is unchanged.")


if __name__ == "__main__":
    main()
