"""Exercise the composed constant-buffer binding with synthetic allocations."""
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
    draw = (workspace / "runtime/vk_exec_draw.c").read_text(encoding="utf-8")
    start = draw.index("static VkDescriptorBufferInfo c0_info(")
    end = draw.index("\n}\n", start) + 3
    function = draw[start:end]
    output = ROOT / "build/validation-indirect-constants"
    output.mkdir(parents=True, exist_ok=True)
    source = output / "check.c"
    source.write_text(r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
enum { VK_C0_BYTES=2560, NVN_STAGE_VS=0, NVN_STAGE_FS=1, NVN_STAGE_CS=5 };
typedef uint64_t VkBuffer, VkDeviceSize;
typedef struct { VkBuffer buffer; VkDeviceSize offset, range; } VkDescriptorBufferInfo;
typedef struct { uint64_t addr, size; } p_bind_buf;
typedef struct { p_bind_buf ubo[6][16], ssbo[6][16]; } VkExec;
static struct {
    VkBuffer c0_buf[3]; VkDeviceSize c0_off[3]; int c0_valid[3];
    uint8_t c0[3][VK_C0_BYTES];
    struct { p_bind_buf ssbo[16], ubo[16]; uint32_t dim[3], binst; } c0_in[3];
} B;
static struct { int volatile_; } RS;
static uint32_t c0_dim[3], c0_binst;
static uint8_t allocations[8][VK_C0_BYTES];
static unsigned allocated;
static void *scratch(VkExec *ex, size_t size, VkBuffer *buffer, VkDeviceSize *offset) {
    assert(size == VK_C0_BYTES && allocated < 8);
    *buffer = 123; *offset = allocated * VK_C0_BYTES;
    return allocations[allocated++];
}
static int df_compute_bank(VkExec *ex, int stage, uint8_t *bank, size_t capacity) {
    assert(capacity == VK_C0_BYTES);
    if (stage != NVN_STAGE_CS && stage != 3) return 0;
    memset(bank, 0, capacity); memcpy(bank + 4, c0_dim, 12); return 1;
}
static void vk_c0_fill(uint8_t *bank, int stage, const p_bind_buf *s, const p_bind_buf *u,
                       const uint32_t *dim, uint32_t base) { memset(bank, 0, VK_C0_BYTES); }
''' + function + r'''
int main(void) {
    VkExec ex = {0};
    VkDescriptorBufferInfo previous = c0_info(&ex, NVN_STAGE_CS);
    B.c0_valid[2] = 0;
    VkDescriptorBufferInfo indirect = c0_info(&ex, NVN_STAGE_CS);
    assert(indirect.offset != previous.offset);
    assert(B.c0_valid[2] && B.c0_buf[2] == indirect.buffer && B.c0_off[2] == indirect.offset);
    uint32_t gpu_dimensions[3] = {7, 9, 11};
    // Model the subsequent GPU copy using the published destination.
    memcpy((uint8_t *)allocations + B.c0_off[2] + 4, gpu_dimensions, 12);
    assert(!memcmp((uint8_t *)allocations + indirect.offset + 4, gpu_dimensions, 12));
    uint32_t zero[3] = {0};
    assert(!memcmp((uint8_t *)allocations + previous.offset + 4, zero, 12));
    c0_info(&ex, 3);
    assert(B.c0_buf[2] == indirect.buffer && B.c0_off[2] == indirect.offset);
    assert(RS.volatile_);
    return 0;
}
''', encoding="utf-8")
    executable = output / "check.exe"
    subprocess.run([str(args.compiler), "-O2", str(source), "-o", str(executable)], check=True)
    subprocess.run([str(executable)], check=True, timeout=10)
    print("Indirect constants: bound allocation receives dimensions, earlier dispatch and task binding stay isolated")


if __name__ == "__main__":
    main()
