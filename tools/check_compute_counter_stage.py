"""Check counter selection, copy-back, alias rejection and allocation lifetime.

The command model is synthetic; native Vulkan validation is a separate check.
"""
import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    args = parser.parse_args()
    folder = ROOT / "build/validation-compute-counter"
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / "check.c"
    source.write_text(r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
typedef uint64_t VkBuffer, VmaAllocation;
typedef struct { VkBuffer buffer; uint64_t offset, range; } VkDescriptorBufferInfo;
typedef struct { VkDescriptorBufferInfo buffer; } VkDescSlot;
typedef struct { unsigned flags; uint8_t cbuf_slot; unsigned handle; } GfxShaderRes;
typedef struct { unsigned count,kind; const GfxShaderRes *res; } VkPipeBinding;
typedef struct { unsigned n_bindings; VkPipeBinding bindings[4]; } VkPipeInfo;
typedef struct { unsigned cb,recorded,fence; } VkExec;
typedef struct { unsigned sType; uint64_t size; unsigned usage; } VkBufferCreateInfo;
typedef struct { unsigned usage,requiredFlags; } VmaAllocationCreateInfo;
typedef struct { uint64_t srcOffset,dstOffset,size; } VkBufferCopy;
enum { GFX_RES_SSBO=1, GFX_RES_UBO=2, VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO=1,
    VK_BUFFER_USAGE_STORAGE_BUFFER_BIT=1, VK_BUFFER_USAGE_TRANSFER_SRC_BIT=2,
    VK_BUFFER_USAGE_TRANSFER_DST_BIT=4, VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT=8, VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE=1,
    VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT=1, VK_SUCCESS=0 };
#define VK_WHOLE_SIZE UINT64_MAX
#define rt_log(...) ((void)0)
static struct { unsigned vma; } context;
static typeof(context) *vk_ctx(void) { return &context; }
static unsigned char bytes[4][8192];
static unsigned allocated,freed,barriers,fail;
static void (*completion)(void *);
static void *completion_arg;
static int vmaCreateBuffer(unsigned a,const VkBufferCreateInfo *b,const VmaAllocationCreateInfo *c,
    VkBuffer *buffer,VmaAllocation *allocation,void *info) {
    if(fail)return -1;
    assert(!allocated && b->size<=8192);
    *buffer=3;*allocation=3;allocated=1;return 0;
}
static void vmaDestroyBuffer(unsigned a,VkBuffer b,VmaAllocation c) {
    assert(allocated && b==3 && c==3);allocated=0;freed++;
}
static void vkCmdCopyBuffer(unsigned cb,VkBuffer a,VkBuffer b,unsigned n,const VkBufferCopy *c) {
    assert(n==1 && a<4 && b<4 && c->srcOffset+c->size<=8192 && c->dstOffset+c->size<=8192);
    memcpy(bytes[b]+c->dstOffset,bytes[a]+c->srcOffset,c->size);
}
static void vk_exec_barrier(VkExec *ex) { barriers++; }
static void vk_completion_add(unsigned fence,void (*fn)(void *),void *arg) {
    assert(fence==7 && !completion);completion=fn;completion_arg=arg;
}
static unsigned map_ok;
static int df_counter_raw_map(VkExec *ex,VkDescriptorBufferInfo map,VkDescriptorBufferInfo source,
    VkBuffer staged,VkDescriptorBufferInfo *result) {
    if(!map_ok) return 0;
    assert(staged==3 && source.buffer==1 && map.buffer==2);
    *result=(VkDescriptorBufferInfo){2,512,128};return 1;
}
#include "compute_counter_stage.inc"
int main(void) {
    _putenv("DEKUFORGE_STAGE_COMPUTE_COUNTERS=1");
    _putenv("DEKUFORGE_STAGE_COMPUTE_COUNTER_MAX=64");
    _putenv("DEKUFORGE_STAGE_COMPUTE_RAW_READS=0");
    VkExec ex={.fence=7};
    GfxShaderRes writable={1,0},readonly={0,0},raw={0,255};
    VkPipeInfo pipe={.n_bindings=2,.bindings={{1,GFX_RES_SSBO,&writable},{1,GFX_RES_SSBO,&readonly}}};
    VkDescSlot slots[2]={{{1,32,16}},{{2,0,128}}};
    uint32_t initial=19,result=0;
    memcpy(bytes[1]+32,&initial,4);
    df_counter_direct=1;
    df_counter_prepare(&ex,&pipe,slots);
    assert(allocated && slots[0].buffer.buffer==3 && slots[0].buffer.offset==0);
    memcpy(&result,bytes[3],4);assert(result==19);result+=128;memcpy(bytes[3],&result,4);
    df_counter_finish(&ex);
    memcpy(&result,bytes[1]+32,4);assert(result==147 && barriers==3 && allocated && completion);
    completion(completion_arg);completion=NULL;assert(!allocated && freed==1);
    slots[0]=(VkDescSlot){{1,32,192}};
    df_counter_prepare(&ex,&pipe,slots);assert(!allocated); // default stays bounded
    _putenv("DEKUFORGE_STAGE_COMPUTE_COUNTER_MAX=4096");
    df_counter_prepare(&ex,&pipe,slots);assert(allocated);
    memset(bytes[3],0x5a,192);
    df_counter_finish(&ex);
    for(unsigned i=32;i<224;i++) assert(bytes[1][i]==0x5a);
    completion(completion_arg);completion=NULL;assert(!allocated && freed==2);
    slots[0]=(VkDescSlot){{1,32,192}};
    _putenv("DEKUFORGE_STAGE_COMPUTE_COUNTER_MAX=8193");
    df_counter_prepare(&ex,&pipe,slots);assert(!allocated);
    _putenv("DEKUFORGE_STAGE_COMPUTE_COUNTER_MAX=4096junk");
    df_counter_prepare(&ex,&pipe,slots);assert(!allocated);
    _putenv("DEKUFORGE_STAGE_COMPUTE_COUNTER_MAX=");
    slots[0].buffer=(VkDescriptorBufferInfo){1,32,16};
    slots[1].buffer=(VkDescriptorBufferInfo){1,24,32};
    df_counter_prepare(&ex,&pipe,slots);assert(!allocated); // overlapping read alias
    slots[1].buffer=(VkDescriptorBufferInfo){2,0,128};
    pipe.bindings[1].res=&raw;df_counter_prepare(&ex,&pipe,slots);assert(!allocated);
    _putenv("DEKUFORGE_STAGE_COMPUTE_RAW_READS=1");
    df_counter_prepare(&ex,&pipe,slots);assert(!allocated && slots[0].buffer.buffer==1);
    map_ok=1;
    df_counter_prepare(&ex,&pipe,slots);
    assert(allocated && slots[0].buffer.buffer==3 && slots[1].buffer.offset==512);
    df_counter_finish(&ex);completion(completion_arg);completion=NULL;
    slots[0].buffer=(VkDescriptorBufferInfo){1,32,16};
    raw.flags=1;
    df_counter_prepare(&ex,&pipe,slots);assert(!allocated); // raw writes stay rejected
    raw.flags=0;raw.handle=1;
    df_counter_prepare(&ex,&pipe,slots);assert(!allocated); // write-log binding
    raw.handle=0;
    _putenv("DEKUFORGE_STAGE_COMPUTE_RAW_READS=");
    pipe.bindings[1].res=&writable;slots[1].buffer.range=16;
    df_counter_prepare(&ex,&pipe,slots);assert(!allocated); // ambiguous small counters
    pipe.bindings[1].res=&readonly;fail=1;
    df_counter_prepare(&ex,&pipe,slots);assert(!allocated && slots[0].buffer.buffer==1);
    fail=0;df_counter_direct=0;
    df_counter_prepare(&ex,&pipe,slots);assert(!allocated); // indirect path
    df_counter_direct=1;_putenv("DEKUFORGE_STAGE_COMPUTE_COUNTERS=0");
    df_counter_prepare(&ex,&pipe,slots);assert(!allocated);
    _putenv("DEKUFORGE_STAGE_COMPUTE_COUNTERS=");
    _putenv("DEKUFORGE_STAGE_COMPUTE_COUNTER_MAX=");
    _putenv("DEKUFORGE_STAGE_COMPUTE_RAW_READS=");
    pipe.bindings[1].res=&raw;
    slots[0].buffer=(VkDescriptorBufferInfo){1,0,8192};
    slots[1].buffer=(VkDescriptorBufferInfo){2,0,128};
    df_counter_prepare(&ex,&pipe,slots);assert(allocated);
    df_counter_finish(&ex);completion(completion_arg);completion=NULL;
    return 0;
}
''', encoding="utf-8")
    executable = folder / "check.exe"
    subprocess.run([str(args.compiler), "-std=gnu11", "-I", str(ROOT / "engine_overrides"),
                    str(source), "-o", str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
    print("Counter copy-back, deferred release, alias/raw-global rejection and fallback checks passed")


if __name__ == "__main__":
    main()
