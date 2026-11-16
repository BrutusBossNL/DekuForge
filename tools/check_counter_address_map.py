"""Check staging address-map splitting and virtual aliases with synthetic ranges."""
import argparse
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    folder = root / "build/validation-counter-map"
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / "check.c"
    source.write_text(r'''
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <assert.h>
#include "counter_address_map.h"
static uint64_t resolve(uint64_t (*map)[4],uint64_t address) {
    for(unsigned i=1;i<16 && map[i][0]!=UINT64_MAX;i++)
        if(address>=map[i][0] && address<map[i][1]) return address+map[i][2];
    return UINT64_MAX;
}
int main(void) {
    uint64_t in[16][4]={{0}},out[16][4];
    for(unsigned i=1;i<16;i++) in[i][0]=UINT64_MAX;
    in[1][0]=100;in[1][1]=200;in[1][2]=900;
    in[2][0]=300;in[2][1]=400;in[2][2]=700; // virtual alias of first range
    in[3][0]=500;in[3][1]=600;in[3][2]=1500;
    assert(df_counter_address_map(out,in,16,1025,50,8000));
    for(uint64_t a=100;a<600;a++) {
        uint64_t before=resolve(in,a),expected=before;
        if(before>=1025 && before<1075) expected=8000+before-1025;
        assert(resolve(out,a)==expected);
    }
    assert(!df_counter_address_map(out,in,4,1025,50,8000)); // split exceeds capacity
    assert(!df_counter_address_map(out,in,16,UINT64_MAX-10,20,8000));
    assert(!df_counter_address_map(out,in,16,1025,50,UINT64_MAX-10));
    assert(df_counter_address_map(out,in,16,1000,100,8000)); // exact range
    assert(resolve(out,100)==8000 && resolve(out,399)==8099 && resolve(out,500)==2000);
    in[2][0]=150; // overlapping guest ranges are ambiguous
    assert(!df_counter_address_map(out,in,16,1025,50,8000));
    return 0;
}
''')
    executable = folder / "check.exe"
    subprocess.run([str(args.compiler), "-std=c11", "-I", str(root / "engine_overrides"),
                    str(source), "-o", str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
    print("Counter address-map splits, virtual aliases, exact boundaries and rejection cases pass.")


if __name__ == "__main__":
    main()
