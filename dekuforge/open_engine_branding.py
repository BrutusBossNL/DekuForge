# SPDX-License-Identifier: GPL-3.0-or-later
"""Recorded runtime adaptations of the pinned GPL provider.

Original provider files stay immutable. Only the affected translation units use
generated, attributed copies, so unrelated CPU/renderer objects remain reusable.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from .core import ROOT


def game_resource(work, compiler):
    """Embed the project's icon and component identity, preserving cache timestamps."""
    work = Path(work).absolute()
    if work.resolve() != work or not work.is_relative_to(ROOT/'build'):
        raise ValueError('Game resources must stay inside the independent build folder')
    compiler = Path(compiler).resolve()
    tool = compiler/'bin/x86_64-w64-mingw32-windres.exe'
    if not tool.is_file():
        raise ValueError('Explicit LLVM-MinGW resource compiler is missing')
    version = json.loads((ROOT/'dekuforge/components.json').read_text())['engine']['version']
    digits = [int(n) for n in re.findall(r'\d+', version)[:4]]
    digits = (digits+[0]*4)[:4]
    numbers = ','.join(map(str, digits))
    text = ('#include <windows.h>\n1 ICON "'+(ROOT/'assets/branding/launcher.ico').as_posix()+'"\n'
            '1 VERSIONINFO\nFILEVERSION '+numbers+'\nPRODUCTVERSION '+numbers+'\n'
            'FILEFLAGSMASK 0x3fL\nFILEFLAGS 0\nFILEOS 0x40004L\nFILETYPE 1\nBEGIN\n'
            ' BLOCK "StringFileInfo"\n BEGIN\n  BLOCK "040904b0"\n  BEGIN\n'
            '   VALUE "FileDescription", "DekuForge experimental game"\n'
            '   VALUE "ProductName", "DekuForge"\n'
            '   VALUE "FileVersion", "'+version+'"\n'
            '   VALUE "ProductVersion", "'+version+'"\n'
            '  END\n END\n BLOCK "VarFileInfo"\n BEGIN\n  VALUE "Translation", 0x409, 1200\n END\nEND\n')
    work.mkdir(parents=True, exist_ok=True)
    rc, target = work/'dekuforge-game.rc', work/'hookshot.res'
    rc.write_text(text, encoding='utf-8')
    staged = work/'dekuforge-game.new.res'
    subprocess.run([str(tool), '-O', 'res', '-i', str(rc), '-o', str(staged)], check=True,
                   env={**os.environ, 'PATH': str(tool.parent)+os.pathsep+os.environ.get('PATH', '')})
    if target.exists() and target.read_bytes() == staged.read_bytes():
        staged.unlink()
    else:
        staged.replace(target)
    return target


def _replace(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Pinned UI adaptation anchor changed: ' + old[:65])
    return text.replace(old, new, 1)


def prepare(source, output):
    source, output = Path(source).resolve(), Path(output).absolute()
    if output.resolve() != output or not output.is_relative_to(ROOT / 'build'):
        raise ValueError('Adapted source must remain in the independent build folder')
    output.mkdir(parents=True, exist_ok=True)
    palette = (source / 'gpu/vk/vk_ui.h').read_text(encoding='utf-8')
    for old, new in (
        ('kGold = rgba(222, 152, 40)', 'kGold = rgba(233, 185, 73)'),
        ('kGoldHi = rgba(238, 168, 52)', 'kGoldHi = rgba(250, 207, 105)'),
        ('kGoldInk = rgba(36, 24, 8)', 'kGoldInk = rgba(9, 24, 14)'),
        ('kEdge = rgba(122, 98, 64, 150)', 'kEdge = rgba(114, 135, 69, 150)'),
        ('kCellDark = rgba(30, 25, 19, 246)', 'kCellDark = rgba(11, 28, 19, 246)'),
        ('kCellName = rgba(60, 47, 32, 240)', 'kCellName = rgba(29, 53, 35, 240)'),
        ('kCellNameSel = rgba(92, 70, 42, 248)', 'kCellNameSel = rgba(55, 78, 40, 248)'),
        ('kColumn = rgba(34, 26, 17, 228)', 'kColumn = rgba(12, 30, 20, 238)'),
        ('kBronze = rgba(84, 64, 38)', 'kBronze = rgba(43, 73, 40)'),
        ('kBannerTop = rgba(184, 146, 96, 246)', 'kBannerTop = rgba(24, 58, 37, 246)'),
        ('kBanner = rgba(176, 138, 88, 246)', 'kBanner = rgba(16, 43, 28, 246)'),
        ('kBannerInk = rgba(46, 30, 12)', 'kBannerInk = rgba(245, 225, 174)'),
        ('kBannerEdge = rgba(70, 48, 24)', 'kBannerEdge = rgba(86, 106, 48)'),
        ('kTabInset = rgba(84, 56, 30, 250)', 'kTabInset = rgba(40, 68, 42, 250)'),
        ('kBox = rgba(36, 28, 19, 248)', 'kBox = rgba(15, 33, 23, 248)'),
        ('kBoxEdge = rgba(122, 98, 64, 220)', 'kBoxEdge = rgba(114, 135, 69, 220)'),
        ('kBar = rgba(22, 17, 11, 232)', 'kBar = rgba(8, 22, 15, 240)'),
    ):
        palette = _replace(palette, old, new)
    files = {'vk_ui.h': palette}
    menu = (source / 'gpu/vk/vk_menu.cpp').read_text(encoding='utf-8')
    menu = _replace(menu, '#include "vk_ui.h"', '#include "' + (output / 'vk_ui.h').as_posix() + '"')
    menu = _replace(menu, 'std::string("Hookshot ")', 'std::string("DekuForge ")')
    menu = _replace(menu,
        'ui::spaced(c, c.f.heading, 42 * k, ImVec2(cx, y), ui::rgba(246, 232, 204), "HOOKSHOT", 6 * k);',
        'ui::text_centre(c, c.f.body, 20 * k, ImVec2(cx, y + 12 * k), ui::kAccent, "Reforging a legend.");')
    menu = _replace(menu, 'ui::rgba(14, 10, 6)', 'ui::rgba(7, 21, 13)')
    for old, new in (
        ('"Controls", "Debug"}', '"Controls", "Cheat Manager"}'),
        ('{TAB_DEBUG, "Debug tools",', '{TAB_DEBUG, "Enable cheats",'),
        ('{TAB_DEBUG, "Movement speed",', '{TAB_DEBUG, "Sprint speed",'),
        ('How fast Link walks, runs and swims, as a multiple of his own speed. Choose with Left or Right.',
         'Sets the speed multiplier while sprinting. Hold the left stick click (L3) or the normal sprint button while moving.'),
        ('"Nintendo (Def)", "Xbox / PC", "Swap Face", "Custom"', '"Nintendo", "PlayStation / Xbox", "Swap Face", "Custom"'),
    ):
        menu = _replace(menu, old, new)
    menu = _replace(menu, 'constexpr int link_speeds[] = {100, 125, 150, 200, 300};',
                    'constexpr int link_speeds[] = {100, 125, 150, 200, 300, 350, 500};')
    menu = _replace(menu, 'constexpr const char* link_speed_names[] = {"1x", "1.25x", "1.5x", "2x", "3x"};',
                    'constexpr const char* link_speed_names[] = {"1x", "1.25x", "1.5x", "2x", "3x", "3.5x", "5x"};')
    sprint_header = (ROOT / 'engine_overrides/independent/sprint.h').as_posix()
    sprint_include = f'#include "{sprint_header}"'
    resource_include = f'#include "{(ROOT / "engine_overrides/independent/resources.h").as_posix()}"'
    projectile_include = f'#include "{(ROOT / "engine_overrides/independent/projectiles.h").as_posix()}"'
    aura_include = f'#include "{(ROOT / "engine_overrides/independent/projectile_aura.h").as_posix()}"'
    world_include = f'#include "{(ROOT / "engine_overrides/independent/world_markers.h").as_posix()}"'
    menu = '\n'.join((sprint_include, resource_include, projectile_include, world_include, menu))
    menu = _replace(menu, 'namespace mkwvk {', aura_include + '\nnamespace mkwvk {')
    menu = _replace(menu, 'if (rows[tab_row_to_global(TAB_DEBUG, k)].cheat == debug_tools_order[t]) out[n++] = k;',
                    'if (debug_tools_order[t] != 0 && rows[tab_row_to_global(TAB_DEBUG, k)].cheat == debug_tools_order[t]) out[n++] = k;')
    menu = _replace(menu, '    return cheats_on() || v < 0 ? v : 0;', '    return 0;')
    menu = _replace(menu, 'int menu_heart_protection() {\n    const int v = protect_hearts.load(std::memory_order_relaxed);',
                    'int menu_heart_protection() {')
    menu = _replace(menu, '    if (!start && !fps && !open) {',
                    '''    DfAuraDot aura[16];
    const unsigned aura_count = !start && !open ? df_aura_dots(aura, 16, w, h) : 0;
    if (!start && !fps && !open && !aura_count) {''')
    menu = _replace(menu, '    if (!open && !fps) return;',
                    '''    DfAuraDot aura[16];
    const unsigned aura_count = !open && !startup_on.load(std::memory_order_acquire) ? df_aura_dots(aura, 16, w, h) : 0;
    if (!open && !fps && !aura_count) return;''')
    aura_draw = '''    for (unsigned i = 0; i < aura_count; ++i)
        for (int layer = 8; layer >= 1; --layer)
            c.d->AddCircleFilled(ImVec2(aura[i].x, aura[i].y), aura[i].radius * (0.35f + 0.095f * layer),
                                 IM_COL32(3, 2, 5, 24), 24);
'''
    menu = menu.replace('    if (open) draw_menu(c);', aura_draw + '    if (open) draw_menu(c);')
    menu = _replace(menu, 'const char* tx_auto_run(int v)',
                    '''static int df_sprint_mode, df_air_jump;
static int df_resources[DF_RESOURCE_OPTIONS];
static int df_spin_range, df_spin_charge;
static int df_bomb_arrows, df_explosive_seeds;
static int df_world[7];
static bool df_world_row(const int* value) {
    for (int& option : df_world) if (value == &option) return true;
    return false;
}
static bool df_world_ready() { return getenv("DEKUFORGE_WORLD_DATA") != nullptr; }
static bool df_equipment_row(const int* value) {
    return value == &df_spin_range || value == &df_spin_charge ||
           value == &df_bomb_arrows || value == &df_explosive_seeds;
}
const char* tx_spin_range(int v) {
    static const char* const labels[] = {"Normal", "1.5x", "2x", "2.5x"};
    return labels[std::clamp(v, 0, 3)];
}
const char* tx_spin_charge(int v) { return v ? "Instant" : "Normal"; }
static int df_bottles[DF_BOTTLES] = {-1, -1, -1, -1, -1};
static int df_bottle_edit[DF_BOTTLES];
static int df_bottle_slot(const int* value) {
    for (int i = 0; i < DF_BOTTLES; ++i) if (value == &df_bottles[i]) return i;
    return -1;
}
const char* tx_bottle_content(int v) {
    static const char* const names[DF_BOTTLE_TYPES] = {"Empty", "Red potion", "Green potion", "Blue potion",
        "Blue fire", "Fish", "Letter", "Big Poe", "Poe", "Bugs", "Fairy", "Milk", "Half milk"};
    return v >= 0 && v < DF_BOTTLE_TYPES ? names[v] : "Locked";
}
static bool df_resource_row(const int* value) {
    if (value == &df_air_jump) return true;
    for (int& resource : df_resources) if (value == &resource) return true;
    return false;
}
const char* tx_l3_sprint(int v) { return v ? "Click to toggle" : "Hold L3"; }
const char* tx_auto_run(int v)''')
    menu = _replace(menu, '    {TAB_CONTROLS, "Auto run",',
                    '''    {TAB_CONTROLS, "L3 sprint", &df_sprint_mode, 0, 1, 1, tx_l3_sprint,
     "Hold L3 to sprint, or click to toggle. In toggle mode, stopping movement cancels the sprint.", nullptr, false, true},
    {TAB_CONTROLS, "Auto run",''')
    menu = _replace(menu, '} // namespace mkwvk',
                    '''int menu_dekuforge_option(int id) {
    std::lock_guard lk(menu_mu);
    if (id == DF_OPT_L3_SPRINT) return df_sprint_mode;
    if (id == DF_OPT_AIR_JUMP) return cheats_on() && df_air_jump;
    if (id == DF_OPT_WORLD) {
        int mask = 0;
        if (cheats_on() && df_world_ready())
            for (unsigned i = 0; i < 7; ++i) if (df_world[i]) mask |= 1 << i;
        return mask;
    }
    if (id == DF_OPT_SPIN) return cheats_on() ? df_spin_range | (df_spin_charge ? DF_SPIN_INSTANT : 0) : 0;
    if (id == DF_OPT_EXPLOSIVE_SHOTS) return cheats_on() ?
        (df_bomb_arrows ? DF_BOMB_ARROW : 0) | (df_explosive_seeds ? DF_EXPLOSIVE_SEED : 0) : 0;
    if (id == DF_OPT_BOTTLE_EDITS) {
        const bool enabled = cheats_on();
        int packed = 0;
        for (int i = 0; i < DF_BOTTLES; ++i) {
            if (enabled) packed |= df_bottle_edit[i] << (i * 4);
            df_bottle_edit[i] = 0;
        }
        return enabled ? packed : -1;
    }
    int mask = 0;
    if (cheats_on())
        for (int i = 0; i < DF_RESOURCE_OPTIONS; ++i) if (df_resources[i]) mask |= 1 << i;
    return mask;
}
} // namespace mkwvk''')
    developer_rows = '''    for (int k = 0; k < count; ++k) {
        const Row& r = rows[tab_row_to_global(TAB_DEBUG, k)];
        if (r.heading) *dev_head = k;
        else if (*dev_head >= 0 && r.cheat < 0 && r.value != &opts.debug_tools) out[n++] = k;
    }
'''
    menu = _replace(menu, developer_rows, '''    if (cheats_on())
        for (int k = 0; k < count; ++k) {
            const Row& r = rows[tab_row_to_global(TAB_DEBUG, k)];
            if (r.heading) *dev_head = k;
            else if (df_resource_row(r.value) || df_bottle_slot(r.value) >= 0 || df_equipment_row(r.value) ||
                     (df_world_ready() && df_world_row(r.value))) out[n++] = k;
        }
''')
    menu = _replace(menu, '    {TAB_DEBUG, "Developer", nullptr, 0, 0, 0, nullptr, nullptr, nullptr, false, true, -1, true},',
                    '''    {TAB_DEBUG, "Link and resources", nullptr, 0, 0, 0, nullptr, nullptr, nullptr, false, true, -1, true},
    {TAB_DEBUG, "Unlimited jumps", &df_air_jump, 0, 1, 1, tx_onoff,
     "Press the jump button again in the air to jump again.", nullptr, false, true},
    {TAB_DEBUG, "Auto-refill hearts", &df_resources[DF_RESOURCE_HEARTS], 0, 1, 1, tx_onoff,
     "Refills existing hearts while Link is alive.", nullptr, false, true},
    {TAB_DEBUG, "Freeze countdown", &df_resources[DF_RESOURCE_TIMER], 0, 1, 1, tx_onoff,
     "Freezes the shared event and minigame countdown while it is running.", nullptr, false, true},
    {TAB_DEBUG, "Refill magic", &df_resources[DF_RESOURCE_MAGIC], 0, 1, 1, tx_onoff,
     "Refills the unlocked magic meter up to its current capacity.", nullptr, false, true},
#define DF_RESOURCE_ROW(id, label, ...) \\
    {TAB_DEBUG, label, &df_resources[DF_RESOURCE_##id], 0, 1, 1, tx_onoff, \\
     "Refills the resource up to its current limit once available.", nullptr, false, true},
    DF_RESOURCE_ROWS(DF_RESOURCE_ROW)
#undef DF_RESOURCE_ROW
    {TAB_DEBUG, "Spin attack range", &df_spin_range, 0, 3, 1, tx_spin_range,
     "Scales the charged spin attack for the equipped sword.", nullptr, false, true},
    {TAB_DEBUG, "Magic spin charge", &df_spin_charge, 0, 1, 1, tx_spin_charge,
     "Charges the magic spin instantly once the Great Fairy has unlocked it.", nullptr, false, true},
    {TAB_DEBUG, "Bomb arrows", &df_bomb_arrows, 0, 1, 1, tx_onoff,
     "Adult Link's normal arrows can consume a bomb to explode on impact.", nullptr, false, true},
    {TAB_DEBUG, "Explosive Deku seeds", &df_explosive_seeds, 0, 1, 1, tx_onoff,
     "Young Link's slingshot seeds can consume a bomb to explode on impact.", nullptr, false, true},
#define DF_WORLD_ROW(index, label, detail) \
    {TAB_DEBUG, label, &df_world[index], 0, 1, 1, tx_onoff, detail, nullptr, false, true},
    DF_WORLD_ROW(0, "Gold Skulltulas", "Show this age's Gold Skulltulas. A moon marks night-only locations.")
    DF_WORLD_ROW(1, "Heart pieces", "Show these heart pieces on the map and mark the ones already collected.")
    DF_WORLD_ROW(2, "Grottos", "Show hidden grotto entrances for the current age.")
    DF_WORLD_ROW(3, "Chests", "Show extra chest markers and keep the native opened state.")
    DF_WORLD_ROW(4, "Bean plots", "Show soft soil for planting magic beans.")
    DF_WORLD_ROW(5, "Great Fairies", "Show Great Fairy locations and known collected rewards.")
    DF_WORLD_ROW(6, "Upgrades", "Show permanent upgrade locations and known collected rewards.")
#undef DF_WORLD_ROW
#define DF_BOTTLE_ROW(n) \\
    {TAB_DEBUG, "Bottle " #n, &df_bottles[n - 1], 0, DF_BOTTLE_TYPES - 1, 1, tx_bottle_content, \\
     "Changes the contents once. The item is used normally and kept by an in-game save.", nullptr, false, true},
    DF_BOTTLE_ROW(1) DF_BOTTLE_ROW(2) DF_BOTTLE_ROW(3) DF_BOTTLE_ROW(4) DF_BOTTLE_ROW(5)
#undef DF_BOTTLE_ROW''')
    menu = _replace(menu,
        '''    for (int i = dev; i < n; ++i) vrow[i] = dev_row + 1 + (i - dev);
    const int visual_count = n > dev ? dev_row + 1 + (n - dev) : foot;''',
        '''    int extra_row = dev_row + 1, equipment_head = -1, world_head = -1, bottles_head = -1;
    for (int i = dev; i < n; ++i) {
        const int* v = rows[tab_row_to_global(TAB_DEBUG, order[i])].value;
        if (df_equipment_row(v) && equipment_head < 0) {
            extra_row++;
            equipment_head = extra_row++;
        }
        if (df_world_row(v) && world_head < 0) {
            extra_row++;
            world_head = extra_row++;
        }
        if (df_bottle_slot(v) >= 0 && bottles_head < 0) {
            extra_row++;
            bottles_head = extra_row++;
        }
        vrow[i] = extra_row++;
    }
    const int visual_count = n > dev ? extra_row : foot;''')
    menu = _replace(menu, '    if (dev_head >= 0 && n > dev) heading(left, right, dev_row, rows[tab_row_to_global(TAB_DEBUG, dev_head)].name);',
                    '''    if (dev_head >= 0 && n > dev) heading(left, right, dev_row, rows[tab_row_to_global(TAB_DEBUG, dev_head)].name);
    if (equipment_head >= 0) heading(left, right, equipment_head, "Equipment");
    if (world_head >= 0) heading(left, right, world_head, "World");
    if (bottles_head >= 0) heading(left, right, bottles_head, "Bottle contents");''')
    menu = _replace(menu, 'bool row_shown(int i) {\n    const int* v = rows[i].value;',
                    '''bool row_shown(int i) {
    const int* v = rows[i].value;
    if (df_world_row(v)) return cheats_on() && df_world_ready();
    if (const int slot = df_bottle_slot(v); slot >= 0) return cheats_on() && df_bottles[slot] >= 0;''')
    menu = _replace(menu, 'void set_row(Row& r, int v, int dir, bool keep = true) {',
                    '''void set_row(Row& r, int v, int dir, bool keep = true) {
    if (const int slot = df_bottle_slot(r.value); slot >= 0) {
        if (cheats_on() && df_bottles[slot] >= 0) {
            df_bottles[slot] = v < r.lo ? r.hi : v > r.hi ? r.lo : v;
            df_bottle_edit[slot] = df_bottles[slot] + 1;
            menu_refresh = true;
        }
        return;
    }''')
    menu = _replace(menu, 'void menu_option_set(int id, int value) {',
                    '''void menu_option_set(int id, int value) {
    if (id >= DF_OPT_BOTTLE_REPORT && id < DF_OPT_BOTTLE_REPORT + DF_BOTTLES) {
        std::lock_guard lk(menu_mu);
        const int slot = id - DF_OPT_BOTTLE_REPORT;
        if (!df_bottle_edit[slot]) df_bottles[slot] = value;
        menu_refresh = true;
        return;
    }''')
    menu = _replace(menu, 'else if (r.value && r.value != &opts.game_lang) {',
                    'else if (r.value && r.value != &opts.game_lang && df_bottle_slot(r.value) < 0) {')
    menu = _replace(menu, 'if (!r.value || r.value == &opts.game_lang || strcmp(line, ini_key(r))) continue;',
                    'if (!r.value || r.value == &opts.game_lang || df_bottle_slot(r.value) >= 0 || strcmp(line, ini_key(r))) continue;')
    menu = _replace(menu, '''        c.d->AddRectFilled(ImVec2(cx, ty - 13 * s), ImVec2(cx + cw, ty + 13 * s), hover ? ui::kTabInset : ui::kBannerInk, 3 * s);
        ui::text_mid_centre(c, c.f.strong, 14 * s, cx + cw * 0.5f, ty, ui::kInk, keys[i]);''',
                    '''        const ImVec2 a(cx, ty - 13 * s), b(cx + cw, ty + 13 * s);
        c.d->AddRectFilled(a, b, hover ? ui::kCellNameSel : ui::kTabInset, 4 * s);
        c.d->AddRect(a, b, ui::kEdge, 4 * s);
        ui::text_mid_centre(c, c.f.strong, 14 * s, cx + cw * 0.5f, ty, ui::kInkBright, keys[i]);''')
    menu = _replace(menu, '''    ui::banner(c, hh);
    // the tabs in the banner:''',
                    '''    c.d->AddRectFilledMultiColor(ImVec2(0, 0), ImVec2(c.w, hh),
                                 ui::rgba(35, 69, 44), ui::rgba(22, 48, 34),
                                 ui::rgba(8, 22, 15), ui::rgba(12, 32, 22));
    c.d->AddLine(ImVec2(0, hh - s), ImVec2(c.w, hh - s), ui::kEdge, std::max(1.0f, s));
    // the tabs in the banner:''')
    menu = _replace(menu, '''            c.d->AddRectFilled(ImVec2(x, 0), ImVec2(x + tw[i], hh - 3 * s), shown ? ui::kTabInset : ui::alpha(ui::kTabInset, 0.35f));
            if (shown) {
                c.d->AddLine(ImVec2(x + 1, 0), ImVec2(x + 1, hh - 3 * s), ui::rgba(52, 34, 16), std::max(1.0f, s));
                c.d->AddLine(ImVec2(x + tw[i] - 1, 0), ImVec2(x + tw[i] - 1, hh - 3 * s), ui::rgba(52, 34, 16), std::max(1.0f, s));
            }''',
                    '''            const ImVec2 a(x + 4 * s, 6 * s), b(x + tw[i] - 4 * s, hh - 6 * s);
            c.d->AddRectFilled(a, b, shown ? ui::kTabInset : ui::alpha(ui::kTabInset, 0.72f), 7 * s);
            if (shown) {
                c.d->AddRect(a, b, ui::kEdge, 7 * s);
                c.d->AddRectFilled(ImVec2(a.x + 14 * s, b.y - 3 * s), ImVec2(b.x - 14 * s, b.y),
                                  ui::kGold, 1.5f * s);
            }''')
    menu = _replace(menu, 'const ImU32 green = ui::rgba(72, 255, 110), ink =',
                    'const ImU32 green = ui::rgba(155, 221, 130), ink =')
    menu = _replace(menu, '''    const float edge = left ? c.safe : c.w - c.safe;
    const float top = bottom ? c.h - c.safe - h : under_banner && !tune_mode && page != 5 && !beside ? banner_h(c) + 10 * s : c.safe;''',
                    '''    const float pad = 10 * s;
    const float edge = left ? c.safe + pad : c.w - c.safe - pad;
    const float top = bottom ? c.h - c.safe - h - pad :
        (under_banner && !tune_mode && page != 5 && !beside ? banner_h(c) : c.safe) + pad + 3 * s;''')
    menu = _replace(menu, '    const auto at = [&](float w) { return left ? edge : edge - w; };',
                    '''    const auto at = [&](float w) { return left ? edge : edge - w; };
    float panel = std::max(nw + 4 * s + lw, sw);
    if (level >= fs::kFrameTime && fps_ms_text[0])
        panel = std::max(panel, tab.width(fps_ms_text) + 10 * s + tab.width(fps_low_text));
    if (level >= fs::kGraph) panel = std::max(panel, gw + 32 * s);
    const ImVec2 card_a(at(panel) - pad, top - pad), card_b(at(panel) + panel + pad, top + h + pad);
    c.d->AddRectFilled(card_a, card_b, ui::rgba(9, 23, 16, 237), 8 * s);
    c.d->AddRect(card_a, card_b, ui::kEdge, 8 * s);
    c.d->AddRectFilled(ImVec2(card_a.x + pad, card_a.y + 2 * s), ImVec2(card_b.x - pad, card_a.y + 4 * s),
                      ui::kGold, s);''')
    menu = _replace(menu, ' : green;\n    {   // (the number and "FPS"', ' : ui::kGoldHi;\n    {   // (the number and "FPS"')
    start, end = '    {TAB_DEBUG, "Save my pipeline list",', '    {TAB_DEBUG, "Descriptor reuse",'
    if menu.count(start) != 1 or menu.count(end) != 1:
        raise ValueError('Pinned pipeline-submission row changed')
    first, last = menu.index(start), menu.index(end)
    if first >= last:
        raise ValueError('Unexpected pipeline-submission row bounds')
    menu = menu[:first]+'    // DekuForge reports never request pipeline/cache uploads.\n'+menu[last:]
    menu = menu.replace('github.com/NotRexed/Hookshot/issues/2034', 'github.com/BrutusBossNL/DekuForge/issues')
    menu = menu.replace('github.com/NotRexed/Hookshot/issues', 'github.com/BrutusBossNL/DekuForge/issues')
    files['vk_menu.cpp'] = menu
    display = (source / 'host/display.c').read_text(encoding='utf-8')
    display = _replace(display, '#include "hos.h"', '#include "hos.h"\n#undef HOS_GAME_TITLE\n#define HOS_GAME_TITLE "DekuForge"')
    files['display.c'] = display
    hid = (source / 'host/nn_hid.c').read_text(encoding='utf-8')
    hid = sprint_include + '\n' + hid
    hid = _replace(hid, 'static int move_stick_held;',
                   '''static int sprint_held;
int hos_dekuforge_sprint_held(void) { return __atomic_load_n(&sprint_held, __ATOMIC_RELAXED); }
static int move_stick_held;''')
    hid = _replace(hid, '        __atomic_store_n(&flight_input, flight, __ATOMIC_RELAXED);',
                   '''        int hos_oot_player_free(void);
        void df_guest_air_jump(Ctx *);
        const int player_input = !menu_open && !free_camera && !flying && hos_oc_wait != 1 &&
                                 !(buttons & ((1ULL << B_PLUS) | (1ULL << B_MINUS))) && hos_oot_player_free();
        static int jump_held;
        const int jump_down = !!(buttons & (1ULL << B_X));
        const int jump_was_down = __atomic_exchange_n(&jump_held, jump_down, __ATOMIC_RELAXED);
        if (jump_down && !jump_was_down &&
            player_input && rx_option(DF_OPT_AIR_JUMP, 0)) df_guest_air_jump(c);
        const int sprint_allowed = player_input && (abs(stick[0]) > 4096 || abs(stick[1]) > 4096);
        static DfSprint sprint;
        const int l3 = !!(buttons & (1ULL << B_LS));
        const int l3_active = df_sprint(&sprint, rx_option(DF_OPT_L3_SPRINT, 0), l3, sprint_allowed);
        if (l3_active) {
            static int told;
            if (!__atomic_exchange_n(&told, 1, __ATOMIC_RELAXED)) hos_log("hid: left-stick click activated sprint");
            buttons &= ~(1ULL << B_LS);
            buttons |= 1ULL << B_A;
        }
        __atomic_store_n(&sprint_held, sprint_allowed && (buttons & (1ULL << B_A)), __ATOMIC_RELAXED);
        __atomic_store_n(&flight_input, flight, __ATOMIC_RELAXED);''')
    files['nn_hid.c'] = hid
    replay = (source / 'gpu/vk/vk_replay.cpp').read_text(encoding='utf-8')
    replay = '\n'.join((sprint_include, resource_include, projectile_include, world_include, replay))
    replay = _replace(replay, '        if (id == HOS_OPT_AUTO_RUN)',
                      '''        extern int menu_dekuforge_option(int);
        if (id == DF_OPT_L3_SPRINT || id == DF_OPT_RESOURCE_MASK || id == DF_OPT_BOTTLE_EDITS ||
            id == DF_OPT_SPIN || id == DF_OPT_EXPLOSIVE_SHOTS || id == DF_OPT_AIR_JUMP || id == DF_OPT_WORLD)
            return menu_dekuforge_option(id);
        if (id == HOS_OPT_AUTO_RUN)''')
    files['vk_replay.cpp'] = replay
    host = (source / 'host/hos_main.c').read_text(encoding='utf-8')
    host = _replace(host, 'static void oot_update_player_cheats(Ctx *c,',
                    '\n'.join(('#define DF_RESOURCE_HOST', resource_include, '#define DF_PROJECTILE_HOST',
                               projectile_include, '#define DF_WORLD_HOST', world_include,
                               'static void oot_update_player_cheats(Ctx *c,')))
    host = _replace(host, '    hos_mods_init(image);', '    df_world_init();\n    hos_mods_init(image);')
    host = _replace(host, '    oot_player_speed(c, components);',
                    '''    oot_player_speed(c, components);
    df_refill_resources(c, actor, rx_option(DF_OPT_RESOURCE_MASK, 0), rx_option(DF_OPT_BOTTLE_EDITS, -1));''')
    host = _replace(host, '    if (percent < 100 || percent > 400) percent = 100;',
                    '    if (percent < 100 || percent > 500) percent = 100;')
    host = _replace(host, '''    int hos_move_stick_held(void);   /* host/nn_hid.c */
    if (percent <= 100 || percent > 400 || !hos_move_stick_held()) return;''',
                    '''    int hos_dekuforge_sprint_held(void);   /* host/nn_hid.c */
    if (percent <= 100 || percent > 500 || !hos_dekuforge_sprint_held()) return;''')
    host = _replace(host, '    speed *= percent / 100.0f;',
                    '''    static int logged_multiplier;
    if (__atomic_exchange_n(&logged_multiplier, percent, __ATOMIC_RELAXED) != percent)
        hos_log("cheats: sprint speed applied at %d%%", percent);
    speed *= percent / 100.0f;''')
    files['hos_main.c'] = host
    pad = (source / 'host/pad_sdl.c').read_text(encoding='utf-8')
    pad = _replace(pad, '            b |= sig;\n', '')
    for button in ('TOUCHPAD', 'LTRIGGER', 'RTRIGGER'):
        pad = _replace(pad, f') b |= 1ULL << HOS_PAD_{button};', f') sig |= 1ULL << HOS_PAD_{button};')
    pad = _replace(pad, '            const int inv_x = rx_option(16, 0);',
                   '            b |= sig;\n            const int inv_x = rx_option(16, 0);')
    pad = _replace(pad, '                if (sig != pads[i].input_sig) pads[i].input_sig = sig, pads[i].used_ns = now;',
                   '''                if (sig && sig != pads[i].input_sig) pads[i].used_ns = now;
                pads[i].input_sig = sig;''')
    pad = _replace(pad, '''        for (int i = 0; i < MAX_PADS; i++)
            if (pads[i].gc && !pads[i].motion_only) {   /* (the stand-in's name, not its motion-only pad's) */
                const char *name = hos_sdl_pad_name(pads[i].gc);
                snprintf(state_name, sizeof state_name, "%s", name ? name : "");
                break;
            }''',
                   '''        int active = -1;
        for (int i = 0; i < MAX_PADS; i++)
            if (pads[i].gc && !pads[i].motion_only &&
                (active < 0 || pads[i].used_ns > pads[active].used_ns))
                active = i;
        if (active >= 0) {
            void *gc = pads[active].gc;
            const char *name = hos_sdl_pad_name(gc);
            const int type = hos_sdl_pad_type(gc);
            /* SDL 2 and SDL 3 use different gamepad type enums. Keep the
               device name for Steam Input and other types without a face. */
            const int three = hos_sdl_load() == 3;
            if (type == (three ? 6 : 7)) name = "DualSense";
            else if (type == (three ? 5 : 4)) name = "DualShock 4";
            else if (type == (three ? 7 : 5)) name = "Nintendo Switch Pro";
            snprintf(state_name, sizeof state_name, "%s", name ? name : "");
        }''')
    files['pad_sdl.c'] = pad
    applet = (source / 'host/nn_applet.c').read_text(encoding='utf-8')
    applet = _replace(applet, '                int known = 0;',
                      '                int known = !_stricmp(code, "system");')
    applet = _replace(applet, '\\n\\nen-US\\n\\n", f);', '\\n\\nsystem\\n\\n", f);')
    applet = _replace(applet, '    snprintf(lang, sizeof lang, "en-US");',
                      '''    if (!want[0] || !_stricmp(want, "system")) {
        const char *system = getenv("DEKUFORGE_SYSTEM_LANGUAGE");
        snprintf(want, sizeof want, "%s", system ? system : "en-US");
        from = "system language";
    }
    snprintf(lang, sizeof lang, "en-US");''')
    files['nn_applet.c'] = applet
    language = (source / 'gpu/vk/vk_menu_i18n.cpp').read_text(encoding='utf-8')
    language = _replace(language, 'constexpr GameLang kGameLangs[] = {',
                         'constexpr GameLang kGameLangs[] = {\n    {"system", "System language"},')
    language = _replace(language, '''        const std::string want = env ? known_code(env) : read_language_txt();
        return want.empty() ? std::string("en-US") : want;''',
                        '''        std::string want = env ? known_code(env) : read_language_txt();
        if (want.empty() || want == "system") {
            const char* system = getenv("DEKUFORGE_SYSTEM_LANGUAGE");
            want = system ? known_code(system) : "";
        }
        return want.empty() || want == "system" ? std::string("en-US") : want;''')
    language = _replace(language, 'return txt.empty() ? game_language_started() : txt;',
                        'return txt.empty() ? std::string("system") : txt;')
    language = _replace(language, '        const menu_i18n::Lang& l = menu_i18n::kLangs[lang];',
                        '''        const menu_i18n::Lang& l = menu_i18n::kLangs[lang];
        static const char* const labels[] = {"Enable cheats", "Sprint speed", "System language",
            "Sets the speed multiplier while sprinting. Hold the left stick click (L3) or the normal sprint button while moving."};
        static const char* const translations[][5] = {
            {"nl", "Cheats inschakelen", "Sprintsnelheid", "Systeemtaal",
             "Vermenigvuldigt je snelheid tijdens het sprinten. Houd L3 of de gewone sprintknop ingedrukt terwijl je beweegt."},
            {"de", "Cheats aktivieren", "Sprinttempo", "Systemsprache",
             "Legt den Faktor für das Sprinttempo fest. Halte beim Laufen L3 oder die normale Sprinttaste gedrückt."},
            {"es", "Activar trucos", "Velocidad de esprint", "Idioma del sistema",
             "Ajusta el multiplicador al esprintar. Mantén pulsado L3 o el botón de esprint normal mientras te mueves."},
            {"fr", "Activer les codes", "Vitesse de sprint", "Langue du système",
             "Règle le multiplicateur du sprint. Maintenez L3 ou la touche de sprint habituelle en vous déplaçant."},
        };
        for (const auto& row : translations)
            if (!strcmp(l.code, row[0]))
                for (size_t i = 0; i < sizeof labels / sizeof *labels; ++i)
                    t[lang]->exact.emplace(labels[i], row[i + 1]);
        if (!strcmp(l.code, "nl")) {
            static const char* const cheats[][2] = {
                {"L3 sprint", "Sprinten met L3"}, {"Hold L3", "L3 vasthouden"}, {"Click to toggle", "Klikken om te wisselen"},
                {"Link and resources", "Link en voorraden"}, {"Unlimited jumps", "Onbeperkt springen"},
                {"Equipment", "Uitrusting"}, {"Bottle contents", "Flesinhoud"},
                {"Auto-refill hearts", "Hartjes automatisch aanvullen"}, {"Freeze countdown", "Afteltimer stilzetten"},
                {"Refill magic", "Magie aanvullen"}, {"Refill rupees", "Roepies aanvullen"}, {"Refill bombs", "Bommen aanvullen"},
                {"Refill arrows", "Pijlen aanvullen"}, {"Refill bombchus", "Bombchu's aanvullen"},
                {"Refill Deku nuts", "Deku-noten aanvullen"}, {"Refill Deku seeds", "Deku-zaden aanvullen"},
                {"Refill Deku sticks", "Deku-stokken aanvullen"}, {"Refill magic beans", "Toverbonen aanvullen"},
                {"Refill Scrub seeds", "Scrub-zaden aanvullen"}, {"Bottle 1", "Fles 1"}, {"Bottle 2", "Fles 2"},
                {"Bottle 3", "Fles 3"}, {"Bottle 4", "Fles 4"}, {"Bottle 5", "Fles 5"},
                {"Spin attack range", "Bereik draai-aanval"}, {"Magic spin charge", "Magische draai-aanval opladen"},
                {"Bomb arrows", "Bompijlen"}, {"Explosive Deku seeds", "Explosieve Deku-zaden"},
                {"World", "Wereld"}, {"Gold Skulltulas", "Gouden Skulltula’s"}, {"Heart pieces", "Hartstukjes"},
                {"Grottos", "Grotten"}, {"Chests", "Kisten"}, {"Bean plots", "Plantplekken"},
                {"Great Fairies", "Grote feeën"}, {"Upgrades", "Upgrades"},
            };
            for (const auto& row : cheats) t[lang]->exact.emplace(row[0], row[1]);
        }''')
    files['vk_menu_i18n.cpp'] = language
    draw = (source / 'gpu/vk/vk_draw.cpp').read_text(encoding='utf-8')
    draw = draw.replace('namespace mkwvk {\n', '#define DF_AURA_RENDERER\n' + aura_include + '\nnamespace mkwvk {\n', 1)
    draw = _replace(draw, '    if (at.n && at.color[0] && at.depth) {\n        temporal_note_scene_draw',
                    '''    if (at.n && at.color[0] && at.depth) {
        if (at.color[0]->format == VK_FORMAT_B10G11R11_UFLOAT_PACK32)
            df_note_aura_camera(at.width, at.height, s.ubo[0][0]);
        temporal_note_scene_draw''')
    draw = _replace(draw,
        '    if (!gone_on && !prepare_stopped()) precompile_built_write(graphics_n);',
        '''    if (!gone_on && !prepare_stopped()) {
        // Ordinary window close only saves play generations. Persist the cache
        // built here before reporting a build's preparation complete.
        if (env_on("DEKUFORGE_SAVE_BUILD_CACHE")) {
            // The startup size already includes merged play files. Use a
            // fresh snapshot even when its size does not grow during warmup.
            size_t bytes = 0;
            const bool has_data = pcache && vkGetPipelineCacheData(dev.device, pcache, &bytes, nullptr) == VK_SUCCESS && bytes > 32;
            const size_t saved = has_data ? play_file_write(pcache, pcache_path) : 0;
            if (saved > 32) {
                pcache_saved_size = saved;
                logf("DekuForge: build pipeline cache saved (%zu bytes)", saved);
            } else {
                logf("DekuForge: build pipeline cache save failed");
            }
        }
        precompile_built_write(graphics_n);
    }''')
    files['vk_draw.cpp'] = draw
    prompts = (source / 'host/prompts.c').read_text(encoding='utf-8')
    for file in ('Common.bntx', 'Common.blarc'):
        old = f'    snprintf(path, sizeof path, "%sprompts/{file}", dir);'
        count = prompts.count(old)
        if count != 2:
            raise ValueError('Pinned prompt paths changed')
        prompts = prompts.replace(old,
            f'    if (getenv("DEKUFORGE_WORLD_DATA")) snprintf(path, sizeof path, "%s/{file}", getenv("DEKUFORGE_WORLD_DATA"));\n'
            f'    else snprintf(path, sizeof path, "%sprompts/{file}", dir);')
    for target, capacity, file in (('out', 'cap', 'Common.bntx.zs'), ('out', 'cap', 'Common.blarc.zs'),
                                   ('keypath', 'sizeof keypath', 'Common.key'), ('keypath', 'sizeof keypath', 'Common.blarc.key')):
        old = f'    snprintf({target}, {capacity}, "%sprompts/{file}", dir);'
        prompts = _replace(prompts, old,
            f'    if (getenv("DEKUFORGE_WORLD_DATA")) snprintf({target}, {capacity}, "%s/{file}", getenv("DEKUFORGE_WORLD_DATA"));\n'
            f'    else snprintf({target}, {capacity}, "%sprompts/{file}", dir);')
    files['prompts.c'] = prompts
    mapping, records = {}, {}
    origins = {'vk_ui.h': 'gpu/vk/vk_ui.h', 'vk_menu.cpp': 'gpu/vk/vk_menu.cpp',
               'display.c': 'host/display.c', 'vk_draw.cpp': 'gpu/vk/vk_draw.cpp',
               'nn_hid.c': 'host/nn_hid.c', 'hos_main.c': 'host/hos_main.c', 'pad_sdl.c': 'host/pad_sdl.c',
               'nn_applet.c': 'host/nn_applet.c', 'vk_menu_i18n.cpp': 'gpu/vk/vk_menu_i18n.cpp',
               'vk_replay.cpp': 'gpu/vk/vk_replay.cpp', 'prompts.c': 'host/prompts.c'}
    for name, text in files.items():
        path = output / name
        if path.exists() and (path.is_symlink() or getattr(path, 'is_junction', lambda: False)()):
            raise ValueError('Adapted source cannot be a link')
        kind = 'cache preparation' if name == 'vk_draw.cpp' else 'runtime'
        data = (f'// DekuForge {kind} adaptation of Hookshot; GPL-3.0-or-later.\n' + text).encode('utf-8')
        if not path.is_file() or path.read_bytes() != data:
            path.write_bytes(data)
        original = source / origins[name]
        mapping[str(original)] = str(path)
        records[origins[name]] = {'original_sha256': hashlib.sha256(original.read_bytes()).hexdigest(),
                                'adapted_sha256': hashlib.sha256(data).hexdigest()}
    (output / 'adaptations.json').write_text(json.dumps(records, indent=2)+'\n', encoding='utf-8')
    return mapping


def configure(module, source, work):
    """Install once in a fresh provider compiler process before calling main()."""
    if getattr(module, '_dekuforge_branded', False):
        raise ValueError('Provider branding already installed')
    source = Path(source).resolve()
    game_resource(work, os.environ['HOOKSHOT_MINGW'])
    mapping = prepare(source, Path(work) / 'dekuforge-ui')
    version = json.loads((ROOT / 'dekuforge/components.json').read_text(encoding='utf-8'))['engine']['version']
    os.environ['HOOKSHOT_VERSION'] = version
    logo_write = module.logo_rgba.write
    module.logo_rgba.write = lambda path: logo_write(path, str(ROOT / 'assets/branding/logo.png'))
    original_compile, original_key = module.compile_one, module.object_key

    def adapted_job(job):
        cc, src, obj, flags, deps = job
        replacement = mapping.get(str(Path(src).resolve()))
        if replacement:
            # Quoted provider includes formerly resolved beside the original file.
            flags = [*flags, '-I' + str(Path(src).parent)]
            deps += Path(mapping[str(source / 'gpu/vk/vk_ui.h')]).read_bytes()
            deps += (ROOT / 'engine_overrides/independent/sprint.h').read_bytes()
            deps += (ROOT / 'engine_overrides/independent/resources.h').read_bytes()
            deps += (ROOT / 'engine_overrides/independent/projectiles.h').read_bytes()
            deps += (ROOT / 'engine_overrides/independent/projectile_aura.h').read_bytes()
            deps += (ROOT / 'engine_overrides/independent/world_markers.h').read_bytes()
            src = replacement
        return cc, src, obj, flags, deps

    def key(src, flags, deps):
        _, src, _, flags, deps = adapted_job((None, src, None, flags, deps))
        return original_key(src, flags, deps)

    module.object_key = key
    module.compile_one = lambda job: original_compile(adapted_job(job))
    module._dekuforge_branded = True
