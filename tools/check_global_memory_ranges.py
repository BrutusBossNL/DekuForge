"""Check native raw-memory interval mapping against overlapping synthetic pools."""
import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    args = parser.parse_args()
    output = ROOT / "build/validation-global-memory"
    output.mkdir(parents=True, exist_ok=True)
    source = output / "check.c"
    source.write_text(r'''
#include <stdint.h>
#include <stdlib.h>
#include <assert.h>
#include <stddef.h>
typedef uint64_t VkBuffer;
typedef uint64_t VkDeviceAddress;
typedef struct { int sType; VkBuffer buffer; } VkBufferDeviceAddressInfo;
#define VK_STRUCTURE_TYPE_BUFFER_DEVICE_ADDRESS_INFO 1
#define VK_MEM_BOUND(span) assert(pool_lock==1)
#define VK_NULL_HANDLE 0
#define NVN_VPOOL_PAGE 64
#define POOL_VIRT 2
#define rt_fatal(...) abort()
typedef struct PoolRec PoolRec;
typedef struct { PoolRec *phys; uint64_t off; } VPage;
struct PoolRec { int kind; uint64_t lo, npages; VPage *pt; VkBuffer buffer; };
typedef struct { uint64_t lo,hi; PoolRec *buf; } pidx_ent;
static struct { int n; pidx_ent e[3]; } pool_index;
static int pool_lock, shadow_on;
static uint64_t pool_gen=1;
static uint64_t vk_mem_gen(void) { assert(pool_lock==1); return pool_gen; }
static struct { int device; } device;
static typeof(device) *vk_ctx(void) { return &device; }
static VkDeviceAddress vkGetBufferDeviceAddress(int device, const VkBufferDeviceAddressInfo *query) {
    assert(pool_lock==1); return query->buffer * 0x100000;
}
static void plat_mutex_lock_shared(int *p) { assert(!*p); *p=1; }
static void plat_mutex_unlock_shared(int *p) { assert(*p==1); *p=0; }
typedef struct { VkBuffer buffer; uint64_t offset,avail; } VkMemSpan;
static int df_resolve_under_lock(uint64_t at, uint64_t size, VkMemSpan *span) {
    assert(pool_lock==1);
    pidx_ent *selected=NULL;
    for(int i=0;i<pool_index.n;i++) {
        pidx_ent *e=&pool_index.e[i];
        if(at>=e->lo && at<e->hi && (!selected || e->lo>selected->lo)) selected=e;
    }
    if(!selected)return 0;
    PoolRec *p=selected->buf;
    if(p->kind==POOL_VIRT) {
        unsigned page=(unsigned)((at-p->lo)/NVN_VPOOL_PAGE);
        if(!p->pt[page].phys)return 0;
        span->buffer=p->pt[page].phys->buffer;
        span->offset=p->pt[page].off+(at-p->lo)%NVN_VPOOL_PAGE;
        span->avail=NVN_VPOOL_PAGE-(at-p->lo)%NVN_VPOOL_PAGE;
    } else {
        span->buffer=p->buffer;span->offset=at-p->lo;span->avail=selected->hi-at;
    }
    return 1;
}
#include "global_memory_ranges.inc"
int main(void) {
    PoolRec first={.lo=100,.buffer=1}, second={.lo=200,.buffer=2};
    VPage pages[2]={{&second,0},{&second,128}};
    PoolRec virt={.kind=POOL_VIRT,.lo=1000,.npages=2,.pt=pages};
    pool_index.n=3;
    pool_index.e[0]=(pidx_ent){100,500,&first};
    pool_index.e[1]=(pidx_ent){200,300,&second};
    pool_index.e[2]=(pidx_ent){1000,1128,&virt};
    uint64_t ranges[8][2];
    assert(df_global_ranges(ranges,8)==5);
    assert(pool_lock==0);
    assert(ranges[0][0]==100 && ranges[0][1]==200);
    assert(ranges[1][0]==200 && ranges[1][1]==300);
    assert(ranges[2][0]==300 && ranges[2][1]==500);
    assert(ranges[3][0]==1000 && ranges[3][1]==1064);
    assert(ranges[4][0]==1064 && ranges[4][1]==1128);
    uint64_t map[8][4], generation;
    assert(df_global_address_map(map,8,&generation)==5);
    assert(pool_lock==0 && generation==1);
    assert(map[0][0]==100 && map[0][1]==200 && map[0][2]+100==0x100000);
    assert(map[2][0]==300 && map[2][1]==500 && map[2][2]+300==0x100000+200);
    assert(map[4][0]==1064 && map[4][1]==1128 && map[4][2]+1064==0x200000+128);
    // A later registration change cannot change an already captured snapshot.
    second.buffer=3; pool_gen++;
    assert(map[4][2]+1064==0x200000+128);
    assert(df_global_address_map(map,8,&generation)==5);
    assert(generation==2 && map[4][2]+1064==0x300000+128);
    pages[1].phys=NULL;pool_gen++;
    assert(df_global_ranges(ranges,8)==4);
    assert(ranges[3][1]==1064);
    return 0;
}
''', encoding="utf-8")
    executable = output / "check.exe"
    subprocess.run([str(args.compiler), "-O2", "-I", str(ROOT / "engine_overrides"),
                    str(source), "-o", str(executable)], check=True)
    subprocess.run([str(executable)], check=True, timeout=10)
    print("Native global memory: overlaps, disjoint virtual backing, holes and atomic address snapshots passed")


if __name__ == "__main__":
    main()
