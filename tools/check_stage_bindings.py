"""Exercise composed command recording for NVN2 task/mesh resource bindings."""
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
    workspace = stage_engine()
    commands = (workspace / "runtime/nvn_api_cmd.c").read_text(encoding="utf-8")
    functions = []
    for name in ("bind_buffers", "bind_buffer", "bind_handles"):
        start = commands.index("static void " + name + "(")
        end = commands.index("\n}\n", start) + 3
        functions.append(commands[start:end])
    output = ROOT / "build/validation-stage-bindings"
    output.mkdir(parents=True, exist_ok=True)
    source = output / "check.c"
    source.write_text(r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include "nvn2_stages.h"
typedef struct { uint64_t x[8]; } Cpu;
typedef struct { int unused; } cmd_t;
typedef struct { uint64_t address, size; } NVNbufferRange;
typedef struct { int stage, index; uint64_t addr, size; } p_bind_buf;
typedef struct { int stage, first, n; uint64_t src, h[]; } p_bind_handles;
static union { uint64_t alignment; uint8_t bytes[4096]; } records;
static size_t used;
static void *record(size_t size) {
    size_t offset = used; used += (size + 7) & ~(size_t)7;
    assert(used <= sizeof records); return records.bytes + offset;
}
#define REC(o, op, type) ((type *)record(sizeof(type)))
#define RECN(o, op, type, member, n) ((type *)record(sizeof(type) + sizeof(((type *)0)->member[0]) * (n)))
#define rt_log(...) ((void)0)
static uint64_t arg_x(const Cpu *c, int i) { return c->x[i]; }
static void *arg_p(const Cpu *c, int i) { return (void *)(uintptr_t)c->x[i]; }
static cmd_t *cmd_of(const Cpu *c) { return (cmd_t *)(uintptr_t)c->x[0]; }
static void hw_fix(cmd_t *c, size_t n) {}
''' + "\n".join(functions) + r'''
int main(void) {
    const int expected[8] = {0, 1, 2, 3, 4, 5, 3, 4};
    for (int stage = 0; stage < 8; stage++) {
        Cpu c = {.x = {0, stage, 2, 0x12340000, 512}};
        used = 0; bind_buffer(&c, 0);
        const p_bind_buf *b = (const p_bind_buf *)records.bytes;
        assert(b->stage == expected[stage] && b->index == 2 && b->addr == 0x12340000 && b->size == 512);
        NVNbufferRange ranges[] = {{0x1000, 128}, {0x2000, 256}};
        c.x[3] = 2; c.x[4] = (uintptr_t)ranges;
        used = 0; bind_buffers(&c, 0);
        b = (const p_bind_buf *)records.bytes;
        assert(b[0].stage == expected[stage] && b[1].stage == expected[stage]);
        assert(b[0].index == 2 && b[1].index == 3 && b[1].addr == 0x2000);
        uint64_t handles[] = {0x1234, 0x5678};
        for (int deferred = 0; deferred < 2; deferred++) {
            used = 0; bind_handles(NULL, 0, stage, 4, 2, handles, deferred, 0);
            const p_bind_handles *h = (const p_bind_handles *)records.bytes;
            assert(h->stage == expected[stage] && h->first == 4 && h->n == 2);
            assert(h->h[0] == 0x1234 && h->h[1] == 0x5678);
            assert(h->src == (deferred ? (uintptr_t)handles : 0));
        }
    }
    assert(df_nvn_stage_mask(0xc3) == 0x1b);
    assert(df_nvn_stage_mask(0x3f) == 0x3f);
    assert(df_nvn_stage(-1) == -1 && df_nvn_stage(8) == 8);
    return 0;
}
''', encoding="utf-8")
    executable = output / "check.exe"
    subprocess.run([str(args.compiler), "-O2", "-I", str(ROOT / "engine_overrides"),
                    str(source), "-o", str(executable)], check=True)
    subprocess.run([str(executable)], check=True, timeout=10)
    print("Stage bindings: single/plural buffers, immediate/deferred handles and program masks passed")


if __name__ == "__main__":
    main()
