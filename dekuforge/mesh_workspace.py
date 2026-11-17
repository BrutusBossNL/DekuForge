"""Compose native Vulkan task/mesh execution over the pinned runtime."""


def stage_mesh(output, write):
    import hashlib
    root = output.parent.parent
    movie = root / "engine_overrides/movie_scale.comp"
    write(output / "runtime/shaders/df_movie_scale.comp", movie.read_text(encoding="utf-8"))
    movie_digest = hashlib.sha256(movie.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    movie_header = root / "build/host-shaders" / movie_digest / "df_movie_scale_spv.h"
    if movie_header.is_file():
        write(output / "runtime/df_movie_scale_spv.h", movie_header.read_text(encoding="utf-8"))
    write(output / "runtime/df_movie_scale.inc", (root / "engine_overrides/movie_scale.inc").read_text(encoding="utf-8"))
    source = root / "engine_overrides/scene_scale.comp"
    write(output / "runtime/shaders/df_scene_scale.comp", source.read_text(encoding="utf-8"))
    digest = hashlib.sha256(source.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    header = root / "build/host-shaders" / digest / "df_scene_scale_spv.h"
    if header.is_file():
        write(output / "runtime/df_scene_scale_spv.h", header.read_text(encoding="utf-8"))
    easu = root / "engine_overrides/scene_easu.comp"
    write(output / "runtime/shaders/df_scene_easu.comp", easu.read_text(encoding="utf-8"))
    easu_digest = hashlib.sha256(easu.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    easu_header = root / "build/host-shaders" / easu_digest / "df_scene_easu_spv.h"
    if easu_header.is_file():
        write(output / "runtime/df_scene_easu_spv.h", easu_header.read_text(encoding="utf-8"))
    write(output / "runtime/df_scene_scale.inc", (root / "engine_overrides/scene_scale.inc").read_text(encoding="utf-8"))
    write(output / "runtime/df_gpu_pass_timing.inc", (root / "engine_overrides/gpu_pass_timing.inc").read_text(encoding="utf-8"))
    write(output / "runtime/df_compute_counter_stage.inc", (root / "engine_overrides/compute_counter_stage.inc").read_text(encoding="utf-8"))
    write(output / "runtime/df_counter_address_map.h", (root / "engine_overrides/counter_address_map.h").read_text(encoding="utf-8"))
    for name in ("global_memory_ranges.inc", "global_memory_binding.inc", "global_memory_completion.inc", "texture_numeric.inc", "depth_dummy.inc", "nvn2_stages.h", "mesh_draw_trace.inc", "mesh_fragment_interface.inc", "mesh_point_interface.inc"):
        write(output / "runtime" / ("df_" + name), (output.parent.parent / "engine_overrides" / name).read_text(encoding="utf-8"))
    def edit(name, changes):
        path = output / "runtime" / name
        text = path.read_text(encoding="utf-8")
        for old, new in changes:
            if old not in text:
                raise ValueError(f"Mesh composition anchor missing in {name}: {old[:70]}")
            count = 1 if old.startswith("    VkGraphicsPipelineCreateInfo pi") else -1
            text = text.replace(old, new, count)
        write(path, text)

    write(output / "runtime/df_startup_progress.inc", (root / "engine_overrides/startup_progress.inc").read_text(encoding="utf-8"))
    edit("gfx.h", [('void gfx_window_start(void);', '''#ifdef _WIN32
void df_startup_progress(unsigned stage, unsigned done, unsigned total);
#else
static inline void df_startup_progress(unsigned stage, unsigned done, unsigned total) {
    (void)stage; (void)done; (void)total;
}
#endif
void gfx_window_start(void);''')])
    edit("gfx_window_win.c", [
        ('static LRESULT CALLBACK wnd_proc(HWND h, UINT m, WPARAM w, LPARAM l) {',
         '''#include "df_startup_progress.inc"
static LRESULT CALLBACK wnd_proc(HWND h, UINT m, WPARAM w, LPARAM l) {
    if (m == DF_STARTUP_MESSAGE) {
        const unsigned *values = (const unsigned *)l;
        df_startup.stage = values[0]; df_startup.done = values[1]; df_startup.total = values[2];
        if (df_startup.stage) { InvalidateRect(h, NULL, FALSE); UpdateWindow(h); }
        return 0;
    }
    if (m == WM_PAINT && df_startup.stage) { df_startup_paint(h); return 0; }'''),
    ])
    edit("boot.c", [
        ('    vk_pipeline_prewarm();', '''    const char *df_gpu = rt_config()->gpu;
    int df_visible = !rt_config()->shot && !(df_gpu && !strcmp(df_gpu, "null"));
    if (df_visible) { gfx_window_start(); df_startup_progress(1, 0, 0); }
    vk_pipeline_prewarm();
    if (df_visible) df_startup_progress(0, 0, 0);'''),
    ])
    edit("gfx_shader.c", [
        ('    size_t total = w.n_named + w.n_other;',
         '    size_t total = w.n_named + w.n_other;\n    df_startup_progress(1, 0, (unsigned)total);'),
        ('''        while (!plat_thread_join_ns(t[m], 2000000000u))
            rt_log("gfx_shader: prewarm: %lld of %zu shaders, %llu translated, %.0f ms", (long long)w.done, total,
                   (unsigned long long)((uint64_t)n_xlated - xl0), (double)plat_now_ms() - t0);''',
         '''        while (!plat_thread_join_ns(t[m], 2000000000u)) {
            unsigned done = (unsigned)__atomic_load_n(&w.done, __ATOMIC_RELAXED);
            df_startup_progress(1, done, (unsigned)total);
            rt_log("gfx_shader: prewarm: %u of %zu shaders, %llu translated, %.0f ms", done, total,
                   (unsigned long long)((uint64_t)n_xlated - xl0), (double)plat_now_ms() - t0);
        }
    df_startup_progress(1, (unsigned)total, (unsigned)total);'''),
    ])

    edit("vk_caps.c", [
        ('    const char *e = cfg_get("NX2NAVI_GPL");\n    vk_caps.gpl = gpl_lib && gpl_fast && !(e && !strcmp(e, "0"));',
         '    vk_caps.gpl = gpl_lib && gpl_fast && cfg_bool("NX2NAVI_GPL");'),
    ])
    # This workspace targets NVN2. Within each 512-byte GOB, the two address
    # bits for x[4] and y[1] exchange positions relative to the pinned X1 layout.
    edit("tex_deswizzle.c", [
        ('//     (x%64/32)*256 + (y%8/2)*64 + (x%32/16)*32 + (y%2)*16 + x%16',
         '//   DekuForge NVN2 order: x[3:0], y[1:0], x[4], y[2], x[5] from low to high.'),
        ('// 16-byte segments of a GOB row (x % 64 = 0, 16, 32, 48) sit at 0, 32, 256 and 288 of it.',
         '// NVN2 segment offsets are derived from gob_off so the bulk and tail paths agree.'),
        ('    return (x % 64 / 32) * 256 + (y % 8 / 2) * 64 + (x % 32 / 16) * 32 + (y % 2) * 16 + x % 16;',
         '''    uint32_t x1 = (x & 15u) | ((y & 1u) << 4) | ((x & 16u) << 1) |
        ((y & 6u) << 5) | ((x & 32u) << 3);
    // DekuForge NVN2 adaptation: reorder the two inner 16-byte lanes.
    return (x1 & ~96u) | ((x1 & 32u) << 1) | ((x1 & 64u) >> 1);'''),
        ('    static const uint32_t seg[4] = {0, 32, 256, 288};',
         '    const uint32_t seg[4] = {gob_off(0, 0), gob_off(16, 0), gob_off(32, 0), gob_off(48, 0)};'),
    ])
    edit("tex_probe.c", [
        ('    // BC1, 64x48: blocks uploaded as they are, read back from the image',
         '''    // A storage-image result must remain GPU-owned when later sampled.
    tex_t stored = make_tex(tpool, 0x80000, 0x25, 16, 16, 1, 99);
    uint8_t *expected[4] = {0};
    if (fill_storage(&stored, expected)) return 1;
    const VkTexImage *storage_img = vk_texture_get(&stored);
    GCHECK(storage_img && !storage_img->gpu_owned, "storage fixture starts CPU-owned");
    vk_texture_lock();
    vk_texture_storage_bound_locked(storage_img, 0);
    GCHECK(!storage_img->gpu_owned, "read-only image binding preserves ownership");
    vk_texture_storage_bound_locked(storage_img, 1);
    GCHECK(storage_img->gpu_owned, "image store transfers ownership to GPU");
    vk_texture_unlock();
    VkCommandBuffer sc = vk_upload_begin();
    VkMemoryBarrier2 sm = {.sType=VK_STRUCTURE_TYPE_MEMORY_BARRIER_2,
        .srcStageMask=VK_PIPELINE_STAGE_2_ALL_COMMANDS_BIT, .srcAccessMask=VK_ACCESS_2_MEMORY_WRITE_BIT,
        .dstStageMask=VK_PIPELINE_STAGE_2_TRANSFER_BIT, .dstAccessMask=VK_ACCESS_2_TRANSFER_WRITE_BIT};
    VkDependencyInfo sd = {.sType=VK_STRUCTURE_TYPE_DEPENDENCY_INFO, .memoryBarrierCount=1, .pMemoryBarriers=&sm};
    vkCmdPipelineBarrier2(sc, &sd);
    VkClearColorValue colour = {.float32={1, 0, 1, 1}};
    VkImageSubresourceRange sr = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};
    vkCmdClearColorImage(sc, storage_img->image, VK_IMAGE_LAYOUT_GENERAL, &colour, 1, &sr);
    sm.srcStageMask=VK_PIPELINE_STAGE_2_TRANSFER_BIT; sm.srcAccessMask=VK_ACCESS_2_TRANSFER_WRITE_BIT;
    sm.dstStageMask=VK_PIPELINE_STAGE_2_ALL_COMMANDS_BIT; sm.dstAccessMask=VK_ACCESS_2_MEMORY_READ_BIT;
    vkCmdPipelineBarrier2(sc, &sd);
    vk_upload_end();
    for (unsigned si=0; si<16*16; si++) {
        expected[0][si*4]=255; expected[0][si*4+1]=0;
        expected[0][si*4+2]=255; expected[0][si*4+3]=255;
    }
    if (read_back(&stored, 0, expected, 0, "storage result ignores old CPU texels")) return 1;
    vk_texture_release(&stored);
    free(expected[0]);
    g_gpu_checks += 3;

    // BC1, 64x48: blocks uploaded as they are, read back from the image'''),
        ('    t.pool = pool, t.off = (int64_t)off, t.mem = pool->mem + off, t.serial = serial;',
         '    t.pool = pool, t.pool_flags = pool->flags, t.off = (int64_t)off, t.mem = pool->mem + off, t.serial = serial;'),
        ('// Byte offset inside a 64 x 8 GOB from the bit layout: x[3:0] -> 0-3, y[0] -> 4, x[4] -> 5, y[2:1] -> 6-7, x[5] -> 8.',
         '// DekuForge NVN2 oracle: x[3:0] -> 0-3, y[1:0] -> 4-5, x[4] -> 6, y[2] -> 7, x[5] -> 8.'),
        ('    return (x & 15) | (y & 1) << 4 | (x >> 4 & 1) << 5 | (y >> 1 & 3) << 6 | (x >> 5 & 1) << 8;',
         '    return (x & 15) | ((y & 3) << 4) | ((x & 16) << 2) | ((y & 4) << 5) | ((x & 32) << 3);'),
    ])

    edit("nvn_api_cmd.c", [
        ('NVN_API(nvnCommandBufferBindProgram) {', '#include "df_nvn2_stages.h"\nNVN_API(nvnCommandBufferBindProgram) {'),
        ('(p_bind_program){arg_p(c, 1), (int)arg_x(c, 2)}',
         '(p_bind_program){arg_p(c, 1), df_nvn_stage_mask((int)arg_x(c, 2))}'),
        ('int st = (int)arg_x(c, 1), first =', 'int st = df_nvn_stage((int)arg_x(c, 1)), first ='),
        ('(p_bind_buf){(int)arg_x(c, 1), (int)arg_x(c, 2), arg_x(c, 3), arg_x(c, 4)}',
         '(p_bind_buf){df_nvn_stage((int)arg_x(c, 1)), (int)arg_x(c, 2), arg_x(c, 3), arg_x(c, 4)}'),
        ('r->stage = st;', 'r->stage = df_nvn_stage(st);')])
    edit("vk_exec_xfer.c", [
        ('if (int_format(img->format) != (p->is_uint != 0)) {',
         '''// Positive zero has the same representation in every clear union member.
        // The guest also uses its float clear entry point to zero integer images.
        int zero = !(p->c.u[0] | p->c.u[1] | p->c.u[2] | p->c.u[3]);
        if (!zero && int_format(img->format) != (p->is_uint != 0)) {'''),
        ('"texture clear value kind (uint %d) does not match format %d: skipped", p->is_uint, (int)img->format',
         '"texture clear value kind (uint %d) does not match format %d: skipped; words %08x %08x %08x %08x", p->is_uint, (int)img->format, p->c.u[0], p->c.u[1], p->c.u[2], p->c.u[3]')])
    edit("gfx.h", [("GFX_STAGE_FS, GFX_STAGE_CS };", "GFX_STAGE_FS, GFX_STAGE_CS, GFX_STAGE_TS, GFX_STAGE_MS };")])
    edit("vk_texture.c", [
        ('// tex_info). Its storage is not marked GPU-owned: only the write fence for ReadTexels.',
         '// tex_info). Written bindings become GPU-owned; read-only bindings only record their fence.'),
        ('void vk_texture_storage_bound_locked(const VkTexImage *img) {',
         'void vk_texture_storage_bound_locked(const VkTexImage *img, int written) {'),
        ('    if (f > e->wr_fence) e->wr_fence = f;\n}\n\nuint64_t vk_texture_last_write',
         '''    if (f > e->wr_fence) e->wr_fence = f;
    // Storage writes are authoritative just like attachment and copy writes.
    // Otherwise a later CPU-page freshness check can replace the compute result
    // with old block-linear storage, and aliases never see the GPU's result.
    if (written) vk_texture_gpu_written(&e->t);
}

uint64_t vk_texture_last_write'''),
        ('if ((d->flags & NVN_TEXTURE_FLAGS_IMAGE) && (ff & VK_FORMAT_FEATURE_STORAGE_IMAGE_BIT) && samples == 1)',
         '''// NVN2 compute destinations do not use the pinned NVN1 IMAGE flag.
    // Allocate supported single-sample colour images for storage use up front;
    // Vulkan usage cannot be added when a later dispatch first binds the image.
    if (!ds && (ff & VK_FORMAT_FEATURE_STORAGE_IMAGE_BIT) && samples == 1)'''),
        ('    VkImageCreateFlags flags = ds ? 0 : VK_IMAGE_CREATE_MUTABLE_FORMAT_BIT;', '''    // An sRGB target can be written through its compatible UNORM view.
    VkFormat storage_view = f.vk == VK_FORMAT_R8G8B8A8_SRGB ? VK_FORMAT_R8G8B8A8_UNORM :
                            f.vk == VK_FORMAT_B8G8R8A8_SRGB ? VK_FORMAT_B8G8R8A8_UNORM : VK_FORMAT_UNDEFINED;
    int extended_storage = samples == 1 && storage_view &&
                           (features_of(storage_view) & VK_FORMAT_FEATURE_STORAGE_IMAGE_BIT);
    if (extended_storage) usage |= VK_IMAGE_USAGE_STORAGE_BIT;
    VkImageCreateFlags flags = ds ? 0 : VK_IMAGE_CREATE_MUTABLE_FORMAT_BIT;
    if (extended_storage) flags |= VK_IMAGE_CREATE_EXTENDED_USAGE_BIT;'''),
        ('    // A followed texture is another descriptor at the same storage:', '''    // A shared-exponent sampling descriptor may follow a live packed-float
    // render target at the same address. Preserve its interpretation of those
    // 32-bit texels instead of feeding R11G11B10 values to the image network.
    if (e && e->pub.format == VK_FORMAT_B10G11R11_UFLOAT_PACK32 &&
        !(s->has_view && s->v.set_format)) {
        TexVkFormat requested;
        if (tex_vk_format(s->t.d.format, &requested) && requested.vk == VK_FORMAT_E5B9G9R9_UFLOAT_PACK32) {
            if (!*has_view) memset(view, 0, sizeof *view);
            view->set_format = 1;
            view->format = s->t.d.format;
            *has_view = 1;
            static unsigned reported;
            if (reported++ < 4) rt_log("DekuForge: preserve RGB9E5 sampling view of shared scene image at %#llx",
                                      (unsigned long long)e->pub.addr);
        }
    }
    // A followed texture is another descriptor at the same storage:'''),
        ('if (!s->has_view) memset(view, 0, sizeof *view);', 'if (!*has_view) memset(view, 0, sizeof *view);')])
    edit("vk.h", [("} VkMemSpan;", "} VkMemSpan;\nsize_t df_global_ranges(uint64_t (*out)[2], size_t capacity);\nsize_t df_global_address_map(uint64_t (*out)[4], size_t capacity, uint64_t *generation);\nvoid df_global_host_barrier(VkCommandBuffer cb);")])
    edit("vk_sync.c", [("    if (recorded) ts_end(s->cb, fence);", "    if (recorded) df_global_host_barrier(s->cb);\n    if (recorded) ts_end(s->cb, fence);")])
    edit("vk_crumbs.c", [
        ('static void pass_marks_init(VkCtx *c) {', '#include "df_gpu_pass_timing.inc"\nstatic void pass_marks_init(VkCtx *c) {'),
        ('vk_pass_marks_on = pm_amd || set_checkpoint;', 'vk_pass_marks_on = pm_amd || set_checkpoint || df_timing_frame();'),
        ('void vk_pass_mark_cmd(VkCommandBuffer cb, uint32_t id, int end) {',
         'void vk_pass_mark_cmd(VkCommandBuffer cb, uint32_t id, int end) {\n    df_timing_mark(cb, id, end);')])
    edit("vk_exec_draw.c", [
        ('static void bind_resources(VkExec *ex, const VkPipeInfo *info) {',
         '#include "df_compute_counter_stage.inc"\nstatic void bind_resources(VkExec *ex, const VkPipeInfo *info) {'),
        ('    // Under the validation layer, a new graphics layout binds set 1',
         '    if (!gfx) df_counter_prepare(ex, info, d);\n    // Under the validation layer, a new graphics layout binds set 1'),
        ('    c0_dim[0] = (uint32_t)d->x, c0_dim[1] = (uint32_t)d->y, c0_dim[2] = (uint32_t)d->z;',
         '    df_counter_direct = 1;\n    c0_dim[0] = (uint32_t)d->x, c0_dim[1] = (uint32_t)d->y, c0_dim[2] = (uint32_t)d->z;'),
        ('    if (vk_dump_armed) vk_dump_dispatch(ex, cs, p, info, d);',
         '    df_counter_direct = 0;\n    df_counter_finish(ex);\n    if (vk_dump_armed) vk_dump_dispatch(ex, cs, p, info, d);'),
        ('static void op_dispatch(VkExec *ex, const p_dispatch *d) {',
         '#include "df_scene_scale.inc"\n#include "df_movie_scale.inc"\nstatic void op_dispatch(VkExec *ex, const p_dispatch *d) {'),
        ('    const GfxShader *cs = shader_for(ex, NVN_STAGE_CS, &present, NULL, 0);   // synchronous:',
         '    if (df_scene_scale(ex, d) || df_movie_scale(ex, d)) return;\n    const GfxShader *cs = shader_for(ex, NVN_STAGE_CS, &present, NULL, 0);   // synchronous:'),
        ('static void twins_release(VkCtx *c);', '#include "df_mesh_draw_trace.inc"\nstatic void twins_release(VkCtx *c);'),
        ('void vk_exec_draw_shutdown(void) {', 'void vk_exec_draw_shutdown(void) {\n    df_mesh_trace_shutdown();'),
        ('ex->prog = b->prog, ex->prog_stages = b->stages;', '''// Log distinct masks while diagnosing native stage binding.
        static uint64_t seen_bindings;
        unsigned mask = (unsigned)b->stages & 63;
        if (!(seen_bindings & (UINT64_C(1) << mask))) {
            seen_bindings |= UINT64_C(1) << mask;
            unsigned available = 0;
            if (b->prog) for (unsigned i = 0; i < b->prog->nstage && i < 6; i++) {
                const uint8_t *control = b->prog->sd[i].control;
                uint32_t stage = 0;
                if (control) memcpy(&stage, control + 0x714, 4);
                if (control && stage < 6) available |= 1u << stage;
            }
            rt_log("program binding: mask %02x, available stages %02x", mask, available);
        }
        ex->prog = b->prog, ex->prog_stages = b->stages;'''),
        ('static void dummies_init(void) {', '#include "df_depth_dummy.inc"\nstatic void dummies_init(void) {'),
        ('void vk_exec_draw_shutdown(void) {', 'void vk_exec_draw_shutdown(void) {\n    df_shadow_dummy_shutdown();'),
        ('if (img) view = get_view(ex, img, &v, hv, r->type, storage), *image = img->image;', '''// A typed bindless shadow array shares slot numbers with colour textures.
        // Only its depth-compatible entries can be sampled through this array.
        if (img && !storage && r->count > 1 && (r->type & 0x400) &&
            !(vk_exec_view_aspect(img, &v, hv) & VK_IMAGE_ASPECT_DEPTH_BIT)) img = NULL;
        if (img) view = get_view(ex, img, &v, hv, r->type, storage), *image = img->image;'''),
        ('view = storage ? storage_dummy(di, r->format) : Z.img[di].view;',
         'view = storage ? storage_dummy(di, r->format) : (r->type & 0x400) ? df_shadow_dummy(di) : Z.img[di].view;'),
        ('samp = point ? vk_sampler_point_by_id_locked(sid) : vk_sampler_by_id_locked(sid);',
         'samp = img ? (point ? vk_sampler_point_by_id_locked(sid) : vk_sampler_by_id_locked(sid)) : VK_NULL_HANDLE;'),
        ('#include "vk_exec.h"', '#include "vk_exec.h"\n#include "tex.h"'),
        ('uint8_t tt[32], it[32];', 'uint8_t tt[32], it[32], ifmt[32];'),
        ('c->it[slot] = type_of_handle(hi),', 'c->ifmt[slot] = df_storage_format_of_handle(hi), c->it[slot] = type_of_handle(hi),'),
        ('a->img_type[slot] = c->it[slot];', 'a->img_type[slot] = c->it[slot] & 63, a->img_format[slot] = c->ifmt[slot];'),
        ('static void answers_for(', '''static uint8_t df_storage_format_of_handle(uint64_t handle) {
    view_t view;
    int has_view;
    const VkTexImage *image = handle ? vk_texture_by_id_locked(NVN_HANDLE_TEX(handle), &view, &has_view) : NULL;
    if (!image) return 0;
    VkFormat format = image->format;
    if (has_view && view.set_format) {
        TexVkFormat requested;
        if (!tex_vk_format(view.format, &requested)) return 0;
        format = requested.vk;
    }
    return df_storage_format(format);
}

static void answers_for('''),
        ("static uint8_t type_of_handle(uint64_t h)", '#include "df_texture_numeric.inc"\nstatic uint8_t type_of_handle(uint64_t h)'),
        ("return img ? (uint8_t)gfx_type_of(img, &v, hv) : 0;", """if (!img) return 0;
    VkFormat format = img->format;
    if (hv && v.set_format) {
        TexVkFormat requested;
        if (tex_vk_format(v.format, &requested)) format = requested.vk;
    }
    return (uint8_t)gfx_type_of(img, &v, hv) | df_texture_numeric(format);"""),
        ("    ViewKey k = {img->image, img->format, vt, aspect, l0, nl, y0, ny, swz};", """    VkFormat view_format = img->format;
    if (hv && v->set_format && aspect == VK_IMAGE_ASPECT_COLOR_BIT) {
        TexVkFormat requested;
        if (!tex_vk_format(v->format, &requested)) rt_fatal("Unsupported texture view format %u", v->format);
        view_format = requested.vk;
    }
    ViewKey k = {img->image, view_format, vt, aspect, l0, nl, y0, ny, swz};"""),
        (".format = img->format,\n                                .components", ".format = view_format,\n                                .components"),
        ('if (img->block_views) ci.pNext = &use;',
         '''if (img->block_views || view_format == VK_FORMAT_E5B9G9R9_UFLOAT_PACK32) ci.pNext = &use;
    if (view_format == VK_FORMAT_R8G8B8A8_SRGB || view_format == VK_FORMAT_B8G8R8A8_SRGB) {
        use.usage = img->usage & ~VK_IMAGE_USAGE_STORAGE_BIT;
        ci.pNext = &use;
    }'''),
        ('if (blocks) ci.pNext = &use;', '''if (blocks) ci.pNext = &use;
        if (format == VK_FORMAT_R8G8B8A8_SRGB || format == VK_FORMAT_B8G8R8A8_SRGB) {
            use.usage = img->usage & ~VK_IMAGE_USAGE_STORAGE_BIT;
            ci.pNext = &use;
        }'''),
        ("    int nwritten, cwritten;", "    int nwritten, cwritten;\n    uint32_t *df_log, *df_checks;\n    VkDescriptorBufferInfo df_log_info, df_log_readback, df_map_info, df_checks_info;\n    VmaAllocation df_log_alloc;\n    uint64_t df_map_gen;"),
        ("static void cb_done(void *arg)", '#include "df_global_memory_completion.inc"\nstatic void cb_done(void *arg)'),
        ("    for (int i = 0; i < r->nwritten; i++) vk_gpu_written", "    df_global_complete(r);\n    if (r->df_log_alloc) vmaDestroyBuffer(c->vma, r->df_log_info.buffer, r->df_log_alloc);\n    for (int i = 0; i < r->nwritten; i++) vk_gpu_written")])
    edit("vk_memory.c", [
        ("    if (c->has_conditional_rendering) u |=", "    if (c->has_buffer_device_address) u |= VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT;\n    if (c->has_conditional_rendering) u |="),
        ("    VkMemoryAllocateInfo ai = {.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO, .pNext = &im,", "    VkMemoryAllocateFlagsInfo address_flags = {.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_FLAGS_INFO, .flags = VK_MEMORY_ALLOCATE_DEVICE_ADDRESS_BIT};\n    if (c->has_buffer_device_address) im.pNext = &address_flags;\n    VkMemoryAllocateInfo ai = {.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO, .pNext = &im,")])
    memory = output / "runtime/vk_memory.c"
    memory_text = memory.read_text(encoding="utf-8")
    start = memory_text.index("static int resolve_locked(uint64_t addr, uint64_t size, VkMemSpan *out) {")
    end = memory_text.index("\nuint64_t vk_mem_gen(void)", start)
    resolver = memory_text[start:end]
    resolver = resolver.replace("static int resolve_locked(", "static int df_resolve_under_lock(", 1)
    resolver = resolver.replace("    plat_mutex_lock_shared(&pool_lock);\n", "", 1)
    resolver = resolver.replace("    plat_mutex_unlock_shared(&pool_lock);\n", "", 1)
    resolver += """
static int resolve_locked(uint64_t addr, uint64_t size, VkMemSpan *out) {
    plat_mutex_lock_shared(&pool_lock);
    int ok = df_resolve_under_lock(addr, size, out);
    plat_mutex_unlock_shared(&pool_lock);
    return ok;
}
"""
    write(memory, memory_text[:start] + resolver + memory_text[end:] + '\n#include "df_global_memory_ranges.inc"\n')
    edit("vk_exec_draw.c", [("static VkDescriptorBufferInfo ssbo_info(VkExec *ex, int st, const GfxShaderRes *r, int written) {", '#include "df_global_memory_binding.inc"\nstatic VkDescriptorBufferInfo ssbo_info(VkExec *ex, int st, const GfxShaderRes *r, int written) {\n    if ((uint8_t)r->cbuf_slot == 254) return df_mesh_checks_info(ex);\n    if ((uint8_t)r->cbuf_slot == 255) return df_global_info(ex, r);')])
    edit("vk_exec_draw.c", [
        ("    typeof(AC[0]) *c = &AC[st];", "    if (st == NVN_STAGE_CS) memcpy(&a->shared_bytes, ctl + 0x754, 4);\n    typeof(AC[0]) *c = &AC[st];"),
        ("VkBufferCopy cp = {ip.offset, B.c0_off[2] + 0x200, sizeof(VkDispatchIndirectCommand)};", """const uint8_t *control, *code;
        uint32_t code_size;
        VkDeviceSize dimensions = find_stage(ex->prog, NVN_STAGE_CS, &control, &code, &code_size)
            && df_control_ampere(control) ? 4 : 0x200;
        VkBufferCopy cp = {ip.offset, B.c0_off[2] + dimensions, sizeof(VkDispatchIndirectCommand)};"""),
    ])
    edit("vk.h", [('void vk_texture_storage_bound_locked(const VkTexImage *img);',
                    'void vk_texture_storage_bound_locked(const VkTexImage *img, int written);')])
    edit("vk_exec_draw.c", [('vk_texture_storage_bound_locked(img);',
                            'vk_texture_storage_bound_locked(img, (r->flags & 4) != 0);')])
    edit("vk_exec.h", [("#define VK_C0_BYTES 0x800u", "#define VK_C0_BYTES 0xa00u")])
    edit("nvn_obj.h", [("int32_t prim, first, count, base_instance, instances; } p_draw;", "int32_t prim, first, count, base_instance, instances; uint64_t df_ind; } p_draw;")])
    edit("vk.h", [("has_device_fault,", "has_device_fault, has_mesh_shader,"),
                  ("const GfxShader *vs, *fs;", "const GfxShader *vs, *fs, *task;")])
    edit("vk_device.c", [
        ('else if (!h->shaderStorageImageWriteWithoutFormat)',
         'else if (!h->shaderStorageImageExtendedFormats) miss = "shaderStorageImageExtendedFormats";\n    else if (!h->shaderStorageImageWriteWithoutFormat)'),
        ("VkPhysicalDeviceFeatures2 f2;", "VkPhysicalDeviceMeshShaderFeaturesEXT mesh;\n    VkPhysicalDeviceFeatures2 f2;"),
        ("    // Graphics pipeline library: chained last", """    if (has_ext(ep, ne, VK_EXT_MESH_SHADER_EXTENSION_NAME)) {
        ext[n_ext++] = VK_EXT_MESH_SHADER_EXTENSION_NAME;
        CHAIN(mesh, VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_MESH_SHADER_FEATURES_EXT);
    }
    // Graphics pipeline library: chained last"""),
        ("    vk_caps_driver(g_vk.phys);", "    g_vk.has_mesh_shader = c->mesh.taskShader && c->mesh.meshShader;\n    c->mesh.primitiveFragmentShadingRateMeshShader = VK_FALSE;\n    c->mesh.multiviewMeshShader = VK_FALSE;\n    vk_caps_driver(g_vk.phys);")])
    edit("gfx_shader.c", [
        ('"NX2NAVISPRP"', '"TOTKSPRP"'),
        ('    if (a) {\n        const char *sep = "";', '''    if (!strcmp(stage, "cs") && df_control_ampere(control)) {
        int end = (int)(df_control_word(control, 0xb8) >> 16);
        o += sprintf(o, ",\\\"nvn2_tex_base\\\":%d,\\\"nvn2_tex_count\\\":%d,\\\"nvn2_img_base\\\":%d,\\\"nvn2_img_count\\\":%d",
                     end - 8 * (control[0xb3] + control[0xb6]), control[0xb3],
                     end - 8 * control[0xb6], control[0xb6]);
    }
    if (a) {
        const char *sep = "";'''),
        ('if (a->tex_type[i] && a->tex_type[i] < COUNT(tex_names)) o += sprintf(o, "%s\\\"%d\\\":\\\"%s\\\"", sep, i, tex_names[a->tex_type[i]]), sep = ",";', '''if ((a->tex_type[i] & 63) && (a->tex_type[i] & 63) < COUNT(tex_names)) {
                const char *numeric = a->tex_type[i] & 128 ? "uint" : a->tex_type[i] & 64 ? "sint" : "float";
                o += sprintf(o, "%s\\\"%d\\\":{\\\"type\\\":\\\"%s\\\",\\\"numeric\\\":\\\"%s\\\"}", sep, i,
                             tex_names[a->tex_type[i] & 63], numeric);
                sep = ",";
            }'''),
        ("free(file), free(recs), free(iid), free(ab);\n    return ok ? 0 : 1;", "free(file), free(recs), free(iid), free(ab);\n    return ok && (uint64_t)n_failures == fail0 ? 0 : 1;"),
        ("uint32_t *pointee = calloc(bound, sizeof *pointee);", "uint32_t *pointee = calloc(bound, sizeof *pointee);\n    uint32_t *array_count = calloc(bound, sizeof *array_count), *constants = calloc(bound, sizeof *constants);"),
        ("!tcomps || !pointee) goto out;", "!tcomps || !pointee || !array_count || !constants) goto out;"),
        ("        } else if (op == OP_TYPE_INT", "        } else if (op == 43 && len == 4 && a[1] < bound) {\n            constants[a[1]] = a[2];\n        } else if (op == OP_TYPE_INT"),
        ("ttype[id] = ttype[a[1]], tcomps[id] = tcomps[a[1]];   // element type (arrayed interface blocks)", "ttype[id] = ttype[a[1]], tcomps[id] = tcomps[a[1]];\n            if ((s->stage == GFX_STAGE_VS || s->stage == GFX_STAGE_FS) && a[2] < bound)\n                array_count[id] = constants[a[2]] > 32 ? 32 : constants[a[2]];"),
        ("                if (sc == SC_INPUT) s->in_mask |= 1u << l, s->in[l] = io;\n                else s->out_mask |= 1u << l, s->out[l] = io;", "                uint32_t count = array_count[t] ? array_count[t] : 1;\n                for (uint32_t offset = 0; offset < count && l + offset < 32; offset++) {\n                    if (sc == SC_INPUT) s->in_mask |= 1u << (l + offset), s->in[l + offset] = io;\n                    else s->out_mask |= 1u << (l + offset), s->out[l + offset] = io;\n                }"),
        ("free(loc), free(packed), free(ttype), free(tcomps), free(pointee);", "free(loc), free(packed), free(ttype), free(tcomps), free(pointee), free(array_count), free(constants);"),
        ('!strncmp(st, "\\\"cs\\\"", 4)', '!strncmp(st, "\\\"cs\\\"", 4) || !strncmp(st, "\\\"ts\\\"", 4) || !strncmp(st, "\\\"ms\\\"", 4)'),
        ('!strcmp(stage, "cs") ? GFX_STAGE_CS', '!strcmp(stage, "ts") ? GFX_STAGE_TS : !strcmp(stage, "ms") ? GFX_STAGE_MS : !strcmp(stage, "cs") ? GFX_STAGE_CS'),
        ('stage == GFX_STAGE_CS ? "cs" : NULL', 'stage == GFX_STAGE_CS ? "cs" : stage == GFX_STAGE_TS ? "ts" : stage == GFX_STAGE_MS ? "ms" : NULL'),
        ('    if (a) {\n        const char *sep = "";', '''    if (!strcmp(stage, "ts") || !strcmp(stage, "ms")) {
        o += sprintf(o, ",\\\"mesh_control\\\":\\\"");
        for (unsigned i = 0; i < 0xd8; i++) o += sprintf(o, "%02x", control[i]);
        o += sprintf(o, "\\\"");
    }
    if (a) {
        const char *sep = "";'''),
        ("stages[6] = {0}", "stages[8] = {0}"),
        ("a[0] < 6 ? a[0] : 0", "a[0] < 8 ? a[0] : 0")])

    edit("vk_pipeline.c", [
        ('    vkCmdSetDepthCompareOp(cb, compare_op(d->df));', '''    VkCompareOp df_compare = compare_op(d->df);
    const char *df_depth_probe = getenv("DEKUFORGE_DIAGNOSTIC_DEPTH_EQUAL");
    if (df_depth_probe && d->dt && !d->dw &&
        df_compare == VK_COMPARE_OP_EQUAL) {
        if (!strcmp(df_depth_probe, "always")) df_compare = VK_COMPARE_OP_ALWAYS;
        else if (!strcmp(df_depth_probe, "lequal")) df_compare = VK_COMPARE_OP_LESS_OR_EQUAL;
        else if (!strcmp(df_depth_probe, "gequal")) df_compare = VK_COMPARE_OP_GREATER_OR_EQUAL;
        static int reported;
        if (df_compare != VK_COMPARE_OP_EQUAL && !reported++)
            rt_log("DekuForge: diagnostic read-only EQUAL depth test override: %s", df_depth_probe);
    }
    vkCmdSetDepthCompareOp(cb, df_compare);'''),
        ('    P.max_push = pd.maxPushDescriptors;', '''    P.max_push = pd.maxPushDescriptors;
    const char *df_no_push = getenv("DEKUFORGE_NO_PUSH_DESCRIPTORS");
    if (df_no_push && !strcmp(df_no_push, "1")) {
        P.max_push = 0;
        rt_log("DekuForge: diagnostic allocated-descriptor route enabled");
    }'''),
        ('!memcmp(h.magic, "NX2NAVIPKEY", 8)', '!memcmp(h.magic, "TOTKPKEY", 8)'),
        ("uint8_t vs[32], fs[32];", "uint8_t vs[32], fs[32], task[32];"),
        ("uint32_t has_fs, pad;", "uint32_t has_fs, has_task;"),
        ("    r->s = *s;", "    if (s->task) memcpy(r->task, gfx_shader_input_id(s->task), 32), r->has_task = 1;\n    r->s = *s;"),
        ("r->s.vs = r->s.fs = NULL;", "r->s.vs = r->s.fs = r->s.task = NULL;"),
        ("malloc(2 * n * 32)", "malloc(3 * n * 32)"),
        ("calloc(2 * n, sizeof *sh)", "calloc(3 * n, sizeof *sh)"),
        ("if (r[i].has_fs) memcpy(ids[m++], r[i].fs, 32);", "if (r[i].has_fs) memcpy(ids[m++], r[i].fs, 32);\n        if (r[i].has_task) memcpy(ids[m++], r[i].task, 32);"),
        ("        if (!vs || (r[i].has_fs && !fs)) {", "        const uint8_t (*t)[32] = r[i].has_task ? bsearch(r[i].task, ids, u, 32, id_cmp) : NULL;\n        const GfxShader *task = t ? sh[t - ids] : NULL;\n        if (!vs || (r[i].has_fs && !fs) || (r[i].has_task && !task)) {"),
        ("s.vs = vs, s.fs = fs;", "s.vs = vs, s.fs = fs, s.task = task;"),
        ("const GfxShader *vs, *fs;", "const GfxShader *vs, *fs, *task;"),
        ("k->vs = s->vs, k->fs = s->fs;", "k->vs = s->vs, k->fs = s->fs, k->task = s->task;"),
        ("static VkShaderStageFlags stage_bit(int stage) {", """static VkShaderStageFlags stage_bit(int stage) {
    if (stage == GFX_STAGE_TS) return VK_SHADER_STAGE_TASK_BIT_EXT;
    if (stage == GFX_STAGE_MS) return VK_SHADER_STAGE_MESH_BIT_EXT;"""),
        (".pSetLayouts = &l->set};", """.pSetLayouts = &l->set};
    VkPushConstantRange mesh_push = {VK_SHADER_STAGE_TASK_BIT_EXT | VK_SHADER_STAGE_MESH_BIT_EXT, 0, 16};
    for (int i = 0; i < B->n; i++) if (B->b[i].stageFlags & mesh_push.stageFlags) {
        pi.pushConstantRangeCount = 1; pi.pPushConstantRanges = &mesh_push; break;
    }"""),
        ("VkShaderModule vm = VK_NULL_HANDLE, fm = VK_NULL_HANDLE;", "VkShaderModule vm = VK_NULL_HANDLE, fm = VK_NULL_HANDLE, tm = VK_NULL_HANDLE;\n    int mesh = gfx_shader_stage(s->vs) == GFX_STAGE_MS;"),
        ("static VkPipeline create_graphics(", '#include "df_mesh_fragment_interface.inc"\n#include "df_mesh_point_interface.inc"\n\nstatic VkPipeline create_graphics('),
        ("        if (k->dsb) {", """        if (mesh) {
            static unsigned missing_reports;
            if (missing && !df_mesh_is_points(vcode, vw) && __atomic_fetch_add(&missing_reports, 1, __ATOMIC_RELAXED) < 8) {
                char mesh_id[65], fragment_id[65];
                for (unsigned b=0; b<32; ++b) {
                    snprintf(mesh_id+b*2, 3, "%02x", gfx_shader_input_id(s->vs)[b]);
                    snprintf(fragment_id+b*2, 3, "%02x", gfx_shader_input_id(s->fs)[b]);
                }
                rt_log("mesh interface: missing outputs %#x, mesh %s, fragment %s", missing, mesh_id, fragment_id);
            }
            uint64_t patched_words;
            if (missing && df_mesh_is_points(vcode, vw)) {
                uint32_t *points = df_fragment_point_inputs(fcode, fw, missing, &patched_words);
                if (points) fcode = fpatched = points, fw = patched_words;
            }
            uint32_t *matched = df_fragment_primitive_inputs(fcode, fw,
                df_mesh_primitive_mask(vcode, vw), &patched_words);
            if (matched) { free(fpatched); fcode = fpatched = matched; fw = patched_words; }
        }
        if (k->dsb) {"""),
        ("if (d) fcode = fpatched = d, fw = n2;", "if (d) { free(fpatched); fcode = fpatched = d; fw = n2; }"),
        ("if (missing && !l->set1)", "if (missing && !l->set1 && !mesh)"),
        ("VkPipelineShaderStageCreateInfo stages[2] = {", "VkPipelineShaderStageCreateInfo stages[3] = {"),
        (".stage = VK_SHADER_STAGE_VERTEX_BIT, .module = vm", ".stage = mesh ? VK_SHADER_STAGE_MESH_BIT_EXT : VK_SHADER_STAGE_VERTEX_BIT, .module = vm"),
        ("    VkPipelineShaderStageRequiredSubgroupSizeCreateInfo rqv, rqf;", """    unsigned stage_count = s->fs ? 2 : 1;
    if (s->task) {
        uint64_t tw; const uint32_t *tc = gfx_shader_spirv(s->task, &tw);
        uint32_t offset = binding_span(s->vs) + (s->fs ? binding_span(s->fs) - 1 : 0) - 1;
        uint32_t *patched = spirv_rebind(tc, tw, offset);
        tm = patched ? make_module(patched, tw) : VK_NULL_HANDLE;
        free(patched);
        if (!tm) goto out;
        stages[stage_count++] = (VkPipelineShaderStageCreateInfo){.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
            .stage=VK_SHADER_STAGE_TASK_BIT_EXT, .module=tm, .pName="main"};
    }
    VkPipelineShaderStageRequiredSubgroupSizeCreateInfo rqv, rqf;"""),
        (".stageCount = s->fs ? 2 : 1, .pStages = stages, .pVertexInputState = &vi,", ".stageCount = stage_count, .pStages = stages, .pVertexInputState = mesh ? NULL : &vi,"),
        (".pInputAssemblyState = &ia, .pViewportState = &vp", ".pInputAssemblyState = mesh ? NULL : &ia, .pViewportState = &vp"),
        ("    VkGraphicsPipelineCreateInfo pi = {.sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO, .pNext = &ri,", """    VkDynamicState mesh_dynamic[32];
    if (mesh) {
        dy.dynamicStateCount = 0;
        for (uint32_t i = 0; i < P.n_dyn; i++) {
            VkDynamicState state = P.dyn[i];
            if (state == VK_DYNAMIC_STATE_PRIMITIVE_TOPOLOGY || state == VK_DYNAMIC_STATE_PRIMITIVE_RESTART_ENABLE ||
                state == VK_DYNAMIC_STATE_VERTEX_INPUT_EXT || state == VK_DYNAMIC_STATE_VERTEX_INPUT_BINDING_STRIDE) continue;
            mesh_dynamic[dy.dynamicStateCount++] = state;
        }
        dy.pDynamicStates = mesh_dynamic;
    }
    VkGraphicsPipelineCreateInfo pi = {.sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO, .pNext = &ri,"""),
        ("    if (vm) vkDestroyShaderModule", "    if (tm) vkDestroyShaderModule(P.device, tm, NULL);\n    if (vm) vkDestroyShaderModule"),
        ("if (gfx_shader_stage(s->vs) != GFX_STAGE_VS ||", "if ((gfx_shader_stage(s->vs) != GFX_STAGE_VS && gfx_shader_stage(s->vs) != GFX_STAGE_MS) ||"),
        ("    else if (P.indep) {", "    else if (P.indep && gfx_shader_stage(s->vs) != GFX_STAGE_MS) {"),
        ('    else if (!(l = layout_get(&B))) why = "descriptor layout creation failed";', '''    else if (s->task && !add_stage(&B, s->task, span - 1 + (s->fs ? binding_span(s->fs) - 1 : 0))) why = "too many task bindings";
    else if (!(l = layout_get(&B))) why = "descriptor layout creation failed";'''),
        ("if (P.gpl && (!j->prebuild", "if (P.gpl && gfx_shader_stage(j->s.vs) != GFX_STAGE_MS && (!j->prebuild"),
        ("p->building && P.gpl &&", "p->building && P.gpl && gfx_shader_stage(s->vs) != GFX_STAGE_MS &&")])

    edit("vk_exec_draw.c", [
        ("VK_BUFFER_USAGE_TRANSFER_SRC_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT};", "VK_BUFFER_USAGE_TRANSFER_SRC_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT | VK_BUFFER_USAGE_INDIRECT_BUFFER_BIT | (vk_ctx()->has_buffer_device_address ? VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT : 0)};"),
        ("static const GfxShader *shader_for(VkExec *ex, int st, int *present, int *pending, int await) {", """static int df_mesh_draw;
static const VkPipeInfo *df_mesh_info;
static const GfxShader *shader_for(VkExec *ex, int st, int *present, int *pending, int await) {
    if (df_mesh_draw && st == NVN_STAGE_VS) st = 4;"""),
        ("int gs = st == NVN_STAGE_VS ?", "int gs = st == 3 ? GFX_STAGE_TS : st == 4 ? GFX_STAGE_MS : st == NVN_STAGE_VS ?"),
        ("static int nvn_stage_of(int gfx_stage) {", """static int nvn_stage_of(int gfx_stage) {
    if (gfx_stage == GFX_STAGE_TS) return 3;
    if (gfx_stage == GFX_STAGE_MS) return 4;"""),
        ("    if (memo && SM.valid", "    if (!df_mesh_draw && memo && SM.valid"),
        ("if (memo && vs &&", "if (!df_mesh_draw && memo && vs &&"),
        ("    s.vs = vs, s.fs = fs;", """    s.vs = vs, s.fs = fs; s.task = NULL;
    if (df_mesh_draw) {
        int present = 0;
        s.task = shader_for(ex, 3, &present, NULL, 1);
        if (present && !s.task) rt_fatal("Native task shader translation failed");
        const char *trace_frame = getenv("DEKUFORGE_TRACE_MESH_FRAME");
        if (trace_frame && __atomic_load_n(&gfx_counters.frames, __ATOMIC_RELAXED) == strtoull(trace_frame, NULL, 10)) {
            VkViewport vp = draw_viewport(ex);
            const uint8_t *vi = gfx_shader_input_id(vs);
            const uint8_t *fi = fs ? gfx_shader_input_id(fs) : NULL;
            rt_log("Mesh raster state: vs %02x%02x%02x%02x fs %02x%02x%02x%02x depth %llu format %d test %u write %u compare %u bias-enable %u bias %.9g %.9g %.9g viewport %.9g %.9g %.9g %.9g range %.9g %.9g",
                vi[0], vi[1], vi[2], vi[3], fi ? fi[0] : 0, fi ? fi[1] : 0, fi ? fi[2] : 0, fi ? fi[3] : 0,
                (unsigned long long)ex->depth.image, s.depth_fmt, s.ds.dt, s.ds.dw, s.ds.df, s.poly.offset_en,
                ex->poly_offset.units, ex->poly_offset.clamp, ex->poly_offset.factor,
                vp.x, vp.y, vp.width, vp.height, vp.minDepth, vp.maxDepth);
        }
    }"""),
        ("    bind_vertex_buffers(ex);", "    if (!df_mesh_draw) bind_vertex_buffers(ex);"),
        ("    vk_exec_oq_draw(ex);", "    if (df_mesh_draw) df_mesh_info = info;\n    vk_exec_oq_draw(ex);"),
        ("static void op_draw(VkExec *ex, const p_draw *d) {", """static void op_draw(VkExec *ex, const p_draw *d) {
    if (d->prim == 0x40) {
        if (d->count <= 0 && !d->df_ind) return;
        if (!vk_ctx()->has_mesh_shader) rt_fatal("This GPU lacks Vulkan task/mesh shader support");
        VkBuffer indirect_buffer = VK_NULL_HANDLE; VkDeviceSize indirect_offset = 0;
        uint64_t first_address = 0;
        if (d->df_ind) {
            if (!vk_ctx()->has_buffer_device_address) rt_fatal("Indirect mesh draws require buffer device addresses");
            VkMemSpan source;
            if (!vk_mem_resolve(d->df_ind, 8, &source) || source.offset % 4)
                rt_fatal("Indirect mesh arguments are not backed or aligned");
            uint32_t initial[4] = {0, 1, 1, 0};
            memcpy(scratch(ex, sizeof initial, &indirect_buffer, &indirect_offset), initial, sizeof initial);
            vk_exec_barrier(ex);
            VK_MEM_USE(source);
            VkBufferCopy copies[2] = {{source.offset, indirect_offset, 4}, {source.offset+4, indirect_offset+12, 4}};
            vkCmdCopyBuffer(ex->cb, source.buffer, indirect_buffer, 2, copies);
            df_mesh_trace_copy(ex, &source, d->df_ind);
            ex->recorded++;
            VK_MEM_BOUND(source);
            vk_exec_barrier(ex);
            VkBufferDeviceAddressInfo address = {.sType=VK_STRUCTURE_TYPE_BUFFER_DEVICE_ADDRESS_INFO, .buffer=indirect_buffer};
            first_address = vkGetBufferDeviceAddress(vk_ctx()->device, &address) + indirect_offset + 12;
        }
        df_mesh_draw = 1;
        df_mesh_info = NULL;
        int ready = prepare_draw(ex, NVN_DRAW_PRIMITIVE_TRIANGLES, d->df_ind ? 0x7fffffff : d->count, 0);
        df_mesh_draw = 0;
        if (!ready) return;
        PFN_vkCmdDrawMeshTasksEXT draw = (PFN_vkCmdDrawMeshTasksEXT)vkGetDeviceProcAddr(vk_ctx()->device, "vkCmdDrawMeshTasksEXT");
        if (!draw || !df_mesh_info) rt_fatal("Native mesh pipeline is unavailable");
        uint32_t args[4] = {(uint32_t)d->first, (uint32_t)d->count, (uint32_t)first_address, (uint32_t)(first_address >> 32)};
        vkCmdPushConstants(ex->cb, df_mesh_info->layout, VK_SHADER_STAGE_TASK_BIT_EXT | VK_SHADER_STAGE_MESH_BIT_EXT, 0, sizeof args, args);
        // Extension function pointers bypass the recorder's vkCmd macros. Drain
        // all queued bindings and barriers before issuing the draw on this thread.
        rec_drain();
        if (d->df_ind) {
            PFN_vkCmdDrawMeshTasksIndirectEXT indirect = (PFN_vkCmdDrawMeshTasksIndirectEXT)vkGetDeviceProcAddr(vk_ctx()->device, "vkCmdDrawMeshTasksIndirectEXT");
            if (!indirect) rt_fatal("Indirect mesh entry point is unavailable");
            indirect(ex->cb, indirect_buffer, indirect_offset, 1, 12);
        } else draw(ex->cb, (uint32_t)d->count, 1, 1);
        ex->recorded++; vk_exec_frame.draws++;
        return;
    }""")])
    edit("vk.h", [('void vk_device_fault_report(VkResult r);', 'void vk_device_fault_report(VkResult r);\nvoid df_mesh_trace_report(void);')])
    # Driver banks have distinct layouts for vertex, fragment, compute, task and mesh.
    edit("vk_exec_draw.c", [
        ('uint8_t c0[3][VK_C0_BYTES];', 'uint8_t c0[5][VK_C0_BYTES];'),
        ('VkBuffer c0_buf[3];', 'VkBuffer c0_buf[5];'),
        ('VkDeviceSize c0_off[3];', 'VkDeviceSize c0_off[5];'),
        ('int c0_valid[3];', 'int c0_valid[5];'),
        ('} c0_in[3];', '} c0_in[5];'),
        ('int k = st == NVN_STAGE_VS ? 0 : st == NVN_STAGE_FS ? 1 : 2;',
         'int k = st == NVN_STAGE_VS ? 0 : st == NVN_STAGE_FS ? 1 : st == 3 ? 3 : st == 4 ? 4 : 2;'),
    ])
    edit("vk_exec.h", [('void vk_exec_frame_log(', 'void df_condition_frame_end(void);\nvoid vk_exec_frame_log(')])
    edit("vk_exec.h", [('void df_condition_frame_end(void);', 'void df_condition_frame_end(void);\nvoid df_condition_work(unsigned kind, int skipped);')])
    edit("vk_exec_draw.c", [('    if (ex->render_disabled) return 0;', '    df_condition_work(0, ex->render_disabled);\n    if (ex->render_disabled) return 0;')])
    edit("vk_exec.c", [
        ('    vk_exec_frame.clears++;\n    if (ex->render_disabled) return;', '    vk_exec_frame.clears++;\n    df_condition_work(1, ex->render_disabled);\n    if (ex->render_disabled) return;'),
        ('static void clear_ds(VkExec *ex, const p_clear_ds *c) {', 'static void clear_ds(VkExec *ex, const p_clear_ds *c) {\n    df_condition_work(2, ex->render_disabled);'),
    ])
    edit("vk_rec.c", [('        mode = rt_knob("VK_RECORDER", vk_caps.amd ? "0" : "1");',
        '        mode = rt_knob("VK_RECORDER", vk_caps.amd ? "0" : "1");\n        if (getenv("DEKUFORGE_PROFILE_FRAME")) {\n            mode = 0;\n            rt_log("DekuForge: per-pass GPU profiling uses synchronous recording");\n        }')])
    edit("vk_pipeline.c", [
        ('return graphics(s, info, A.on, pending, wait_ms);',
         'return graphics(s, info, getenv("DEKUFORGE_SYNC_PIPELINES") ? 0 : A.on, pending, wait_ms);'),
    ])
    edit("vk_exec_draw.c", [
        ('    if (pending) *pending = 0;',
         '    if (pending) *pending = 0;\n    if (getenv("DEKUFORGE_SYNC_PIPELINES")) await = 1;'),
    ])
    edit("frame_rate.c", [
        ('    if (rt_trace & RT_TRACE_PERF) speed_report(display_ns, step, interval);',
         '    if ((rt_trace & RT_TRACE_PERF) || getenv("DEKUFORGE_TRACE_CLOCK")) speed_report(display_ns, step, interval);'),
    ])
    edit("vk_backend.c", [('    vk_exec_frame_log(t, frame);', '    df_condition_frame_end();\n    vk_exec_frame_log(t, frame);')])
    for name in ("condition_records.h", "condition_records.inc"):
        write(output / "runtime" / ("df_"+name), (root / "engine_overrides" / name).read_text(encoding="utf-8"))
    edit("vk_exec_xfer.c", [
        ('static void write_counter(uint64_t addr, uint64_t counter) {\n    uint64_t rec[2] = {counter, (uint64_t)((unsigned __int128)kern_now_ns() * 12 / 625)};\n    memcpy((void *)(uintptr_t)addr, rec, sizeof rec);\n}',
         '#include "df_condition_records.inc"\nstatic void write_counter(uint64_t addr, uint64_t counter, uint64_t serial) {\n    df_condition_publish(addr, counter, serial);\n}'),
        ('write_counter(*addr, 0);', 'write_counter(addr[0], 0, addr[1]);'),
        ('#define PENDING 256\nstatic struct { uint64_t addr, fence; int unknown; } pending[PENDING];\nstatic unsigned pending_head;', '// Counter state is tracked by the replay ledger above.'),
        ('typedef struct { uint64_t addr; int reset, lost;', 'typedef struct { uint64_t addr, serial; int reset, lost;'),
        ('write_counter(s->addr, oq_count);', 'write_counter(s->addr, oq_count, s->serial);'),
        ('    s->addr = addr, s->reset = reset,', '    s->serial = df_condition_serial(addr);\n    s->addr = addr, s->reset = reset,'),
        ('    if (samples) oq_report(ex, p->addr);', '    uint64_t serial = df_condition_report(p->addr, samples);\n    if (samples) oq_report(ex, p->addr);'),
        ('uint64_t *a = malloc(sizeof *a);', 'uint64_t *a = malloc(2 * sizeof *a);'),
        ('        *a = p->addr;', '        a[0] = p->addr; a[1] = serial;'),
        ('    pending[pending_head++ % PENDING] = (typeof(pending[0])){p->addr, ex->fence, samples};', ''),
        ('''    uint64_t done = vk_sync_fence_done();
    for (unsigned k = 1; k <= PENDING; k++) {   // newest first: the last report to addr decides
        unsigned i = (pending_head - k) % PENDING;
        if (pending[i].addr == addr && pending[i].fence > done) return *v = 0, pending[i].unknown ? 2 : 1;
    }''', '    int replay = df_condition_read(addr, v);\n    if (replay) return replay;'),
        ('        vkCmdFillBuffer(ex->cb, d.buffer, d.offset, n, p->value);', '        vkCmdFillBuffer(ex->cb, d.buffer, d.offset, n, p->value);\n        df_condition_fill(dst, n, p->value);'),
    ])
    edit("vk_device.c", [('    vk_pass_marks_report();', '    vk_pass_marks_report();\n    df_mesh_trace_report();')])
    edit("vk_pipeline.c", [
        ('static void lb_stop(void) {', '''static void df_prebuild_wait(void) {
    for (int i = 0; i < LB.threads; i++) {
        if (LB.th[i]) {
            while (!plat_thread_join_ns(LB.th[i], 100000000u)) {
                plat_mutex_lock_shared(&LB.stat);
                unsigned done = (unsigned)LB.done, total = (unsigned)LB.n;
                plat_mutex_unlock_shared(&LB.stat);
                df_startup_progress(3, done, total);
            }
        }
        LB.th[i] = NULL;
    }
    LB.threads = 0;
}

static void lb_stop(void) {'''),
        ('    for (int i = 0; i < nt; i++)\n        while (!plat_thread_join_ns(t[i], 2000000000u))\n            rt_log("vk_pipeline: prewarm: %u of %u pipelines, %.0f ms", K.built + K.failed, queued, now_ms() - t1);',
         '''    df_startup_progress(2, 0, queued);
    for (int i = 0; i < nt; i++) {
        while (!plat_thread_join_ns(t[i], 100000000u)) {
            plat_mutex_lock(&P.lock);
            unsigned complete = K.built + K.failed;
            plat_mutex_unlock(&P.lock);
            df_startup_progress(2, complete, queued);
        }
    }'''),
        ('static void lb_start(const uint32_t pr_hist[16], const uint32_t fs_hist[4]);',
         'static void lb_start(const uint32_t pr_hist[16], const uint32_t fs_hist[4]);\nstatic void df_prebuild_wait(void);'),
        ('if (ensure_init()) lb_start(pr_hist, fs_hist);',
         'if (ensure_init()) { lb_start(pr_hist, fs_hist); df_prebuild_wait(); }'),
        ('if (P.ready) lb_start(pr_hist, fs_hist);',
         'if (P.ready) { lb_start(pr_hist, fs_hist); df_prebuild_wait(); }'),
        ('    lb_start(pr_hist, fs_hist);\n}',
         '    lb_start(pr_hist, fs_hist);\n    df_prebuild_wait(); // Finish known compute preparation before entering guest code.\n}'),
        ('make_module(const uint32_t *w, uint64_t words)', 'make_module(const uint32_t *w, uint64_t words, const GfxShader *shader)'),
        ('make_module(fcode, fw)', 'make_module(fcode, fw, s->fs)'),
        ('make_module(vcode, vw)', 'make_module(vcode, vw, s->vs)'),
        ('make_module(patched, tw)', 'make_module(patched, tw, s->task)'),
        ('make_module(patched, fw)', 'make_module(patched, fw, s->fs)'),
        ('make_module(code, words)', 'make_module(code, words, cs)'),
        ('    VkResult r = vkCreateShaderModule(P.device, &ci, NULL, &m);', '''    // Optional, isolated GPU-AV scope: avoid instrumenting every large shader.
    const char *target = getenv("DEKUFORGE_GPU_VALIDATION_SHADER");
    VkValidationFeatureEnableEXT enable = VK_VALIDATION_FEATURE_ENABLE_GPU_ASSISTED_EXT;
    VkValidationFeaturesEXT validation = {.sType = VK_STRUCTURE_TYPE_VALIDATION_FEATURES_EXT,
        .enabledValidationFeatureCount = 1, .pEnabledValidationFeatures = &enable};
    if (target && strlen(target) == 64 && shader && vk_ctx()->validation) {
        const uint8_t *id = gfx_shader_input_id(shader);
        char name[65];
        for (int i = 0; i < 32; i++) snprintf(name + 2 * i, 3, "%02x", id[i]);
        if (!strcmp(target, name)) {
            ci.pNext = &validation;
            rt_log("GPU validation: instrumenting shader %s", name);
        }
    }
    VkResult r = vkCreateShaderModule(P.device, &ci, NULL, &m);''')])
