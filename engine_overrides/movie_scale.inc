// Portable presentation of a decoded movie frame. Tensor scratch passes are
// omitted in portable mode; typed final output uses the decoded source frame.
#include "df_movie_scale_spv.h"
static int df_movie_scale(VkExec *ex, const p_dispatch *dispatch) {
    const char *enabled=getenv("DEKUFORGE_PORTABLE_MOVIES");
    if((enabled && !strcmp(enabled,"0")) || !df_scene_network(ex)) return 0;
    const uint8_t *control,*code;
    uint32_t length;
    if(!find_stage(ex->prog,5,&control,&code,&length) || !df_control_ampere(control)) return 0;
    unsigned image_count=control[0xb6];
    // The portable final scene/movie image does not consume tensor scratch.
    // Retain an opt-out for investigating other tensor workloads.
    const char *skip=getenv("DEKUFORGE_SKIP_TENSOR_SCRATCH");
    if(!image_count && (!skip || strcmp(skip,"0"))) {
        static unsigned reported;
        if(reported++<4) rt_log("DekuForge: portable reconstruction skips tensor scratch dispatch");
        return 1;
    }
    if(!image_count || image_count>32 || !ex->tex[5][0]) return 0;
    int source_slot=-1,destination_slot=-1;
    uint32_t width=0,height=0;
    vk_texture_lock();
    view_t view; int has_view=0;
    const VkTexImage *intermediate=vk_texture_by_id_locked(NVN_HANDLE_TEX(ex->tex[5][0]),&view,&has_view);
    // The movie's final network samples a 10-bit intermediate, while its
    // original decoded RGBA8 frame is still bound. Reject scene HDR formats.
    if(!intermediate || intermediate->format!=VK_FORMAT_A2B10G10R10_UNORM_PACK32 ||
        intermediate->type!=VK_IMAGE_TYPE_2D || intermediate->samples!=1 || intermediate->layers!=1)
        goto unlock;
    const VkTexImage *source=NULL,*destination=NULL;
    for(unsigned i=0;i<128;i++) {
        if(!ex->tex[5][i]) continue;
        has_view=0;
        const VkTexImage *t=vk_texture_by_id_locked(NVN_HANDLE_TEX(ex->tex[5][i]),&view,&has_view);
        if(!t || t->format!=VK_FORMAT_R8G8B8A8_UNORM || t->type!=VK_IMAGE_TYPE_2D ||
            t->samples!=1 || t->layers!=1 || t->width!=intermediate->width || t->height!=intermediate->height ||
            (has_view && (view.set_format || view.set_levels || view.set_layers))) continue;
        if(source && source->image!=t->image) goto unlock; // ambiguous stale binding
        source=t;source_slot=(int)i;
    }
    if(!source) goto unlock;
    for(unsigned i=0;i<image_count;i++) {
        if(!ex->img[5][i]) continue;
        has_view=0;
        const VkTexImage *t=vk_texture_by_id_locked(NVN_HANDLE_TEX(ex->img[5][i]),&view,&has_view);
        if(!t || (t->format!=VK_FORMAT_R8G8B8A8_UNORM && t->format!=VK_FORMAT_R8G8B8A8_SRGB) ||
            t->type!=VK_IMAGE_TYPE_2D || t->samples!=1 || t->layers!=1 ||
            !(t->usage&VK_IMAGE_USAGE_STORAGE_BIT) || t->width<source->width || t->height<source->height ||
            (uint64_t)t->width*source->height!=(uint64_t)t->height*source->width ||
            (has_view && (view.set_levels || view.set_layers))) continue;
        if(has_view && view.set_format) {
            TexVkFormat format;
            if(!tex_vk_format(view.format,&format) || format.vk!=VK_FORMAT_R8G8B8A8_UNORM) continue;
        }
        if(destination && destination->image!=t->image) goto unlock;
        destination=t;destination_slot=(int)i;
    }
    if(!destination || destination->image==source->image) goto unlock;
    width=destination->width;height=destination->height;
unlock:
    vk_texture_unlock();
    if(!width || !height) return 0;
    static const GfxShader *shaders[128][32];
    const GfxShader *shader=shaders[source_slot][destination_slot];
    if(!shader) {
        char reflection[512];
        snprintf(reflection,sizeof reflection,
            "{\"stage\":\"cs\",\"cbufs\":[],\"sbufs\":[],"
            "\"textures\":[{\"binding\":1,\"type\":3,\"cbuf_slot\":2,\"handle\":%u,\"array\":1}],"
            "\"images\":[{\"binding\":2,\"type\":3,\"cbuf_slot\":2,\"handle\":%u,\"array\":1,"
            "\"format\":\"R8G8B8A8Unorm\",\"flags\":4}]}",8+source_slot*2,72+destination_slot*2);
        shader=gfx_shader_own(df_movie_scale_spv,sizeof df_movie_scale_spv/4,reflection);
        if(!shader) rt_fatal("Movie reconstruction reflection is invalid");
        shaders[source_slot][destination_slot]=shader;
    }
    const VkPipeInfo *info;
    VkPipeline pipeline=vk_pipeline_compute(shader,&info);
    if(!pipeline || !info) rt_fatal("Movie reconstruction pipeline failed");
    vk_exec_barrier(ex);
    bind_pipeline(ex,VK_PIPELINE_BIND_POINT_COMPUTE,pipeline);
    bind_resources(ex,info);
    p_dispatch replacement={(width+7)/8,(height+7)/8,1,dispatch->caller};
    VkPassMark *mark=dispatch_mark(ex,shader,replacement.x,replacement.y,1);
    vkCmdDispatch(ex->cb,replacement.x,replacement.y,1);
    vk_pass_mark_end(ex->cb,mark);
    ex->recorded++;
    if(vk_dump_armed) vk_dump_dispatch(ex,shader,pipeline,info,&replacement);
    static int reported;
    if(!reported++) rt_log("DekuForge: portable movie reconstruction active (%ux%u, source %d, output %d)",
        width,height,source_slot,destination_slot);
    return 1;
}
