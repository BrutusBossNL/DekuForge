"""Check NVN2 byte addressing and both bulk-copy directions against a bit-lane oracle."""
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
    runtime = stage_engine() / "runtime"
    text = (runtime / "tex_deswizzle.c").read_text(encoding="utf-8")
    addressing = text[text.index("static uint32_t gob_off("):text.index("static uint32_t mip(")]
    copying = text[text.index("void tex_bl_copy("):text.index("static int move(")]
    folder = ROOT / "build/validation-nvn2-texture-layout"
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / "check.c"
    source.write_text(r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
''' + addressing + copying + r'''
// Independent coordinate-bit specification, low address bit first.
static unsigned lane(unsigned x,unsigned y) {
    unsigned bits[9]={x&1,(x>>1)&1,(x>>2)&1,(x>>3)&1,y&1,(y>>1)&1,(x>>4)&1,(y>>2)&1,(x>>5)&1};
    unsigned result=0;for(unsigned i=0;i<9;i++)result|=bits[i]<<i;return result;
}
static size_t oracle(unsigned x,unsigned y,unsigned z,unsigned width,unsigned rows,unsigned th,unsigned td) {
    size_t gx=(width+63)/64, bh=1u<<th, bd=1u<<td, by=(rows+8*bh-1)/(8*bh);
    size_t tile=((z/bd)*by+y/(8*bh))*gx+x/64;
    size_t gob=(z%bd)*bh+(y/8)%bh;
    return (tile*bh*bd+gob)*512+lane(x,y);
}
int main(void) {
    unsigned seen[512]={0};
    for(unsigned y=0;y<8;y++)for(unsigned x=0;x<64;x++) {
        assert(gob_off(x,y)==lane(x,y));assert(!seen[gob_off(x,y)]++);
    }
    unsigned widths[]={1,15,16,63,64,65,145}, heights[]={1,3,8,17};
    unsigned char *blocked=malloc(65536),*roundtrip=malloc(65536),*linear=malloc(65536);
    assert(blocked && roundtrip && linear);
    for(unsigned a=0;a<7;a++)for(unsigned b=0;b<4;b++)for(unsigned depth=1;depth<=3;depth+=2)
    for(unsigned th=0;th<4;th++)for(unsigned td=0;td<3;td++) {
        unsigned w=widths[a],h=heights[b],pitch=w+11;
        memset(blocked,0xa5,65536);memset(roundtrip,0xa5,65536);memset(linear,0x5a,65536);
        for(unsigned z=0;z<depth;z++)for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++) {
            size_t at=oracle(x,y,z,w,h,th,td);assert(at<65536);
            assert(nvn_bl_offset(x,y,z,w,h,th,td)==at);
            blocked[at]=(unsigned char)(x*13+y*37+z*19);
        }
        tex_bl_copy(blocked,linear,pitch,w,h,depth,th,td,1);
        for(unsigned z=0;z<depth;z++)for(unsigned y=0;y<h;y++)for(unsigned x=0;x<pitch;x++)
            assert(linear[(z*h+y)*pitch+x]==(x<w?(unsigned char)(x*13+y*37+z*19):0x5a));
        tex_bl_copy(roundtrip,linear,pitch,w,h,depth,th,td,0);
        assert(!memcmp(roundtrip,blocked,65536));
    }
    free(blocked);free(roundtrip);free(linear);return 0;
}
''', encoding="utf-8")
    executable = folder / "check.exe"
    subprocess.run([str(args.compiler), "-std=c11", "-O2", str(source), "-o", str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
    print("NVN2 GOB permutation and 672 geometry/padding round-trips passed")


if __name__ == "__main__":
    main()
