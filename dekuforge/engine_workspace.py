"""Compose pinned engine source and original extensions in an owned build folder."""

import os
import re
from pathlib import Path
import shutil

from .core import ROOT


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
    shutil.copytree(root / "engine", output, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("build", "generated", "refs", "toolchain", "__pycache__"))
    shutil.copyfile(root / "engine_overrides" / "lifter.py", output / "recomp" / "lifter.py")
    shutil.copyfile(root / "engine_overrides" / "half_negate.h", output / "runtime" / "df_half_negate.h")
    shutil.copyfile(root / "engine_overrides" / "constructor_flag.h", output / "runtime" / "df_constructor_flag.h")
    shutil.copyfile(root / "engine_overrides" / "dot_product.h", output / "runtime" / "df_dot_product.h")
    cpu = output / "runtime" / "cpu.h"
    cpu.write_text(cpu.read_text(encoding="utf-8") + '\n#include "df_half_negate.h"\n#include "df_dot_product.h"\n', encoding="utf-8")
    loader = output / "runtime" / "loader.c"
    content = loader.read_text(encoding="utf-8")
    content, count = re.subn(r'static uint64_t decode_ctor_flag\(const Mod \*m\) \{.*?\n\}',
                            '''static uint64_t decode_ctor_flag(const Mod *m) {
    if (!m->pub.init || m->pub.init < m->pub.base) return 0;
    uint64_t offset = df_ctor_flag_offset((const uint8_t *)(uintptr_t)m->pub.base,
        m->pub.size, m->pub.data_off, m->pub.text_end, m->pub.init - m->pub.base);
    return offset ? m->pub.base + offset : 0;
}''', content, count=1, flags=re.DOTALL)
    if count != 1:
        raise ValueError("Constructor decoder no longer matches the pinned engine")
    loader.write_text('#include "df_constructor_flag.h"\n' + content, encoding="utf-8")
    boot = output / "runtime" / "boot.c"
    content = boot.read_text(encoding="utf-8")
    original = '#define expected_inits (RT_V143 ? inits_143 : RT_V110 ? inits_110 : inits_121)'
    if content.count(original) != 1:
        raise ValueError("Boot assertions no longer match the pinned engine")
    replacement = '''#if __has_include("df_boot_profile.h")
#include "df_boot_profile.h"
static const InitCount df_expected_inits[] = {DF_BOOT_INIT_ROWS};
#define expected_inits df_expected_inits
#else
''' + original + '\n#endif'
    boot.write_text(content.replace(original, replacement), encoding="utf-8")
    replacements = {
        "runtime/romfs.c": ('"NX2NAVIRFS1", 8', '"DFROMFS1", 8'),
        "tools/romfs_index.py": ("MAGIC = b'NX2NAVIRFS1'", "MAGIC = b'DFROMFS1'"),
    }
    for relative, (original, replacement) in replacements.items():
        path = output / relative
        text = path.read_text(encoding="utf-8")
        if text.count(original) != 1:
            raise ValueError("Engine format extension no longer matches its pinned source")
        path.write_text(text.replace(original, replacement), encoding="utf-8")
    return output
