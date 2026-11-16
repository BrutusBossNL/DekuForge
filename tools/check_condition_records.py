"""Exercise replay counter ordering with synthetic records and delayed callbacks."""
import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    args = parser.parse_args()
    folder = ROOT / "build/validation-condition-records"
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / "check.c"
    source.write_text(r'''
#include <assert.h>
#include <stdio.h>
#define DF_COUNTER_CAPACITY 8u
#include "condition_records.h"
int main(void) {
    DfCounterLedger ledger={.epoch=1};
    uint64_t value=99, serial; uint8_t output[16];
    assert(df_counter_read(&ledger,0x100,&value)==0);
    serial=df_counter_report(&ledger,0x100,0);
    assert(serial && df_counter_read(&ledger,0x100,&value)==1 && value==0);
    assert(df_counter_complete(&ledger,0x100,serial,0,123,output));
    // A CPU re-arm cannot change this frame's completed timestamp value.
    value=1; assert(df_counter_read(&ledger,0x100,&value)==1 && value==0);
    ledger.epoch++;
    assert(df_counter_read(&ledger,0x100,&value)==0);
    serial=df_counter_report(&ledger,0x100,1);
    assert(df_counter_read(&ledger,0x100,&value)==2);
    assert(df_counter_complete(&ledger,0x100,serial,17,124,output));
    assert(df_counter_read(&ledger,0x100,&value)==1 && value==17);
    uint64_t old=serial;
    serial=df_counter_report(&ledger,0x100,1);
    assert(!df_counter_complete(&ledger,0x100,old,999,0,output));
    assert(df_counter_read(&ledger,0x100,&value)==2);
    // A later GPU fill survives a deferred completion write, including timestamp bytes.
    df_counter_fill(&ledger,0x100,4,5);
    df_counter_fill(&ledger,0x10c,4,0xabcdef01);
    assert(df_counter_complete(&ledger,0x100,serial,UINT64_C(0x1234567800000011),123,output));
    assert(df_counter_read(&ledger,0x100,&value)==1 && value==UINT64_C(0x1234567800000005));
    uint32_t top; memcpy(&top,output+12,4);assert(top==0xabcdef01);
    df_counter_fill(&ledger,0x100,8,0);
    assert(df_counter_read(&ledger,0x100,&value)==1 && value==0);
    // More than the old 256-entry ring over time; completed old epochs are reusable.
    for (unsigned i=0;i<4096;i++) {
        ledger.epoch++; uint64_t addr=0x1000+(uint64_t)i*16;
        serial=df_counter_report(&ledger,addr,1);assert(serial);
        assert(df_counter_complete(&ledger,addr,serial,i,0,output));
        assert(df_counter_read(&ledger,addr,&value)==1 && value==i);
    }
    // Pending reports are never evicted to admit new records.
    memset(&ledger,0,sizeof ledger);ledger.epoch=1;
    for (unsigned i=0;i<8;i++) assert(df_counter_report(&ledger,0x100+i*16,1));
    ledger.epoch++;
    assert(!df_counter_report(&ledger,0x200,1));
    assert(df_counter_read(&ledger,0x100,&value)==2);
    puts("Replay counters: completion, CPU re-arm isolation, fill ordering, stale callbacks, capacity and reuse passed");
}
''', encoding="utf-8")
    executable = folder / "check.exe"
    subprocess.run([str(args.compiler.resolve()), "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                    "-I", str(ROOT / "engine_overrides"), str(source), "-o", str(executable)], check=True)
    subprocess.run([str(executable)], check=True)


if __name__ == "__main__":
    main()
