// Portable scene reconstruction for the NVN2 tensor-network presentation route.
// Identification uses instructions and bound formats, never guest addresses.
#include "df_scene_scale_spv.h"
#include "df_scene_easu_spv.h"
static int df_scene_network(const VkExec *ex) {
    static struct { uint64_t serial; int yes; } memo[64];
    if (!ex->prog) return 0;
    const char *native = getenv("DEKUFORGE_NATIVE_SCENE_NETWORK");
    if (native && !strcmp(native, "1")) return 0;
    unsigned index = ex->prog->serial % 64;
    if (ex->prog->serial && memo[index].serial == ex->prog->serial) return memo[index].yes;
    const uint8_t *control, *code;
    uint32_t size;
    int yes = 0;
    if (find_stage(ex->prog, 5, &control, &code, &size) && df_control_ampere(control)) {
        for (uint32_t offset = 0; offset + 16 <= size; offset += 16) {
            unsigned op = (code[offset] | (unsigned)code[offset+1] << 8) & 0xfff;
            if (op == 0x23c) { yes = 1; break; }
        }
    }
    memo[index].serial = ex->prog->serial;
    memo[index].yes = yes;
    return yes;
}

static int df_scene_scale(VkExec *ex, const p_dispatch *dispatch) {
    if (!ex->tex[5][0] || !ex->img[5][1] || !df_scene_network(ex)) return 0;
    view_t sv, dv;
    int sh = 0, dh = 0;
    uint32_t width = 0, height = 0;
    vk_texture_lock();
    const VkTexImage *source = vk_texture_by_id_locked(NVN_HANDLE_TEX(ex->tex[5][0]), &sv, &sh);
    const VkTexImage *destination = vk_texture_by_id_locked(NVN_HANDLE_TEX(ex->img[5][1]), &dv, &dh);
    TexVkFormat format;
    VkFormat sf = source ? source->format : VK_FORMAT_UNDEFINED;
    if (sh && sv.set_format && tex_vk_format(sv.format, &format)) sf = format.vk;
    if (source && destination && sf == VK_FORMAT_E5B9G9R9_UFLOAT_PACK32 &&
        destination->format == VK_FORMAT_B10G11R11_UFLOAT_PACK32 &&
        source->type == VK_IMAGE_TYPE_2D && destination->type == VK_IMAGE_TYPE_2D &&
        source->samples == 1 && destination->samples == 1 &&
        source->layers == 1 && destination->layers == 1 &&
        !(sh && (sv.set_levels || sv.set_layers)) && !(dh && (dv.set_levels || dv.set_layers || dv.set_format)) &&
        destination->width >= source->width && destination->height >= source->height &&
        (uint64_t)destination->width * source->height == (uint64_t)destination->height * source->width &&
        (destination->usage & VK_IMAGE_USAGE_STORAGE_BIT)) {
        width = destination->width;
        height = destination->height;
    }
    vk_texture_unlock();
    if (!width || !height) return 0;
    static const GfxShader *shader;
    static int edge_adaptive;
    if (!shader) {
        const char *mode = getenv("DEKUFORGE_SCENE_EASU");
        edge_adaptive = mode && !strcmp(mode, "1");
        const char *reflection = "{\"stage\":\"cs\",\"cbufs\":[],\"sbufs\":[],"
            "\"textures\":[{\"binding\":1,\"type\":3,\"cbuf_slot\":2,\"handle\":8,\"array\":1}],"
            "\"images\":[{\"binding\":2,\"type\":3,\"cbuf_slot\":2,\"handle\":74,\"array\":1,"
            "\"format\":\"R11G11B10Float\",\"flags\":4}]}";
        shader = edge_adaptive
            ? gfx_shader_own(df_scene_easu_spv, sizeof df_scene_easu_spv / 4, reflection)
            : gfx_shader_own(df_scene_scale_spv, sizeof df_scene_scale_spv / 4, reflection);
        if (!shader) rt_fatal("DekuForge scene resampler reflection is invalid");
    }
    const VkPipeInfo *info;
    VkPipeline pipeline = vk_pipeline_compute(shader, &info);
    if (!pipeline || !info) rt_fatal("DekuForge scene resampler pipeline failed");
    vk_exec_barrier(ex);
    bind_pipeline(ex, VK_PIPELINE_BIND_POINT_COMPUTE, pipeline);
    bind_resources(ex, info);
    p_dispatch replacement = {(width+7)/8, (height+7)/8, 1, dispatch->caller};
    VkPassMark *mark = dispatch_mark(ex, shader, replacement.x, replacement.y, 1);
    vkCmdDispatch(ex->cb, replacement.x, replacement.y, 1);
    vk_pass_mark_end(ex->cb, mark);
    ex->recorded++;
    if (vk_dump_armed) vk_dump_dispatch(ex, shader, pipeline, info, &replacement);
    static int reported;
    if (!reported++) rt_log("DekuForge: portable %s scene reconstruction active (%ux%u)",
        edge_adaptive ? "edge-adaptive" : "cubic", width, height);
    return 1;
}
