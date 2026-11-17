"""Compose the versioned DekuForge UI and owned cheats over the verified engine."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from .core import ROOT
from . import COMPONENTS

ENGINE_VERSION = COMPONENTS["engine"]["version"]
BUILD_KIT_VERSION = COMPONENTS["buildkit"]["version"]
OWNED_CHEATS_REVISION = "8cb3f1c6c168fd36ff2dc08ecdd606508af10f9a"
LAYER = ROOT / "engine_overrides/dekuforge_0110"

# These changes observe guest state or draw the host UI; they do not translate shaders.
CPU_EXTENSION_FILES = {
    "runtime/cfg.c", "runtime/cheats.c", "runtime/cheats.h", "runtime/host.h",
    "runtime/main.c", "runtime/ov_probe.c", "runtime/patches.c", "runtime/resolution.c",
    "runtime/romfs.c", "runtime/ui_text.c", "runtime/ui_text.h", "runtime/world_map.c", "runtime/world_map.h",
}


def gpu_input_signature(source, names=None):
    if names is None:
        from .stable_engine import source_manifest
        names=source_manifest()
    digest=hashlib.sha256(b"DekuForge GPU inputs v1\0")
    for name in sorted(names):
        if name.startswith("runtime/ui/") or name in CPU_EXTENSION_FILES:
            continue
        if not name.startswith(("runtime/","tools/xlate/","tools/vendor/")):
            continue
        data=(source/name).read_bytes()
        if name=="runtime/vk_dlaa.c":
            text=data.decode("utf-8").replace('#include "bomb_arrows.h"\n',"")
            start=text.find("    if(bomb_arrows_camera_needed()")
            if start>=0:
                end=text.index("    if (!inputs_on()",start)
                text=text[:start]+text[end:]
            data=text.encode("utf-8")
        digest.update(name.encode()+b"\0"+hashlib.sha256(data).digest())
    return digest.hexdigest()


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("The pinned UI composition context changed: " + old[:70])
    return text.replace(old,new,1)


def layer_identity():
    digest=hashlib.sha256(Path(__file__).read_bytes())
    for path in sorted(LAYER.iterdir()):
        if path.is_file():
            digest.update(path.name.encode()+b"\0"+path.read_bytes())
    digest.update((ROOT/"assets/branding/logo.png").read_bytes())
    return digest.hexdigest()


def compose(source):
    source=Path(source)
    if source.resolve()!=source or not (source/".dekuforge-stable-engine").is_file():
        raise ValueError("Compose only into the owned stable source workspace")
    patch=(LAYER/"cheat_manager.patch").read_text(encoding="utf-8")
    # New files belong to this reproducible layer; the base export resets the existing files.
    for name in re.findall(r"new file mode \d+\nindex [^\n]+\n--- /dev/null\n\+\+\+ b/([^\n]+)",patch):
        target=source/name
        if not target.resolve().is_relative_to(source.resolve()):
            raise ValueError("Unsafe extension path")
        target.unlink(missing_ok=True)
    for check in (["--check"],[]):
        subprocess.run(["git","apply",*check,"--whitespace=nowarn","--directory",source.relative_to(ROOT).as_posix(),
                        str(LAYER/"cheat_manager.patch")],cwd=ROOT,check=True,capture_output=True)
    for name in ("menu_skin.cpp","menu_skin.h"):
        shutil.copy2(LAYER/name,source/"runtime/ui"/name)
    from PIL import Image
    with Image.open(ROOT/"assets/branding/logo.png") as logo:
        logo=logo.convert("RGBA");logo.thumbnail((240,120),Image.Resampling.LANCZOS)
        pixels=logo.tobytes();width,height=logo.size
    header=f"// Generated from the project's own branding.\n#define DEKU_BRAND_W {width}\n#define DEKU_BRAND_H {height}\nstatic const unsigned char deku_brand_rgba[]={{\n"
    header+="\n".join(",".join(str(b) for b in pixels[i:i+64])+"," for i in range(0,len(pixels),64))+"\n};\n"
    (source/"runtime/ui/deku_brand_pixels.h").write_text(header,encoding="ascii")
    menu=source/"runtime/ui/menu.cpp"
    text=menu.read_text(encoding="utf-8")
    # The interface uses its bundled open-source typeface, not the game's menu faces.
    start=text.index("    g_game_font = menu_asset_font(")
    end=text.index("\n}",start)
    text=text[:start]+"    rt_log(\"DekuForge UI: bundled Roboto and project branding\");"+text[end:]
    text=text.replace("IM_COL32(10, 6, 2, 150)","IM_COL32(3, 12, 7, 150)")
    start=text.index("    ImTextureID frame_tex;",text.index("static void layout_menu"))
    end=text.index("    if (g_title_font) ImGui::PushFont",start)
    text=text[:start]+'''    ImGui::Begin("##menu",nullptr,ImGuiWindowFlags_NoDecoration|ImGuiWindowFlags_NoMove|ImGuiWindowFlags_NoSavedSettings);
    const ImVec2 win_p=ImGui::GetWindowPos(),win_s=ImGui::GetWindowSize();
    skin_panel(ImGui::GetWindowDrawList(),win_p,ImVec2(win_p.x+win_s.x,win_p.y+win_s.y),scale);
'''+text[end:]
    start=text.index('    {   // the Triforce, then "Ocarina of Time"')
    end=text.index("    const float title_end",start)
    text=text[:start]+'''    {
        ImVec2 at=ImGui::GetCursorScreenPos();
        skin_brand(ImGui::GetWindowDrawList(),at,184*scale);
        ImGui::SetCursorScreenPos(ImVec2(at.x+210*scale,at.y+18*scale));
        ImGui::TextColored(ImVec4(.72f,.85f,.49f,1),"%s",menu_text(UI_MENU_TITLE));
        ImGui::SetCursorScreenPos(ImVec2(at.x+210*scale,at.y+49*scale));
        ImGui::TextDisabled("Reforging a legend.");
        ImGui::SetCursorScreenPos(at);
        ImGui::Dummy(ImVec2(500*scale,94*scale));
    }
'''+text[end:]
    start=text.index('        menu_art_draw(ImGui::GetWindowDrawList(), MENU_ART_GUIDE_BAR')
    end=text.index(';',start)+1
    text=text[:start]+'''        ImGui::GetWindowDrawList()->AddLine(ImVec2(win_p.x+st.WindowPadding.x,sy-8*scale),
            ImVec2(win_p.x+win_s.x-st.WindowPadding.x,sy-8*scale),IM_COL32(55,87,59,160),scale);'''+text[end:]
    start=text.index("static void perf_draw(")
    end=text.index("\n// The note after F8",start)
    text=text[:start]+'''static void perf_draw(const MenuTarget *t,float scale) {
    if(g_perf_mode==2) return perf_full_draw(t,scale);
    if(!g_perf_mode||!g_perf_text[0]) return;
    ImDrawList *dl=g_open.load(std::memory_order_relaxed)?ImGui::GetBackgroundDrawList():ImGui::GetForegroundDrawList();
    float width=fmaxf(178*scale,ImGui::CalcTextSize(g_perf_text).x+34*scale),height=76*scale;
    ImVec2 at(t->width-width-18*scale,18*scale);
    skin_panel(dl,at,ImVec2(at.x+width,at.y+height),scale,.94f);
    dl->AddCircleFilled(ImVec2(at.x+16*scale,at.y+17*scale),3*scale,IM_COL32(172,218,105,255));
    dl->AddText(ImGui::GetFont(),13*scale,ImVec2(at.x+28*scale,at.y+10*scale),SKIN_TEXT_DIM,"DEKUFORGE");
    dl->AddText(ImGui::GetFont(),28*scale,ImVec2(at.x+16*scale,at.y+33*scale),SKIN_TEXT,g_perf_text);
}
'''+text[end:]
    text=text.replace('"NX2navi %s','"DekuForge %s')
    menu.write_text(text,encoding="utf-8")
    panel=source/"runtime/ui/perf_panel.cpp"
    text=panel.read_text(encoding="utf-8").replace("236 / 255.0f, 196 / 255.0f, 104 / 255.0f","178 / 255.0f, 216 / 255.0f, 128 / 255.0f")
    text=text.replace("244 / 255.0f, 236 / 255.0f, 214 / 255.0f","231 / 255.0f, 242 / 255.0f, 225 / 255.0f")
    text=text.replace("170 / 255.0f, 152 / 255.0f, 120 / 255.0f","139 / 255.0f, 169 / 255.0f, 145 / 255.0f")
    text=text.replace('    ImGui::TextColored(kDimText, "%s", p->version);','    ImGui::TextColored(kLabel, "DEKUFORGE");\n    ImGui::TextColored(kDimText, "%s", p->version);')
    panel.write_text(text,encoding="utf-8")
    catalog=source/"runtime/ui_text.c"
    text=catalog.read_text(encoding="utf-8").replace('"NX2navi %s','"DekuForge %s')
    text=text.replace('"Infinite health"','"Auto-refill hearts"')
    text=text.replace('"Vida infinita"','"Rellenar corazones"')
    text=text.replace('"\u0411\u0435\u0441\u043a\u043e\u043d\u0435\u0447\u043d\u043e\u0435 \u0437\u0434\u043e\u0440\u043e\u0432\u044c\u0435"','"\u0410\u0432\u0442\u043e\u043f\u043e\u043f\u043e\u043b\u043d\u0435\u043d\u0438\u0435 \u0441\u0435\u0440\u0434\u0435\u0446"')
    text=text.replace('"\u65e0\u9650\u751f\u547d"','"\u81ea\u52a8\u8865\u5145\u751f\u547d"')
    catalog.write_text(text,encoding="utf-8")
    (source/"VERSION").write_text(ENGINE_VERSION+"\n",encoding="ascii")
    info={"engine_version":ENGINE_VERSION,"build_kit_version":BUILD_KIT_VERSION,
          "base_engine_version":"0.10.1","cheat_revision":OWNED_CHEATS_REVISION,"layer_sha256":layer_identity()}
    (source/"DEKUFORGE-LAYER.json").write_text(json.dumps(info,indent=2),encoding="utf-8")
    return info
