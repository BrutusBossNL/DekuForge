// Original AV1 movie adapter. The guest retains demuxing and its VideoFrame objects.
#include <dav1d/dav1d.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include "host.h"
#include "platform/platform.h"

#define DF_VIDEO_MAX 4
#define DF_VIDEO_QUEUE 6
typedef struct { Dav1dData packet; int eos; } DfVideoPacket;
typedef struct { Dav1dPicture picture; int eos; int64_t timestamp; } DfVideoPicture;
typedef struct {
    uint64_t guest, events[2], frames[16];
    unsigned char held[16];
    int frame_count, quit, failed, in_head, in_count, out_head, out_count;
    int64_t first_timestamp;
    uint64_t first_clock;
    PlatMutex lock;
    PlatCond changed;
    PlatThread *worker;
    Dav1dContext *decoder;
    DfVideoPacket input[DF_VIDEO_QUEUE];
    DfVideoPicture output[DF_VIDEO_QUEUE];
} DfVideo;
static DfVideo *df_video_objects[DF_VIDEO_MAX];
static PlatMutex df_video_registry = PLAT_MUTEX_INIT;

static DfVideo *df_video_find(uint64_t guest) {
    DfVideo *result = NULL;
    plat_mutex_lock(&df_video_registry);
    for (int i = 0; i < DF_VIDEO_MAX; i++)
        if (df_video_objects[i] && df_video_objects[i]->guest == guest) result = df_video_objects[i];
    plat_mutex_unlock(&df_video_registry);
    if (!result) rt_fatal("AV1: unknown decoder object");
    return result;
}

static void df_video_push(DfVideo *v, Dav1dPicture *picture, int eos, int64_t timestamp) {
    plat_mutex_lock(&v->lock);
    while (v->out_count == DF_VIDEO_QUEUE && !v->quit) plat_cond_wait(&v->changed, &v->lock);
    if (!v->quit) {
        DfVideoPicture *slot = &v->output[(v->out_head + v->out_count++) % DF_VIDEO_QUEUE];
        *slot = (DfVideoPicture){.eos=eos, .timestamp=timestamp};
        if (picture) { slot->picture = *picture; memset(picture, 0, sizeof *picture); }
        kern_signal_system_event(v->events[1]);
    }
    plat_mutex_unlock(&v->lock);
}

static void df_video_worker(void *argument) {
    DfVideo *v = argument;
    for (;;) {
        plat_mutex_lock(&v->lock);
        while (!v->in_count && !v->quit) plat_cond_wait(&v->changed, &v->lock);
        if (v->quit) { plat_mutex_unlock(&v->lock); return; }
        DfVideoPacket sample = v->input[v->in_head];
        memset(&v->input[v->in_head], 0, sizeof sample);
        v->in_head = (v->in_head + 1) % DF_VIDEO_QUEUE;
        v->in_count--;
        kern_signal_system_event(v->events[0]);
        plat_mutex_unlock(&v->lock);
        int error = 0;
        do {
            int sent = sample.packet.sz ? dav1d_send_data(v->decoder, &sample.packet) : 0;
            if (sent < 0 && sent != DAV1D_ERR(EAGAIN)) { error = sent; break; }
            int received = 0;
            for (;;) {
                Dav1dPicture picture = {0};
                int status = dav1d_get_picture(v->decoder, &picture);
                if (status == DAV1D_ERR(EAGAIN)) break;
                if (status < 0) { error = status; break; }
                received++;
                df_video_push(v, &picture, 0, picture.m.timestamp);
                dav1d_picture_unref(&picture);
            }
            if (error || (!received && sent == DAV1D_ERR(EAGAIN))) { error = error ? error : -1; break; }
        } while (sample.packet.sz);
        if (sample.eos && !error) df_video_push(v, NULL, 1, sample.packet.m.timestamp);
        dav1d_data_unref(&sample.packet);
        if (error) {
            plat_mutex_lock(&v->lock); v->failed = error; plat_mutex_unlock(&v->lock);
            kern_signal_system_event(v->events[1]);
            rt_log("AV1 decoder error %d", error);
        }
    }
}

static void df_video_ctor(Cpu *c) {
    uint64_t object = arg_x(c, 0);
    DfVideo *v = calloc(1, sizeof *v);
    if (!v) rt_fatal("AV1 allocation failed");
    v->guest = object;
    plat_mutex_init(&v->lock); plat_cond_init(&v->changed);
    for (int i = 0; i < 2; i++) {
        v->events[i] = (uintptr_t)mem_kernel_alloc(64, 16);
        kern_bind_system_event(c, v->events[i], 1);
    }
    plat_mutex_lock(&df_video_registry);
    int slot;
    for (slot = 0; slot < DF_VIDEO_MAX && df_video_objects[slot]; slot++);
    if (slot == DF_VIDEO_MAX) rt_fatal("Too many AV1 decoders");
    df_video_objects[slot] = v;
    plat_mutex_unlock(&df_video_registry);
    ST64(object, 0);
    ret_x(c, object);
}

static void df_video_initialize(Cpu *c) {
    DfVideo *v = df_video_find(arg_x(c, 0));
    if (v->decoder) { ret_x(c, 0); return; }
    Dav1dSettings settings;
    dav1d_default_settings(&settings);
    settings.n_threads = 4;
    settings.max_frame_delay = 1;
    settings.frame_size_limit = 4096 * 2160;
    int error = dav1d_open(&v->decoder, &settings);
    if (error) rt_fatal("AV1 decoder initialization failed: %d", error);
    v->worker = plat_thread_new(df_video_worker, v, "DekuForge AV1");
    if (!v->worker) rt_fatal("AV1 worker initialization failed");
    kern_signal_system_event(v->events[0]);
    rt_log("AV1: asynchronous software decoder initialized");
    ret_x(c, 0);
}

static void df_video_shutdown(DfVideo *v) {
    plat_mutex_lock(&v->lock); v->quit = 1; plat_cond_broadcast(&v->changed); plat_mutex_unlock(&v->lock);
    int away = kern_core_away();
    if (v->worker) plat_thread_join(v->worker);
    kern_core_back(&away);
    v->worker = NULL;
    for (int i = 0; i < DF_VIDEO_QUEUE; i++) {
        dav1d_data_unref(&v->input[i].packet);
        dav1d_picture_unref(&v->output[i].picture);
    }
    if (v->decoder) dav1d_close(&v->decoder);
    v->in_count = v->out_count = v->in_head = v->out_head = v->quit = v->failed = 0;
    v->first_clock = 0;
}
static void df_video_finalize(Cpu *c) { df_video_shutdown(df_video_find(arg_x(c, 0))); ret_x(c, 0); }
static void df_video_dtor(Cpu *c) {
    DfVideo *v = df_video_find(arg_x(c, 0));
    df_video_shutdown(v);
    uint64_t destroy = ldr_symbol("_ZN2nn2os18DestroySystemEventEPNS0_15SystemEventTypeE");
    if (!destroy) rt_fatal("Missing system event destructor");
    for (int i = 0; i < 2; i++) { rt_call(c, destroy, 1, v->events[i]); mem_kernel_free((void *)(uintptr_t)v->events[i], 64); }
    plat_mutex_lock(&df_video_registry);
    for (int i = 0; i < DF_VIDEO_MAX; i++) if (df_video_objects[i] == v) df_video_objects[i] = NULL;
    plat_mutex_unlock(&df_video_registry);
    free(v);
    ret_x(c, 0);
}
static void df_video_ok(Cpu *c) { (void)df_video_find(arg_x(c, 0)); ret_x(c, 0); }
static void df_video_flush(Cpu *c) {
    DfVideo *v = df_video_find(arg_x(c, 0));
    df_video_shutdown(v);
    memset(v->held, 0, sizeof v->held);
    df_video_initialize(c);
}
static void df_video_register(Cpu *c) {
    DfVideo *v = df_video_find(arg_x(c, 0));
    int count = (int)arg_x(c, 2);
    if (count < 1 || count > 16 || !arg_x(c, 1)) rt_fatal("Invalid AV1 frame pool");
    plat_mutex_lock(&v->lock);
    memcpy(v->frames, arg_p(c, 1), count * sizeof(uint64_t)); v->frame_count = count;
    memset(v->held, 0, sizeof v->held);
    plat_mutex_unlock(&v->lock); ret_x(c, 0);
}
static void df_video_event(Cpu *c, int index) {
    uint64_t output = arg_x(c, 1);
    DfVideo *v = df_video_find(arg_x(c, 0));
    if (!output) rt_fatal("Null AV1 event output");
    ST64(output, v->events[index]); ret_x(c, 0);
}
static void df_video_input_event(Cpu *c) { df_video_event(c, 0); }
static void df_video_output_event(Cpu *c) { df_video_event(c, 1); }
static void df_video_decode(Cpu *c) {
    DfVideo *v = df_video_find(arg_x(c, 0));
    uint64_t buffer = arg_x(c, 1);
    uint64_t size = LD64(buffer + 16), capacity = LD64(buffer + 8);
    if (size > capacity || size > 16 * 1024 * 1024) rt_fatal("Invalid AV1 input size");
    plat_mutex_lock(&v->lock);
    if (v->in_count == DF_VIDEO_QUEUE) { plat_mutex_unlock(&v->lock); ret_x(c, 0x7d); return; }
    DfVideoPacket *sample = &v->input[(v->in_head + v->in_count) % DF_VIDEO_QUEUE];
    if (size) {
        uint8_t *data = dav1d_data_create(&sample->packet, size);
        if (!data) rt_fatal("AV1 packet allocation failed");
        memcpy(data, (void *)(uintptr_t)LD64(buffer), size);
    }
    sample->packet.m.timestamp = (int64_t)LD64(buffer + 24);
    sample->eos = (LD32(buffer + 32) & 8) != 0;
    v->in_count++;
    plat_cond_signal(&v->changed);
    plat_mutex_unlock(&v->lock);
    ret_x(c, 0);
}

static void df_video_acquire(Cpu *c) {
    DfVideo *v = df_video_find(arg_x(c, 0));
    uint64_t output = arg_x(c, 1);
    if (!output) rt_fatal("Null AV1 frame output");
    ST64(output, 0);
    plat_mutex_lock(&v->lock);
    if (v->failed) rt_fatal("AV1 decode failed: %d", v->failed);
    int index;
    for (index = 0; index < v->frame_count && v->held[index]; index++);
    if (!v->out_count || index == v->frame_count) { plat_mutex_unlock(&v->lock); ret_x(c, 0x7b); return; }
    DfVideoPicture *ready = &v->output[v->out_head];
    uint64_t now = plat_now_ns();
    if (!v->first_clock) { v->first_clock = now; v->first_timestamp = ready->timestamp; }
    int64_t delta = ready->timestamp - v->first_timestamp;
    if (delta > 0 && (uint64_t)delta > now - v->first_clock) {
        kern_signal_system_event(v->events[1]);
        plat_mutex_unlock(&v->lock); ret_x(c, 0x7b); return;
    }
    uint64_t frame = v->frames[index];
    Dav1dPicture *picture = &ready->picture;
    if (!ready->eos) {
        int w = picture->p.w, h = picture->p.h;
        if (picture->p.bpc != 8 || picture->p.layout != DAV1D_PIXEL_LAYOUT_I420 || (w & 1) || (h & 1))
            rt_fatal("Unsupported AV1 movie pixel format");
        uint64_t size = (uint64_t)w * h;
        uint8_t *data = (void *)(uintptr_t)LD64(frame + 8);
        if (!data || LD64(frame + 72) < size + size / 2) rt_fatal("AV1 frame buffer too small");
        for (int y = 0; y < h; y++) memcpy(data + (size_t)y * w, (uint8_t *)picture->data[0] + y * picture->stride[0], w);
        for (int y = 0; y < h / 2; y++) {
            uint8_t *u = (uint8_t *)picture->data[1] + y * picture->stride[1];
            uint8_t *b = (uint8_t *)picture->data[2] + y * picture->stride[1];
            for (int x = 0; x < w / 2; x++) { data[size + (size_t)y * w + 2*x] = u[x]; data[size + (size_t)y * w + 2*x+1] = b[x]; }
        }
        ST64(frame + 16, (uintptr_t)(data + size));
        ST64(frame + 40, size); ST64(frame + 48, size / 2);
    }
    ST64(frame + 120, ready->timestamp);
    ST8(frame + 136, ready->eos);
    dav1d_picture_unref(picture); memset(ready, 0, sizeof *ready);
    v->out_head = (v->out_head + 1) % DF_VIDEO_QUEUE; v->out_count--; v->held[index] = 1;
    if (v->out_count) kern_signal_system_event(v->events[1]);
    plat_cond_signal(&v->changed); plat_mutex_unlock(&v->lock);
    ST64(output, frame); ret_x(c, 0);
}
static void df_video_release(Cpu *c) {
    DfVideo *v = df_video_find(arg_x(c, 0));
    plat_mutex_lock(&v->lock);
    for (int i = 0; i < v->frame_count; i++) if (v->frames[i] == arg_x(c, 1)) v->held[i] = 0;
    if (v->out_count) kern_signal_system_event(v->events[1]);
    plat_mutex_unlock(&v->lock); ret_x(c, 0);
}
#define DF_VID(name) "_ZN5movie12VideoDecoder" name
HOST_OVERRIDE(DF_VID("C1Ev"), df_video_ctor);
HOST_OVERRIDE(DF_VID("C2Ev"), df_video_ctor);
HOST_OVERRIDE(DF_VID("D1Ev"), df_video_dtor);
HOST_OVERRIDE(DF_VID("D2Ev"), df_video_dtor);
HOST_OVERRIDE(DF_VID("10InitializeEPvmN2nn5movie13MediaMimeTypeENS_24VideoDecoderOutputFormatENS_14VideoCodecModeE"), df_video_initialize);
HOST_OVERRIDE(DF_VID("9ConfigureEPKN2nn5movie13MediaPropertyEPKvm"), df_video_ok);
HOST_OVERRIDE(DF_VID("8FinalizeEv"), df_video_finalize);
HOST_OVERRIDE(DF_VID("5StartEv"), df_video_ok);
HOST_OVERRIDE(DF_VID("4StopEv"), df_video_ok);
HOST_OVERRIDE(DF_VID("5FlushEv"), df_video_flush);
HOST_OVERRIDE(DF_VID("18RegisterVideoFrameEPPNS_10VideoFrameEi"), df_video_register);
HOST_OVERRIDE(DF_VID("18GetInputReadyEventEPPN2nn2os15SystemEventTypeE"), df_video_input_event);
HOST_OVERRIDE(DF_VID("19GetOutputReadyEventEPPN2nn2os15SystemEventTypeE"), df_video_output_event);
HOST_OVERRIDE(DF_VID("11DecodeAsyncEPKN2nn5movie6BufferE"), df_video_decode);
HOST_OVERRIDE(DF_VID("17AcquireVideoFrameEPPNS_10VideoFrameE"), df_video_acquire);
HOST_OVERRIDE(DF_VID("17ReleaseVideoFrameEPNS_10VideoFrameE"), df_video_release);
