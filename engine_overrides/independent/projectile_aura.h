#pragma once

namespace mkwvk {
struct DfAuraDot { float x, y, radius; };
unsigned df_aura_dots(DfAuraDot *dots, unsigned capacity, float width, float height);
}

#ifdef DF_AURA_RENDERER
#include <atomic>
#include <cmath>
#include <mutex>
#ifdef _WIN32
#include <windows.h>
#endif

namespace mkwvk {
namespace {
using DfAuraSample = unsigned (*)(float (*)[3], unsigned);

DfAuraSample df_aura_source() {
#ifdef _WIN32
    static auto sample = reinterpret_cast<DfAuraSample>(
        GetProcAddress(GetModuleHandleW(nullptr), "df_projectile_aura_points"));
    return sample;
#else
    return nullptr;
#endif
}

struct DfAuraFrame {
    float transform[12]{};
    float aspect = 0;
    uint64_t frame = 0;
};

std::atomic<uint64_t> df_aura_attempt{0};
std::mutex df_aura_camera_mutex;
DfAuraFrame df_aura_camera;
}

void df_note_aura_camera(uint32_t width, uint32_t height, const nvn_p_bind_buf &camera) {
    if (!camera.addr || camera.size < 0x128) return;
    const uint64_t frame = texture_frame_no();
    if (df_aura_attempt.load(std::memory_order_relaxed) == frame) return;
    const auto read_points = df_aura_source();
    float point[1][3];
    if (!read_points || !read_points(point, 1)) {
        df_aura_attempt.store(frame, std::memory_order_relaxed);
        return;
    }
    // The scene's c3 has a perspective projection and declares its target size.
    float rows[0x128 / sizeof(float)];
    if (!memory_read_as_submitted(camera.addr, rows, sizeof rows) ||
        rows[0x120 / 4] != width || rows[0x124 / 4] != height ||
        rows[0xa0 / 4] || rows[0xa4 / 4] || rows[0xa8 / 4] != -1.0f || rows[0xac / 4]) return;
    const float aspect = std::abs(rows[0x84 / 4] / rows[0x70 / 4]);
    if (!std::isfinite(aspect) || aspect < 0.5f || aspect > 5.0f) return;
    std::lock_guard lock(df_aura_camera_mutex);
    // Retain clip x/y and w. The GPU's own projection includes aspect and jitter.
    std::memcpy(df_aura_camera.transform, rows + 0x30 / 4, 8 * sizeof(float));
    std::memcpy(df_aura_camera.transform + 8, rows + 0x60 / 4, 4 * sizeof(float));
    df_aura_camera.aspect = aspect;
    df_aura_camera.frame = frame;
    df_aura_attempt.store(frame, std::memory_order_relaxed);
}

unsigned df_aura_dots(DfAuraDot *dots, unsigned capacity, float width, float height) {
    const auto read_points = df_aura_source();
    float points[16][3];
    const unsigned count = read_points ? read_points(points, 16) : 0;
    if (!count) return 0;
    DfAuraFrame camera;
    {
        std::lock_guard lock(df_aura_camera_mutex);
        camera = df_aura_camera;
    }
    if (!camera.aspect || texture_frame_no() - camera.frame > 2) return 0;
    const float view_width = std::min(width, height * camera.aspect);
    const float view_height = std::min(height, width / camera.aspect);
    unsigned drawn = 0;
    for (unsigned i = 0; i < count && drawn < capacity; ++i) {
        float clip[3]{};
        for (unsigned j = 0; j < 3; ++j) {
            const float *row = camera.transform + j * 4;
            clip[j] = row[0] * points[i][0] + row[1] * points[i][1] + row[2] * points[i][2] + row[3];
        }
        if (!(clip[2] > 0.2f) || !std::isfinite(clip[2])) continue;
        const float x = clip[0] / clip[2], y = clip[1] / clip[2];
        if (!(std::abs(x) < 1.0f && std::abs(y) < 1.0f)) continue;
        dots[drawn++] = {width * .5f + x * view_width * .5f, height * .5f - y * view_height * .5f,
                         std::clamp(view_height * .06f / clip[2], 4.0f, 29.0f)};
    }
    if (drawn) {
        static std::atomic<bool> logged{false};
        if (!logged.exchange(true, std::memory_order_relaxed)) logf("DekuForge: projected explosive projectile aura");
    }
    return drawn;
}
}
#endif
