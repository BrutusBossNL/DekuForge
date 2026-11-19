#include <assert.h>
#include <stdint.h>
#include <stdalign.h>
#include <stdlib.h>
#include <string.h>
#include "engine_overrides/independent/sprint.h"

typedef struct { uint64_t x[32], vreg[32][2]; } Ctx;
static alignas(8) unsigned char guest[1024*1024];
static size_t next = 4096;
static const uint64_t hos_image_base = 0x8000, hos_image_end = 0x9000;
static const char hos_main_build_id[] = "e0f3ccfaf50065ae4ea01eb5aeb13b1a45da3348";
enum { OOT_GAMEDATA_SLOT = 128 };
static int hos_mem_region(uint64_t a, uint64_t n) { return a && n && a < sizeof guest && n <= sizeof guest - a; }
static uint64_t recomp_load64(Ctx *c, uint64_t a) { uint64_t v; (void)c; assert(hos_mem_region(a,8)); memcpy(&v,guest+a,8); return v; }
static uint32_t recomp_load32(Ctx *c, uint64_t a) { uint32_t v; (void)c; assert(hos_mem_region(a,4)); memcpy(&v,guest+a,4); return v; }
static uint8_t recomp_load8(Ctx *c, uint64_t a) { (void)c; assert(hos_mem_region(a,1)); return guest[a]; }
static void recomp_store8(Ctx *c, uint64_t a, uint8_t v) { (void)c; assert(hos_mem_region(a,1)); guest[a]=v; }
static void recomp_store32(Ctx *c, uint64_t a, uint32_t v) { (void)c; assert(hos_mem_region(a,4)); memcpy(guest+a,&v,4); }
static void wr64(uint64_t a,uint64_t v) { assert(hos_mem_region(a,8)); memcpy(guest+a,&v,8); }
static int64_t hos_now_ns(void) { return 1000000000LL; }
static void hos_log(const char *message, ...) { (void)message; }
int rx_option(int id, int otherwise) { (void)id; return otherwise; }
void rx_option_set(int id,int value) { (void)id; (void)value; }
#define DF_RESOURCE_HOST
#include "engine_overrides/independent/resources.h"

static uint64_t alloc(size_t bytes) { uint64_t a=next;next=(next+bytes+7)&~7u;assert(next<sizeof guest);return a; }
static void table(uint64_t mgr,int offs,uint32_t count,uint32_t stride) {
    recomp_store32(0,mgr+offs,count);
    wr64(mgr+offs+8,alloc(count*stride));
    wr64(mgr+offs+16,alloc(count*16));
    recomp_store32(0,mgr+offs+28,count*2);
}
static uint64_t entry(uint64_t mgr,int offs,uint32_t hash,uint32_t index,uint32_t stride,uint32_t v_off) {
    uint32_t size=recomp_load32(0,mgr+offs+28);
    uint64_t t=recomp_load64(0,mgr+offs+16);
    unsigned s=hash%size;
    while(recomp_load32(0,t+s*8))s=(s+1)%size;
    recomp_store32(0,t+s*8,hash);
    recomp_store32(0,t+s*8+4,index);
    uint64_t e=recomp_load64(0,mgr+offs+8)+index*stride;
    wr64(e,hos_image_base+24);
    return e+v_off;
}
static void value_f(uint64_t a,float f) { memcpy(guest+a,&f,4); }
static float read_f(uint64_t a) { float f;memcpy(&f,guest+a,4);return f; }

int main(void) {
    DfSprint s={0};
    assert(!df_sprint(&s,0,0,1));
    assert(df_sprint(&s,0,1,1));
    assert(!df_sprint(&s,0,0,1));
    assert(df_sprint(&s,1,1,1));
    assert(df_sprint(&s,1,0,1));
    assert(!df_sprint(&s,1,1,1));
    assert(!df_sprint(&s,1,0,1));
    assert(df_sprint(&s,1,1,1));
    assert(!df_sprint(&s,1,1,0));
    assert(!df_sprint(&s,1,1,1));
    assert(!df_sprint(&s,1,0,1));
    assert(df_sprint(&s,1,1,1));

    uint64_t mgr=alloc(1024);
    table(mgr,DF_DATA_BOOL,11292,24);
    table(mgr,DF_DATA_ENUM,130,56);
    table(mgr,DF_DATA_FLOAT,89,40);
    const uint32_t flags[]={0xf39ce410u,0x000ff6eau};
    const uint32_t values[]={0x7d48df76u,0x1edd164au};
    uint64_t writable[2];
    for(unsigned i=0;i<2;++i) {
        guest[entry(mgr,DF_DATA_BOOL,flags[i],10756+i,24,22)]=1;
        uint64_t e=entry(mgr,DF_DATA_ENUM,values[i],60+i,56,28), choices=alloc(13*4);
        recomp_store32(0,e,0xbe69de49u);
        recomp_store32(0,e+12,13);
        recomp_store32(0,choices,0xeaba6067u);
        recomp_store32(0,choices+4,0x049d37c1u);
        wr64(e+20,choices);
        writable[i]=e;
    }
    assert(df_bottle_update(0,mgr,0,2)==1);
    assert(recomp_load32(0,writable[0]+4)==0xeaba6067u);
    assert(df_bottle_update(0,mgr,1,0)==0);
    assert(df_bottle_update(0,mgr,1,3)==2);
    assert(df_bottle_update(0,mgr,0,0)==1);
    assert(df_bottle_update(0,mgr,2,2)==-1);
    assert(df_bottle_update(0,mgr,1,13)==2);

    uint64_t running=entry(mgr,DF_DATA_BOOL,0xf0312188u,10101,24,22);
    uint64_t down=entry(mgr,DF_DATA_BOOL,0xdd49184au,10100,24,22), t=entry(mgr,DF_DATA_FLOAT,0x9d350590u,67,40,28);
    guest[running]=1;guest[down]=1;
    value_f(t,200.0f);df_freeze_timer(0,mgr,1);
    value_f(t,188.0f);df_freeze_timer(0,mgr,1);
    assert(read_f(t)==200.0f && read_f(t+4)==200.0f);
    df_freeze_timer(0,mgr,0);
    value_f(t,180.0f);df_freeze_timer(0,mgr,1);
    assert(read_f(t)==180.0f);
    guest[running]=0;value_f(t,155.0f);df_freeze_timer(0,mgr,1);
    assert(read_f(t)==155.0f);
}
