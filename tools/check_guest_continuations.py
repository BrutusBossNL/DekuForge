"""Exercise native Windows guest nonlocal returns at optimized call sites."""
import argparse
import os
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
    runtime = stage_engine() / "runtime"
    output = ROOT / "build/validation-guest-continuations"
    output.mkdir(parents=True, exist_ok=True)
    source = output / "check.c"
    source.write_text(r'''
#include <assert.h>
#include <stdio.h>
#include <stdarg.h>
#include "df_guest_continuation.c"
static void caller(Cpu *cpu);
static unsigned completions;
static uint32_t jump_value;
int kern_host_track;
int rt_linked_modules(RtModule *out, int max) {
    static uint64_t addresses[] = {0x1000};
    static GuestFn functions[] = {caller};
    assert(max > 0);
    *out = (RtModule){.name="synthetic", .base=0x1000, .size=0x100,
                      .addrs=addresses, .fns=functions, .count=1};
    return 1;
}
void rt_fatal(const char *fmt, ...) {
    va_list ap; va_start(ap,fmt); vfprintf(stderr,fmt,ap); va_end(ap); exit(2);
}
void plat_mutex_lock(PlatMutex *m) { AcquireSRWLockExclusive((PSRWLOCK)m); }
void plat_mutex_unlock(PlatMutex *m) { ReleaseSRWLockExclusive((PSRWLOCK)m); }
static __attribute__((noinline)) void nested(Cpu *cpu, unsigned depth) {
    volatile uint64_t padding[32];
    padding[depth % 32] = depth;
    if (depth) nested(cpu,depth-1);
    else {
        for (int i=19;i<=30;++i) cpu->x[i] = 0xbad;
        cpu->sp=0xbad;
        cpu->v[8]=((__uint128_t)0x5678<<64)|0xbad;
        cpu->x[0]=0x9000;
        cpu->x[1]=jump_value;
        if (kern_host_track) ++*kern_host_depth(cpu->thread);
        df_guest_longjmp(cpu);
    }
    assert(padding[depth % 32] == depth);
    abort();
}
static __attribute__((noinline)) void caller(Cpu *cpu) {
    cpu->x[0]=0x9000;
    cpu->x[19]=0x1919;
    cpu->x[30]=0x1010;
    cpu->sp=0x8000;
    cpu->v[8]=((__uint128_t)0x1234<<64)|0x8888;
    // Match the runtime's tracking wrapper, which a nonlocal jump bypasses.
    if (kern_host_track) ++*kern_host_depth(cpu->thread);
    df_guest_setjmp(cpu);
    if (kern_host_track && !cpu->x[0]) --*kern_host_depth(cpu->thread);
    if (!cpu->x[0]) nested(cpu,8);
    assert(cpu->x[0] == (jump_value ? jump_value : 1));
    assert(cpu->x[19]==0x1919 && cpu->x[30]==0x1010 && cpu->sp==0x8000);
    assert((uint64_t)cpu->v[8]==0x8888);
    assert((uint64_t)(cpu->v[8]>>64)==0x5678);
    assert(*kern_host_depth(cpu->thread)==0);
    ++completions;
}
int main(void) {
    int thread[2]={0};
    Cpu cpu={.thread=thread};
    for (unsigned i=0;i<100;++i) { jump_value=i; kern_host_track=i%2; caller(&cpu); }
    assert(completions==100);
    puts("100 optimized nonlocal returns passed: nesting, repeat capture, zero result and ABI state.");
    return 0;
}
''', encoding="utf-8")
    environment = dict(os.environ)
    environment["PATH"] = str(args.compiler.resolve().parent) + os.pathsep + environment.get("PATH", "")
    executable = output / "check.exe"
    for command in ([str(args.compiler), "-O2", "-g", "-I", str(runtime), str(source), "-o", str(executable)], [str(executable)]):
        result = subprocess.run(command, env=environment, capture_output=True, timeout=60)
        print((result.stdout + result.stderr).decode(errors="replace"), end="")
        if result.returncode:
            raise RuntimeError(f"Continuation validation failed: {result.returncode}")


if __name__ == "__main__":
    main()
