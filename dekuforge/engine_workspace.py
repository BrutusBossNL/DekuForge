"""Compose pinned engine source and original extensions in an owned build folder."""

import os
import hashlib
import re
from pathlib import Path
import shutil

from .core import ROOT


def write_if_changed(path, content):
    if isinstance(content, str) and path.is_file() and path.read_text(encoding="utf-8") == content:
        return
    payload = content.encode("utf-8") if isinstance(content, str) else content
    if not path.is_file() or path.read_bytes() != payload:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)


def stage_engine(root=ROOT):
    root = root.resolve()
    output = root / "build" / "engine-work"
    if output.resolve() != output:
        raise ValueError("Engine workspace must not be a link")
    marker = output / ".dekuforge-engine"
    if output.exists():
        if not marker.is_file():
            raise ValueError("Engine workspace is not owned by DekuForge")
        for directory, folders, files in os.walk(output, followlinks=False):
            for name in folders + files:
                path = Path(directory) / name
                if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
                    raise ValueError("Engine workspace contains a link")
    output.mkdir(parents=True, exist_ok=True)
    marker.touch()
    overridden = {"runtime/cpu.h", "runtime/loader.c", "runtime/boot.c", "runtime/romfs.c",
                  "tools/romfs_index.py", "recomp/lifter.py", "runtime/nvn_api_obj.c", "runtime/gfx_shader.c",
                  "runtime/nvn_api_core.c", "runtime/cfg.c", "runtime/svc.c", "runtime/kernel.c",
                  "runtime/ov_system.c", "runtime/ov_gfx.c", "runtime/main.c", "runtime/memory.c",
                  "runtime/nvn_procs.c", "runtime/nvn_procs.inc", "runtime/nvn_api_cmd.c",
                  "runtime/nvn_obj.h", "runtime/vk_exec.h", "runtime/vk_exec.c", "runtime/vk_exec_xfer.c",
                  "runtime/ipc.c", "runtime/audio_mixer.c", "runtime/fs_host.c", "runtime/audren.c", "runtime/audren.h",
                  "runtime/ov_input.c", "runtime/vk_exec_draw.c", "runtime/gfx_present.c",
                  "runtime/gfx_window_win.c", "runtime/gfx_window_sdl.c", "runtime/nx2navi.ico",
                  "runtime/vk_device.c", "runtime/ui_text.c", "runtime/vk_dump.c"}
    cached_shaders = {}
    for shader in (root / "engine" / "runtime" / "shaders").iterdir():
        if shader.suffix in (".comp", ".frag", ".vert"):
            digest = hashlib.sha256(shader.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            cached = root / "build" / "host-shaders" / digest / (shader.stem + "_spv.h")
            if cached.is_file() and f"// source sha256 {digest}" in cached.read_text(encoding="utf-8"):
                relative = "runtime/" + cached.name
                overridden.add(relative)
                cached_shaders[relative] = cached
    def ignore(directory, names):
        relative = Path(directory).relative_to(root / "engine")
        return [name for name in names if name in {"build", "generated", "refs", "toolchain", "__pycache__"}
                or (relative / name).as_posix() in overridden]
    shutil.copytree(root / "engine", output, dirs_exist_ok=True, ignore=ignore)
    write_if_changed(output / "runtime/nx2navi.ico", (root / "assets/branding/launcher.ico").read_bytes())
    for relative in ("runtime/gfx_window_win.c", "runtime/gfx_window_sdl.c", "runtime/vk_device.c", "runtime/ui_text.c"):
        branded = (root / "engine" / relative).read_text(encoding="utf-8")
        branded = branded.replace('"NX2navi Recomp', '"DekuForge').replace('L"NX2naviRecompWindow"', 'L"DekuForgeGameWindow"')
        if relative == "runtime/gfx_window_win.c":
            branded = branded.replace('#include <imm.h>', '#include <imm.h>\n#include <shobjidl.h>')
            branded = branded.replace('    HINSTANCE inst = GetModuleHandleW(NULL);',
                                      '    SetCurrentProcessExplicitAppUserModelID(L"DekuForge.Game");\n'
                                      '    HINSTANCE inst = GetModuleHandleW(NULL);')
            fullscreen = '            g_fs_pending = cfg_fullscreen();'
            if branded.count(fullscreen) != 1:
                raise ValueError("Fullscreen startup anchor changed")
            branded = branded.replace(fullscreen, fullscreen + '''
            // raise_window may already have delivered WM_ACTIVATEAPP before
            // the pending request was armed. Apply it now when we own focus.
            if (g_fs_pending && GetForegroundWindow() == g_hwnd) {
                g_fs_pending = 0;
                PostMessageW(g_hwnd, WM_APP_FULLSCREEN, 0, 0);
            }''')
        write_if_changed(output / relative, branded)
    for source, target in (("lifter.py", "recomp/lifter.py"), ("half_negate.h", "runtime/df_half_negate.h"),
                           ("windows_continuation.h", "runtime/df_windows_continuation.h"),
                           ("guest_continuation.c", "runtime/df_guest_continuation.c"),
                           ("constructor_flag.h", "runtime/df_constructor_flag.h"),
                           ("dot_product.h", "runtime/df_dot_product.h"), ("qarma.h", "runtime/df_qarma.h"),
                           ("pauth_profile.h", "runtime/df_pauth_profile.h"),
                           ("nvn2_control.h", "runtime/df_nvn2_control.h"),
                           ("nvn2_program.inc", "runtime/df_nvn2_program.inc"),
                           ("program_builder.inc", "runtime/df_program_builder.inc"),
                           ("command_extensions.inc", "runtime/df_command_extensions.inc"),
                           ("romfs_directory.inc", "runtime/df_romfs_directory.inc"),
                           ("display_extensions.inc", "runtime/df_display_extensions.inc"),
                           ("input_extensions.inc", "runtime/df_input_extensions.inc"),
                           ("network_extensions.inc", "runtime/df_network_extensions.inc"),
                           ("av1_movie.c", "runtime/df_av1_movie.c"),
                           ("compute_bank.inc", "runtime/df_compute_bank.inc"),
                           ("romfs_mounts.inc", "runtime/df_romfs_mounts.inc")):
        write_if_changed(output / target, (root / "engine_overrides" / source).read_bytes())
    cpu = output / "runtime" / "cpu.h"
    write_if_changed(cpu, (root / "engine" / "runtime" / "cpu.h").read_text(encoding="utf-8") + '\n#include "df_half_negate.h"\n#include "df_dot_product.h"\n'
                   '#include "df_qarma.h"\n#include "df_pauth_profile.h"\n')
    loader = output / "runtime" / "loader.c"
    content = (root / "engine" / "runtime" / "loader.c").read_text(encoding="utf-8")
    content, count = re.subn(r'static uint64_t decode_ctor_flag\(const Mod \*m\) \{.*?\n\}',
                            '''static uint64_t decode_ctor_flag(const Mod *m) {
    if (!m->pub.init || m->pub.init < m->pub.base) return 0;
    uint64_t offset = df_ctor_flag_offset((const uint8_t *)(uintptr_t)m->pub.base,
        m->pub.size, m->pub.data_off, m->pub.text_end, m->pub.init - m->pub.base);
    return offset ? m->pub.base + offset : 0;
}''', content, count=1, flags=re.DOTALL)
    if count != 1:
        raise ValueError("Constructor decoder no longer matches the pinned engine")
    write_if_changed(loader, '#include "df_constructor_flag.h"\n' + content)
    boot = output / "runtime" / "boot.c"
    content = (root / "engine" / "runtime" / "boot.c").read_text(encoding="utf-8")
    original = '#define expected_inits (RT_V143 ? inits_143 : RT_V110 ? inits_110 : inits_121)'
    if content.count(original) != 1:
        raise ValueError("Boot assertions no longer match the pinned engine")
    replacement = '''#if __has_include("df_boot_profile.h")
#include "df_boot_profile.h"
static const InitCount df_expected_inits[] = {DF_BOOT_INIT_ROWS};
#define expected_inits df_expected_inits
#else
''' + original + '\n#endif'
    content = content.replace(original, replacement)
    for label in ("CHECKPOINT", "NVN"):
        original_check = f"if (ret != main_mod->base + {label}_RET)"
        guard = (f"#if defined(DF_BOOT_{label}_RET_OK)\n"
                 f"        if (!DF_BOOT_{label}_RET_OK(ret - main_mod->base))\n"
                 "#else\n        " + original_check + "\n#endif")
        if content.count(original_check) != 1:
            raise ValueError("Boot checkpoint no longer matches the pinned engine")
        content = content.replace(original_check, guard)
    content = content.replace('    // nn::init::Start(main thread handle,',
                              '    if (getenv("DEKUFORGE_TRACE_GUEST")) g_fnprof = 1;\n'
                              '    // nn::init::Start(main thread handle,')
    write_if_changed(boot, content)
    program = (root / "engine" / "runtime" / "nvn_api_obj.c").read_text(encoding="utf-8")
    program = program.replace("// ---------- Programs", '#include "df_nvn2_control.h"\n#include "df_nvn2_program.inc"\n\n// ---------- Programs')
    program = program.replace("if (o->serial) gfx_backend()->program_release(o);",
                              "if (o->serial) gfx_backend()->program_release(o);\n    df_controls_free(o->serial);")
    program = program.replace('o->serial = nvn_new_serial();\n    NVN_LOG("ProgramSetShaders',
                              'o->serial = nvn_new_serial();\n    df_controls_bind(o);\n    NVN_LOG("ProgramSetShaders')
    program += '\n#include "df_program_builder.inc"\n'
    write_if_changed(output / "runtime" / "nvn_api_obj.c", program)
    shader = (root / "engine" / "runtime" / "gfx_shader.c").read_text(encoding="utf-8")
    shader = '#include "df_nvn2_control.h"\n' + shader
    shader = shader.replace('"nx2navi_xlate.exe"', '"DekuForgeShader.exe"').replace('"nx2navi_xlate.id"', '"DekuForgeShader.id"')
    shader = shader.replace('nx2navi_xlate" PLAT_EXE_SUFFIX', 'DekuForgeShader" PLAT_EXE_SUFFIX')
    shader = shader.replace("stage == GFX_STAGE_CS ? 0 : CODE_SKIP", "(stage == GFX_STAGE_CS || df_control_ampere(control)) ? 0 : CODE_SKIP")
    anchor = '    if (a) {\n        const char *sep = "";'
    if shader.count(anchor) != 1:
        raise ValueError("Shader request anchor differs from the pinned engine")
    shader = shader.replace(anchor, '    if (df_control_ampere(control)) o += sprintf(o, ",\\\"ampere\\\":true");\n' + anchor)
    write_if_changed(output / "runtime" / "gfx_shader.c", shader)
    core = (root / "engine" / "runtime" / "nvn_api_core.c").read_text(encoding="utf-8")
    core = core.replace("[0x00] = 55, [0x01] = 15,", "[0x00] = 231, [0x01] = 40,")
    core = core.replace('    if (w >= sizeof devinfo / sizeof *devinfo)',
                        '    if (w == 0x67) { *out = 256; return; } // Native shader storage alignment.\n'
                        '    if (w >= sizeof devinfo / sizeof *devinfo)')
    core = core.replace("// ---------- Queue", """
// A shared host submission queue already serializes primary and dependent queues.
// Retain the parent identity for API round trips and validate it at creation.
// Preserve the 64-byte builder ABI, including guest copies by value. Its four
// padding bytes carry an index into a synchronized host parent registry.
_Static_assert(offsetof(queue_builder_t, cmd_sz) == 16, "queue builder padding");
static PlatMutex df_parent_lock = PLAT_MUTEX_INIT;
static NVNqueue *df_parents[1024];
static unsigned df_parent_count;
static NVNqueue *df_primary(const void *b) {
    uint32_t index;
    memcpy(&index, (const char *)b + 12, 4);
    plat_mutex_lock(&df_parent_lock);
    NVNqueue *result = index && index <= df_parent_count ? df_parents[index - 1] : NULL;
    plat_mutex_unlock(&df_parent_lock);
    return result;
}
NVN_API(nvnQueueBuilderSetPrimaryQueue) {
    NVNqueue *parent = arg_p(c, 1);
    unsigned index = 0;
    plat_mutex_lock(&df_parent_lock);
    if (parent) {
        while (index < df_parent_count && df_parents[index] != parent) index++;
        if (index == df_parent_count) {
            if (df_parent_count == 1024) rt_fatal("Primary queue registry exhausted");
            df_parents[df_parent_count++] = parent;
        }
        index++;
    }
    plat_mutex_unlock(&df_parent_lock);
    uint32_t tag = index;
    memcpy((char *)arg_p(c, 0) + 12, &tag, 4);
}
NVN_API(nvnQueueBuilderGetPrimaryQueue) {
    ret_x(c, (uint64_t)(uintptr_t)df_primary(arg_p(c, 0)));
}
// ---------- Queue""", 1)
    core = core.replace("    queue_t *q = arg_p(c, 0);", """
    const queue_builder_t *builder = arg_p(c, 1);
    const queue_t *parent = (const queue_t *)df_primary(builder);
    if (parent) {
        if (parent->magic != QUEUE_MAGIC || parent->dev != builder->dev) {
            ret_x(c, 0);
            return;
        }
    }
    queue_t *q = arg_p(c, 0);""", 1)
    core += """
NVN_API(nvnQueueWaitSync) {
    const sync_t *sync = arg_p(c, 1);
    if (!sync || !sync->fenced) { ret_x(c, 0); return; }
    // All host queues feed one ordered backend stream. The sync's earlier
    // submissions already precede subsequent submissions on this queue.
    ret_x(c, 1);
}
"""
    write_if_changed(output / "runtime" / "nvn_api_core.c", core)
    commands = (root / "engine/runtime/nvn_api_cmd.c").read_text(encoding="utf-8")
    commands = commands.replace('"DISPATCH_IND", "CLEAR_BUF",', '"DISPATCH_IND", "CLEAR_BUF", "IMAGE_STRIDE", "COMPUTE_CONSTANTS",')
    write_if_changed(output / "runtime/nvn_api_cmd.c", commands + '\n#include "df_command_extensions.inc"\n')
    obj = (root / "engine/runtime/nvn_obj.h").read_text(encoding="utf-8")
    obj = obj.replace("OP_CLEAR_BUF, OP_COUNT_", "OP_CLEAR_BUF, OP_DF_IMAGE_STRIDE, OP_DF_CONSTANTS, OP_COUNT_")
    obj += '\ntypedef struct { uint32_t slot, offset, size; uint8_t bytes[]; } p_df_constants;\n'
    write_if_changed(output / "runtime/nvn_obj.h", obj)
    execute_header = (root / "engine/runtime/vk_exec.h").read_text(encoding="utf-8")
    execute_header += "\nint df_resource_slot(const VkExec *ex, int stage, int kind, const GfxShaderRes *resource);\n"
    write_if_changed(output / "runtime/vk_exec.h", execute_header.replace("int64_t copy_stride;", "uint8_t df_compute_constants[1024];\n    int64_t copy_image_stride;\n    int64_t copy_stride;"))
    execute = (root / "engine/runtime/vk_exec.c").read_text(encoding="utf-8")
    execute = execute.replace("case OP_COPY_STRIDE:", "case OP_DF_IMAGE_STRIDE: ex->copy_image_stride = ((const p_copy_stride *)a)->stride; break;\n        case OP_COPY_STRIDE:")
    execute = execute.replace("case OP_BIND_UBO: case OP_BIND_SSBO:", "case OP_DF_CONSTANTS: case OP_BIND_UBO: case OP_BIND_SSBO:")
    write_if_changed(output / "runtime/vk_exec.c", execute)
    draw = '#include "df_nvn2_control.h"\n' + (root / "engine/runtime/vk_exec_draw.c").read_text(encoding="utf-8")
    draw = draw.replace("static VkDescriptorBufferInfo c0_info(VkExec *ex, int st) {", """#include "df_compute_bank.inc"
static VkDescriptorBufferInfo c0_info(VkExec *ex, int st) {
    uint8_t native_bank[VK_C0_BYTES];
    if (df_compute_bank(ex, st, native_bank, sizeof native_bank)) {
        VkBuffer buffer; VkDeviceSize offset;
        memcpy(scratch(ex, sizeof native_bank, &buffer, &offset), native_bank, sizeof native_bank);
        // Indirect dispatch copies GPU-produced dimensions into this exact
        // allocation after binding. Publish it just as the legacy path does.
        if (st == NVN_STAGE_CS) {
            B.c0_buf[2] = buffer;
            B.c0_off[2] = offset;
            B.c0_valid[2] = 1;
        }
        RS.volatile_ = 1;
        return (VkDescriptorBufferInfo){buffer, offset, sizeof native_bank};
    }""")
    draw = draw.replace("    if (slot >= 0 && slot < 16) b = ubo ?", """    uint8_t native_bank[VK_C0_BYTES];
    if (r->cbuf_slot == 0 && df_compute_bank(ex, st, native_bank, sizeof native_bank)) {
        size_t at = (size_t)r->handle * 4;
        if (at + 12 > sizeof native_bank) rt_fatal("Compute pointer outside constant bank");
        uint32_t size;
        memcpy(&up.addr, native_bank + at, 8); memcpy(&size, native_bank + at + 8, 4);
        up.size = size < (1u << 30) ? size : 0;
        b = &up; RS.volatile_ = 1;
    }
    else if (slot >= 0 && slot < 16) b = ubo ?""")
    draw = draw.replace("    case OP_BIND_UBO: {", """    case OP_DF_CONSTANTS: {
        const p_df_constants *p = payload;
        if (p->slot != 0 || p->offset > 1024 || p->size > 1024 - p->offset)
            rt_fatal("Corrupt compute constants command");
        uint8_t *bytes = ex->df_compute_constants;
        memcpy(bytes + p->offset, p->bytes, p->size);
        bind_gen++;
        break;
    }
    case OP_BIND_UBO: {""")
    draw = draw.replace("int slot = r->slot + (int)k;", "int slot = df_resource_slot(ex, st, b->kind, r) + (int)k;")
    write_if_changed(output / "runtime/vk_exec_draw.c", draw)
    dump = (root / "engine/runtime/vk_dump.c").read_text(encoding="utf-8")
    dump = dump.replace("int slot = r->slot + (int)k;",
                        "int slot = df_resource_slot(ex, st, bd->kind, r) + (int)k;")
    dump = dump.replace("uint64_t h = handle_of(ex, 5, bd->res->slot, 1);",
                        "int slot = df_resource_slot(ex, 5, bd->kind, bd->res);\n"
                        "        uint64_t h = handle_of(ex, 5, slot, 1);")
    dump = dump.replace('n, bd->res->slot, w, hh', 'n, slot, w, hh')
    dump = dump.replace('bd->res->slot, lv, layer,', 'slot, lv, layer,')
    write_if_changed(output / "runtime/vk_dump.c", dump)
    present = (root / "engine/runtime/gfx_present.c").read_text(encoding="utf-8")
    present = present.replace("    int cap = (g_capture || menu_shot)", """    static int df_test_captured;
    const char *df_test_path = getenv("DEKUFORGE_TEST_SCREEN");
    const char *df_test_frame = getenv("DEKUFORGE_TEST_SCREEN_FRAME");
    if (!df_test_captured && df_test_path && df_test_frame &&
        gfx_counters.frames >= strtoull(df_test_frame, NULL, 10)) {
        menu_shot = df_test_path;
        df_test_captured = 1;
    }
    int cap = (g_capture || menu_shot)""")
    write_if_changed(output / "runtime/gfx_present.c", present)
    transfer = (root / "engine/runtime/vk_exec_xfer.c").read_text(encoding="utf-8")
    transfer = transfer.replace("uint64_t img = row * hb;", """uint64_t img = ex->copy_image_stride ? (uint64_t)ex->copy_image_stride : row * hb;
    if (img < row * hb || img % row || img / row > UINT32_MAX / (uint32_t)s->bh)
        rt_fatal("Texture slice stride cannot be represented by Vulkan");""")
    transfer = transfer.replace(".bufferImageHeight = hb * (uint32_t)s->bh", ".bufferImageHeight = (uint32_t)(img / row) * (uint32_t)s->bh")
    write_if_changed(output / "runtime/vk_exec_xfer.c", transfer)
    proc_list = (root / "engine/runtime/nvn_procs.inc").read_text(encoding="utf-8")
    proc_list += "\nNVN_PROC(nvnQueueBuilderSetPrimaryQueue)\nNVN_PROC(nvnQueueBuilderGetPrimaryQueue)\n"
    for name in re.findall(r"NVN_API\((nvn\w+)\)", (root / "engine_overrides/program_builder.inc").read_text()):
        proc_list += f"NVN_PROC({name})\n"
    for name in re.findall(r"NVN_API\((nvn\w+)\)", (root / "engine_overrides/command_extensions.inc").read_text()):
        if f"NVN_PROC({name})" not in proc_list:
            proc_list += f"NVN_PROC({name})\n"
    write_if_changed(output / "runtime/nvn_procs.inc", proc_list)
    config = (root / "engine" / "runtime" / "cfg.c").read_text(encoding="utf-8")
    if config.count("#define PREFIX_LEN 5") != 1:
        raise ValueError("Settings prefix no longer matches the pinned engine")
    config = config.replace("#define PREFIX_LEN 5", "#define PREFIX_LEN (sizeof(PREFIX) - 1)")
    # Ordinary launches use the modes exercised by the isolated renderer tests;
    # raw-pointer writes currently need coherent pools.
    for old, new in (
        ('{"MEMORY", "auto",', '{"MEMORY", "import",'),
        ('{"PIPE_WAIT", "default",', '{"PIPE_WAIT", "draw",'),
        ('{"PIPE_SKIP", "fullscreen",', '{"PIPE_SKIP", "strict",'),
        ('{"GPL", "1",', '{"GPL", "0",'),
    ):
        if old not in config:
            raise ValueError(f"Renderer default anchor missing: {old}")
        config = config.replace(old, new)
    write_if_changed(output / "runtime" / "cfg.c", config)
    svc = (root / "engine" / "runtime" / "svc.c").read_text(encoding="utf-8")
    svc = '#include "df_boot_profile.h"\n' + svc.replace("#define PROGRAM_ID 0x0100f2c0115b6000ull", "#define PROGRAM_ID DF_APPLICATION_ID")
    svc = svc.replace("case 0: v = 7; break;", "case 0: v = 0x3f; break;")
    anchor = "    case 23: v = 1; break;"
    if svc.count(anchor) != 1:
        raise ValueError("Unexpected GetInfo implementation")
    svc = svc.replace(anchor, anchor + """
    // The host GPU backend uses no guest remote-memory region.
    case 29: case 30: case 31: case 32: v = 0; break;
    // SDK RELRO protection requires the actual guest page granularity.
    case 33: v = 0x1000; break;
""")
    write_if_changed(output / "runtime" / "svc.c", svc)
    ipc = (root / "engine/runtime/ipc.c").read_text(encoding="utf-8")
    ipc = ipc.replace("// Services sm: hands out.", """// Newer SDKs acquire the renderer manager through the audio user service.
static void df_audio_user(IpcSession *session, const IpcRequest *request, IpcResponse *response) {
    if (request->cmd != 2) { ipc_unimplemented(session, request); return; }
    response->move[response->nmove++] = ipc_session_new("IAudioRendererManager", audren_manager_handler, NULL, NULL);
    response->result = 0;
}
// Services sm: hands out.""")
    ipc = ipc.replace('{"audren:u", audren_manager_handler},', '{"audren:u", audren_manager_handler},\n    {"aud:u", df_audio_user},')
    write_if_changed(output / "runtime/ipc.c", ipc)
    audio = (root / "engine/runtime/audio_mixer.c").read_text(encoding="utf-8")
    audio = audio.replace("void audio_device_handler(IpcSession *s, const IpcRequest *rq, IpcResponse *rs) {",
                          "void audio_device_handler(IpcSession *s, const IpcRequest *rq, IpcResponse *rs) {\n    static _Atomic uint8_t df_auto_volume;")
    # The fixed virtual audio device uses the existing shared notification event;
    # callers own and close their returned handles. Release unregisters no host
    # callback because this backend never changes its virtual device identity.
    audio = audio.replace("case 4: case 11: case 12:", "case 15: case 17: case 4: case 11: case 12:")
    audio = audio.replace("    case 5: { int32_t n = output_channels();", "    case 16: case 18: return;\n    case 5: { int32_t n = output_channels();")
    audio = audio.replace('    case 5: { int32_t n = output_channels();', '''    // Auto tuning selects console-device gain calibration. The desktop virtual
    // device has unity calibration in either mode; keep the requested mode for
    // consistent readback without changing the user's Windows volume.
    case 19:
        atomic_store(&df_auto_volume, IPC_ARG(rq, uint8_t, 0) != 0);
        return;
    case 20: case 21: {
        uint8_t enabled = rq->cmd == 20 ? atomic_load(&df_auto_volume) : 0;
        IPC_OUT(rs, enabled);
        return;
    }
    case 5: { int32_t n = output_channels();''')
    write_if_changed(output / "runtime/audio_mixer.c", audio)
    renderer_header = (root / "engine/runtime/audren.h").read_text(encoding="utf-8")
    renderer_header = renderer_header.replace("    int logged;", "    float df_voice_drop;\n    int logged;")
    write_if_changed(output / "runtime/audren.h", renderer_header)
    renderer = (root / "engine/runtime/audren.c").read_text(encoding="utf-8")
    renderer = renderer.replace("    r->revision = p->revision;", "    r->revision = p->revision;\n    r->df_voice_drop = 1.0f;")
    renderer = renderer.replace("    case 7: rs->copy", """    // Voice-drop weighting is retained per renderer. The host mixes all active
    // voices instead of dropping voices to fit a console DSP time budget.
    case 12: {
        float value = IPC_ARG(rq, float, 0);
        if (!(value >= 0.0f && value <= 1.0f)) { rs->result = 0xe402; return; }
        plat_mutex_lock(&r->lock);
        r->df_voice_drop = value;
        plat_mutex_unlock(&r->lock);
        return;
    }
    case 13: {
        plat_mutex_lock(&r->lock);
        float value = r->df_voice_drop;
        plat_mutex_unlock(&r->lock);
        IPC_OUT(rs, value);
        return;
    }
    case 7: rs->copy""")
    write_if_changed(output / "runtime/audren.c", renderer)
    filesystem = (root / "engine/runtime/fs_host.c").read_text(encoding="utf-8")
    filesystem = '#include "df_boot_profile.h"\n' + filesystem.replace("#define NX2NAVI_APPLICATION_ID 0x0100f2c0115b6000ull", "#define NX2NAVI_APPLICATION_ID DF_APPLICATION_ID")
    filesystem = filesystem.replace("static uint32_t open_directory(", '#include "df_romfs_directory.inc"\n\nstatic uint32_t open_directory(')
    filesystem = filesystem.replace('if (romfs_owns(path)) rt_fatal("fs: OpenDirectory on the RomFS (%s) is not implemented", path);',
                                    'if (romfs_owns(path)) return df_open_romfs_directory(out, path, mode);')
    write_if_changed(output / "runtime/fs_host.c", filesystem)
    kernel = (root / "engine" / "runtime" / "kernel.c").read_text(encoding="utf-8")
    # The guest creates workers pinned to core 5; all scheduler arrays use NCORE.
    if kernel.count("#define NCORE 3") != 1:
        raise ValueError("Unexpected virtual-core configuration")
    kernel = kernel.replace("#define NCORE 3", "#define NCORE 6")
    kernel = kernel.replace("static _Thread_local RtThread *tcur;", """static _Thread_local RtThread *tcur;
// A resumed fiber can belong to a different OS thread. Never retain a TLS
// address across the host context switch.
__attribute__((noinline)) static RtThread *df_current_thread(void) { return tcur; }""")
    fiber_start = kernel.index("// ---- fibers\n")
    fibers = kernel[fiber_start:]
    fibers = re.sub(r"\btcur\b", "df_current_thread()", fibers)
    fibers = fibers.replace("    t->host_depth = depth;\n    fiber_resumed();",
                            "    df_current_thread()->host_depth = depth;\n    fiber_resumed();")
    fibers = fibers.replace('    Fiber *to = fiber_find(c->x[0]);', '''    if (c->x[0] == 0) {
        if (t->fiber) fiber_switch_to(t, c, NULL);
        return;
    }
    Fiber *to = fiber_find(c->x[0]);''')
    kernel = kernel[:fiber_start] + fibers
    begin = kernel.index("    case 0x34:")
    end = kernel.index("    case 0x35:", begin)
    wait_address = kernel[begin:end]
    wait_address = wait_address.replace("if (type < 0 || type > 2)", "if (type < 0 || type > 3)")
    wait_address = wait_address.replace("        lock();", """        if (addr & (type == 3 ? 7u : 3u)) {
            x[0] = 0xcc01u; // Horizon InvalidAddress
            return 1;
        }
        lock();""", 1)
    wait_address = wait_address.replace("int ok = type == 2 ? (int32_t)v == val : (int32_t)v < val;",
        "int ok = type == 3 ? __atomic_load_n((const uint64_t *)(uintptr_t)addr, __ATOMIC_SEQ_CST) == x[2] :\n"
        "                 type == 2 ? (int32_t)v == val : (int32_t)v < val;")
    kernel = kernel[:begin] + wait_address + kernel[end:]
    anchor = "    t->handle = h_new(O_THREAD, t);"
    if kernel.count(anchor) != 1:
        raise ValueError("Unexpected thread handle initialization")
    kernel = kernel.replace(anchor, anchor + """
    // The current guest SDK reads its mutex owner tag directly from TLR+0x110.
    // Publish the allocated handle before this thread can execute guest code.
    st32((uint64_t)(uintptr_t)t->tlr + 0x110, t->handle);
""")
    write_if_changed(output / "runtime" / "kernel.c", kernel)
    memory = (root / "engine" / "runtime" / "memory.c").read_text(encoding="utf-8")
    # The current platform's resource heaps exceed the old 3.2 GiB budget.
    # Reserve address space separately from physical pages committed on demand.
    for before, after in (
        ("#define LOW_SIZE (6 * GiB)", "#define LOW_SIZE (HEAP_OFF + HEAP_CAP)"),
        ("#define HEAP_CAP (4 * GiB)", "#define HEAP_CAP (10 * GiB)"),
        ("#define DEFAULT_POOL 0xCD500000ull", "#define DEFAULT_POOL (10 * GiB)"),
        ('"a 6 GiB stack and heap block below 2^39"', '"the configured stack and heap block below 2^39"'),
    ):
        if memory.count(before) != 1:
            raise ValueError("Unexpected guest memory layout")
        memory = memory.replace(before, after)
    write_if_changed(output / "runtime" / "memory.c", memory)
    procs = (root / "engine" / "runtime" / "nvn_procs.c").read_text(encoding="utf-8")
    procs = procs.replace("    if (p) return p->addr;", """
    if (getenv("DEKUFORGE_TRACE_NVNP")) {
        Cpu *c = kern_cpu();
        rt_log("df proc %s caller %#llx", name, (unsigned long long)(c ? c->x[30] : 0));
    }
    if (p) return p->addr;
""")
    write_if_changed(output / "runtime" / "nvn_procs.c", procs)
    system = (root / "engine" / "runtime" / "ov_system.c").read_text(encoding="utf-8")
    system += """
// Desktop graphics scaling has no applet service or asynchronous scale events.
// Keep the requested subscription independently from performance notifications.
static volatile int32_t df_notify_graphics_scale;
static void df_graphics_scale_enabled(Cpu *c) {
    plat_xchg32(&df_notify_graphics_scale, (int32_t)(arg_x(c, 0) & 0xff));
}
HOST_OVERRIDE("_ZN2nn2oe42SetGraphicsScaleChangedNotificationEnabledEb", df_graphics_scale_enabled);
// Fixed desktop scale: the SDK's middle graphics-scale enum value.
static void df_current_graphics_scale(Cpu *c) { ret_x(c, 1); }
HOST_OVERRIDE("_ZN2nn2oe23GetCurrentGraphicsScaleEv", df_current_graphics_scale);
// The independent package mounts no add-on-content archives.
static void df_count_add_on_content(Cpu *c) { ret_x(c, 0); }
HOST_OVERRIDE("_ZN2nn3aoc17CountAddOnContentEv", df_count_add_on_content);
// SDK clock_gettime uses these entry points after selecting nn::time clocks.
// Return the ARM64 timespec ABI explicitly, without invoking uninitialized
// guest time-service clients beneath our host time-service implementation.
static void df_timespec(Cpu *c, uint64_t nanoseconds) {
    if (!arg_p(c, 0)) { ret_x(c, TIME_R_INVALID); return; }
    int64_t fields[2] = {(int64_t)(nanoseconds / 1000000000ull),
                         (int64_t)(nanoseconds % 1000000000ull)};
    memcpy(arg_p(c, 0), fields, sizeof fields);
    ret_x(c, 0);
}
static void df_monotonic_timespec(Cpu *c) { df_timespec(c, plat_now_ns()); }
static void df_realtime_timespec(Cpu *c) { df_timespec(c, plat_unix_time_ns()); }
HOST_OVERRIDE("_ZN2nn4time37GetStandardSteadyClockCurrentTimespecEP8timespec", df_monotonic_timespec);
HOST_OVERRIDE("_ZN2nn4time41GetStandardUserSystemClockCurrentTimespecEP8timespec", df_realtime_timespec);
// This host exposes playback only; no microphone capture devices are enabled.
static void df_list_audio_inputs(Cpu *c) { ret_x(c, 0); }
HOST_OVERRIDE("_ZN2nn5audio6detail23ListVirtualInputDevicesEPNS0_15AudioDeviceNameEi", df_list_audio_inputs);
static void df_display_version(Cpu *c) {
    char *version = arg_p(c, 0);
    if (!version) rt_fatal("Null display-version output");
    memset(version, 0, 16);
    snprintf(version, 16, "%d.%d.%d", rt_game_version / 100, rt_game_version / 10 % 10, rt_game_version % 10);
}
HOST_OVERRIDE("_ZN2nn2oe17GetDisplayVersionEPNS0_14DisplayVersionE", df_display_version);
// No console network session is available in this offline host. Initialization
// and cancellation need no resources; availability is false and connection
// failures use the SDK's NetworkCommunicationDisabled result.
static void df_network_local(Cpu *c) { ret_x(c, 0); }
static void df_network_disabled(Cpu *c) { ret_x(c, (1111u << 9) | 110u); }
HOST_OVERRIDE("_ZN2nn4nifm10InitializeEv", df_network_local);
HOST_OVERRIDE("_ZN2nn4nifm18IsNetworkAvailableEv", df_network_local);
HOST_OVERRIDE("_ZN2nn4nifm27SubmitNetworkRequestAndWaitEv", df_network_local);
HOST_OVERRIDE("_ZN2nn4nifm20CancelNetworkRequestEv", df_network_local);
HOST_OVERRIDE("_ZN2nn4nifm31HandleNetworkRequestErrorResultEv", df_network_disabled);
HOST_OVERRIDE("_ZN2nn4nifm22GetCurrentProxySettingEPNS0_12ProxySettingE", df_network_disabled);
"""
    # Newer SDKs call Send on the implementation object instead of Save on the
    # public wrapper. Preserve the same local-only play-report behavior.
    system += '\nHOST_OVERRIDE("_ZN2nn5prepo6detail14PlayReportImpl4SendERKNS_7account3UidE", ov_report_save);\n'
    system += 'HOST_OVERRIDE("_ZN2nn5prepo6detail14PlayReportImpl4SendEv", ov_report_save);\n'
    system += '''
// Local play reports complete immediately. The SDK's async wrapper still needs
// a real, signalled system event so normal waits and destruction remain valid.
static void df_report_completion(Cpu *c) {
    uint64_t event = arg_x(c, 1);
    if (!event) rt_fatal("prepo completion event is null");
    kern_bind_system_event(c, event, 0);
    kern_signal_system_event(event);
    ret_x(c, 0);
}
HOST_OVERRIDE("_ZN2nn5prepo12AsyncContext18GetCompletionEventEPNS_2os11SystemEventE", df_report_completion);
'''
    write_if_changed(output / "runtime" / "ov_system.c", system + '\n#include "df_network_extensions.inc"\n')
    graphics = (root / "engine" / "runtime" / "ov_gfx.c").read_text(encoding="utf-8")
    anchor = '    if (!mem || !size) rt_fatal("nv::InitializeGraphics:'
    if graphics.count(anchor) != 1:
        raise ValueError("Unexpected graphics initialization")
    graphics = graphics.replace(anchor, '''    // NVN2 may supply allocator callbacks instead of a fixed work arena.
    int callback_arena = !mem && !size && nv.graphics.alloc && nv.graphics.free;
    if ((!mem || !size) && !callback_arena) rt_fatal("nv::InitializeGraphics:''')
    write_if_changed(output / "runtime" / "ov_gfx.c", graphics + '\n#include "df_display_extensions.inc"\n')
    controls = (root / "engine/runtime/ov_input.c").read_text(encoding="utf-8")
    write_if_changed(output / "runtime/ov_input.c", controls + '\n#include "df_input_extensions.inc"\n')
    main = (root / "engine" / "runtime" / "main.c").read_text(encoding="utf-8")
    anchor = "void fnprof_hit(uint64_t addr, uint64_t lr, uint64_t x0) { (void)lr, res_fn_hit(addr, x0); }"
    if main.count(anchor) != 1:
        raise ValueError("Unexpected function trace hook")
    main = main.replace(anchor, """
// Optional local diagnosis: addresses stay in the environment, never in source.
void fnprof_hit(uint64_t addr, uint64_t lr, uint64_t x0) {
    static uint64_t selected[16];
    static int initialized, count;
    if (!initialized) {
        const char *p = getenv("DEKUFORGE_TRACE_GUEST");
        while (p && *p && count < 16) {
            char *end;
            uint64_t value = strtoull(p, &end, 0);
            if (p == end) break;
            selected[count++] = value;
            p = *end == ',' ? end + 1 : end;
        }
        initialized = 1;
    }
    for (int i = 0; i < count; i++) if (addr == selected[i]) {
        Cpu *c = kern_cpu();
        if (c) rt_log("df guest %#llx lr %#llx x0 %#llx x1 %#llx x2 %#llx x3 %#llx",
            (unsigned long long)addr, (unsigned long long)lr, (unsigned long long)x0,
            (unsigned long long)c->x[1], (unsigned long long)c->x[2], (unsigned long long)c->x[3]);
        if (plat_mem_readable(x0, 24)) {
            uint64_t table = LD64(x0 + 16);
            if (plat_mem_readable(table, 64)) rt_log("df indirect object %#llx table %#llx slot38 %#llx",
                (unsigned long long)x0, (unsigned long long)table, (unsigned long long)LD64(table + 56));
        }
        if (plat_mem_readable(x0, 40)) {
            uint64_t table = LD64(x0 + 24);
            if (plat_mem_readable(table, 40)) rt_log("df wait object %#llx table %#llx target %#llx context %#llx",
                (unsigned long long)x0, (unsigned long long)table, (unsigned long long)LD64(table + 32),
                (unsigned long long)LD64(x0 + 32));
        }
    }
    res_fn_hit(addr, x0);
}
""")
    write_if_changed(output / "runtime" / "main.c", main)
    replacements = {
        "runtime/romfs.c": ('"NX2NAVIRFS1", 8', '"DFROMFS1", 8'),
        "tools/romfs_index.py": ("MAGIC = b'NX2NAVIRFS1'", "MAGIC = b'DFROMFS1'"),
    }
    for relative, (original, replacement) in replacements.items():
        path = output / relative
        text = (root / "engine" / relative).read_text(encoding="utf-8")
        if text.count(original) != 1:
            raise ValueError("Engine format extension no longer matches its pinned source")
        text = text.replace(original, replacement)
        if relative == "runtime/romfs.c":
            text = text.replace("static char mount_name[32];", "")
            text = re.sub(r"int romfs_owns\(const char \*path\) \{.*?\n\}", '#include "df_romfs_mounts.inc"', text, count=1, flags=re.DOTALL)
            text = re.sub(r"uint32_t romfs_mount\(const char \*name\) \{.*?\n\}", "", text, count=1, flags=re.DOTALL)
            text = text.replace("romfs_path_relative(mount_name, path)", "df_romfs_relative(path)")
            text += '\nHOST_OVERRIDE("_ZN2nn2fs8MountRomEPKc", ov_mount_rom);\n'
        if relative == "tools/romfs_index.py":
            text = text.replace("manifest.get('status') != 'pass'", "manifest.get('status') not in ('pass', 'ok')")
        write_if_changed(path, text)
    for relative, cached in cached_shaders.items():
        write_if_changed(output / relative, cached.read_bytes())
    from .mesh_workspace import stage_mesh
    stage_mesh(output, write_if_changed)
    return output
