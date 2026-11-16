// Bounded, opt-in GPU timestamps for one frame. Normal runs allocate nothing.
#include <stdlib.h>
#include "nvn_api.h"
typedef struct {
    VkQueryPool query;
    VkPassMark mark;
    uint64_t frame;
} DfPassTiming;
static DfPassTiming *df_timing_pending[VK_PASS_MARKS];
static uint64_t df_timing_frame(void) {
    static int read;
    static uint64_t frame;
    if (!read) {
        const char *value = getenv("DEKUFORGE_PROFILE_FRAME");
        frame = value ? strtoull(value, NULL, 10) : 0;
        read = 1;
    }
    return frame;
}
static uint64_t df_timing_shader(const GfxShader *shader) {
    if (!shader) return 0;
    const uint8_t *id = gfx_shader_input_id(shader);
    uint64_t value = 0;
    for (unsigned i = 0; i < 8; i++) value = value << 8 | id[i];
    return value;
}
static void df_timing_read(void *argument) {
    DfPassTiming *sample = argument;
    uint64_t ticks[2];
    VkCtx *context = vk_ctx();
    VkResult result = vkGetQueryPoolResults(context->device, sample->query, 0, 2,
        sizeof ticks, ticks, sizeof ticks[0], VK_QUERY_RESULT_64_BIT);
    if (result == VK_SUCCESS && ticks[1] >= ticks[0]) {
        double ms = (ticks[1] - ticks[0]) * (double)context->props.limits.timestampPeriod / 1e6;
        const VkPassMark *m = &sample->mark;
        rt_log("DekuForge GPU pass: frame %llu id %u kind %u size %ux%ux%u draws %u ms %.4f shader %016llx %016llx",
            (unsigned long long)sample->frame, m->id, m->kind, m->w, m->h, m->d, m->draws, ms,
            (unsigned long long)df_timing_shader(m->first[0]), (unsigned long long)df_timing_shader(m->first[1]));
    } else rt_log("DekuForge GPU pass: unavailable result %d", (int)result);
    vkDestroyQueryPool(context->device, sample->query, NULL);
    free(sample);
}
static void df_timing_mark(VkCommandBuffer cb, uint32_t id, int end) {
    uint64_t frame = df_timing_frame();
    if (!frame) return;
    unsigned slot = id & (VK_PASS_MARKS - 1);
    if (end) {
        DfPassTiming *sample = df_timing_pending[slot];
        if (!sample || sample->mark.id != id) return;
        const VkPassMark *mark = vk_pass_mark_record(id);
        if (mark) sample->mark = *mark;
        vkCmdWriteTimestamp(cb, VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT, sample->query, 1);
        df_timing_pending[slot] = NULL;
        vk_completion_add(sample->mark.fence, df_timing_read, sample);
        return;
    }
    if (__atomic_load_n(&gfx_counters.frames, __ATOMIC_RELAXED) != frame) return;
    static unsigned count;
    if (count++ >= 1024 || df_timing_pending[slot]) return;
    const VkPassMark *mark = vk_pass_mark_record(id);
    if (!mark || !vk_ctx()->props.limits.timestampPeriod) return;
    DfPassTiming *sample = calloc(1, sizeof *sample);
    if (!sample) rt_fatal("Cannot allocate GPU pass timing");
    VkQueryPoolCreateInfo create = {.sType = VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO,
        .queryType = VK_QUERY_TYPE_TIMESTAMP, .queryCount = 2};
    if (vkCreateQueryPool(vk_ctx()->device, &create, NULL, &sample->query) != VK_SUCCESS) {
        free(sample);
        return;
    }
    sample->mark = *mark;
    sample->frame = frame;
    df_timing_pending[slot] = sample;
    vkCmdResetQueryPool(cb, sample->query, 0, 2);
    vkCmdWriteTimestamp(cb, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, sample->query, 0);
}
