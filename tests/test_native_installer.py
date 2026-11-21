import copy
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from dekuforge import COMPONENTS
from tools.native_resources import digest_header, packaged_sha256, runtime_pin_header, write_resources

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r'''
#include <stdio.h>
#include <stdlib.h>
#include "archive_check.h"
static char *load(const char *path, size_t *length) {
    FILE *file = fopen(path, "rb"); char *data = malloc(1 << 20);
    *length = fread(data, 1, 1 << 20, file); fclose(file); return data;
}
int main(int argc, char **argv) {
    size_t names_length, details_length;
    char *names = load(argv[1], &names_length), *details = load(argv[2], &details_length);
    deku_listing_rules rules = {(size_t)atol(argv[3]), strtoull(argv[4], NULL, 10), argc > 5 ? argv[5] : NULL};
    const char *error = deku_check_listing(names, names_length, details, details_length, &rules);
    puts(error ? error : "OK");
    return 0;
}
'''


def detail(name, size=10, kind="-"):
    mode = "drwxr-xr-x" if kind == "d" else kind + "rw-r--r--"
    return f"{mode}  0 0      0    {size:>8} Nov 10 12:00 {name}"


class NativeInstallerSourceTests(unittest.TestCase):
    """The shipped setup and launcher must not look like a script dropper."""

    def test_setup_and_launcher_start_no_script_host_and_drop_nothing_in_temp(self):
        for name in ("installer/setup.c", "launcher/main.c", "launcher/native.c", "launcher/runtime.c"):
            text = (ROOT / name).read_text(encoding="utf-8").casefold()
            for marker in ("powershell", "executionpolicy", ".ps1", "gettemppath", "cmd.exe", "wscript", "cscript"):
                self.assertNotIn(marker, text, f"{name} references {marker}")
        self.assertFalse((ROOT / "installer/install.ps1").exists())
        self.assertFalse((ROOT / "installer/shortcut.ps1").exists())

    def test_uninstaller_runs_only_the_verified_installed_helper(self):
        text = (ROOT / "installer/uninstall.c").read_text(encoding="utf-8")
        self.assertNotIn("GetTempPath", text)
        self.assertNotIn("RT_RCDATA", text)
        self.assertIn("DEKU_UNINSTALL_SCRIPT_SHA256", text)

    def test_python_installers_use_the_native_runtime_bootstrap(self):
        worker = (ROOT / "tools/update_worker.py").read_text(encoding="utf-8")
        self.assertIn('"--prepare-runtime"', worker)
        for name in ("tools/update_worker.py", "tools/install_package.py"):
            self.assertNotIn("powershell", (ROOT / name).read_text(encoding="utf-8").casefold(), name)


class NativeResourceTests(unittest.TestCase):
    def test_runtime_header_carries_the_component_pins(self):
        header = runtime_pin_header(COMPONENTS)
        python = COMPONENTS["python"]
        self.assertIn(f'#define DEKU_PYTHON_ID L"{python["id"]}"', header)
        self.assertIn(f'#define DEKU_PYTHON_SHA256 "{python["sha256"]}"', header)
        self.assertIn(f'#define DEKU_PYTHON_SIZE {python["size"]}ULL', header)
        self.assertIn(f'#define DEKU_PILLOW_SHA256 "{python["pillow"]["sha256"]}"', header)
        self.assertIn(f'#define DEKU_LAUNCHER_VERSION L"{COMPONENTS["launcher"]["version"]}"', header)
        cache = re.search(r'DEKU_PYTHON_CACHE L"([^"]+)"', header)[1]
        self.assertTrue(cache.startswith("cpython-") and "%" not in cache and "/" not in cache)

    def test_runtime_header_refuses_values_that_could_escape_a_literal(self):
        cases = [("url", 'https://example.org/a".tar.gz'), ("url", "http://example.org/a.tar.gz"),
                 ("url", "https://example.org/a\\b.tar.gz"), ("sha256", "A" * 64), ("size", 0),
                 ("size", 10**10), ("url", "https://example.org/%2e%2e")]
        for key, value in cases:
            pins = copy.deepcopy(COMPONENTS)
            pins["python"][key] = value
            with self.assertRaises(ValueError, msg=f"{key}={value!r}"):
                runtime_pin_header(pins)
        pins = copy.deepcopy(COMPONENTS)
        pins["python"]["id"] = 'x"y'
        with self.assertRaises(ValueError):
            runtime_pin_header(pins)

    def test_development_runtime_has_no_download(self):
        pins = copy.deepcopy(COMPONENTS)
        pins["python"] = {"id": "development-interpreter"}
        header = runtime_pin_header(pins)
        self.assertIn('#define DEKU_PYTHON_URL L""', header)
        self.assertIn("#define DEKU_PYTHON_SIZE 0ULL", header)

    def test_digest_header_and_packaged_digest_use_lf_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / "helper.ps1"
            script.write_bytes(b"line one\r\nline two\r\n")
            digest = packaged_sha256(script)
            self.assertEqual(digest, hashlib.sha256(b"line one\nline two\n").hexdigest())
            self.assertIn(f'#define DEKU_TEST_SHA256 "{digest}"', digest_header("DEKU_TEST_SHA256", digest))
        with self.assertRaises(ValueError):
            digest_header("DEKU_TEST", "not-a-digest")

    def test_resources_declare_publisher_version_and_as_invoker(self):
        with tempfile.TemporaryDirectory() as folder:
            icon = Path(folder) / "icon.ico"
            icon.write_bytes(b"synthetic")
            resource = write_resources(folder, "setup", description="DekuForge setup", filename="DekuForge-Setup.exe",
                                       version="0.4.4-experimental.7.1", icon=icon, extra=['102 RCDATA "payload.zip"'])
            text = resource.read_text(encoding="utf-8")
            manifest = (Path(folder) / "setup.manifest").read_text(encoding="utf-8")
        for value in ('"CompanyName", "DekuForge contributors', '"OriginalFilename", "DekuForge-Setup.exe',
                      '"ProductVersion", "0.4.4-experimental.7.1', "FILEVERSION 0,4,4,0", '102 RCDATA "payload.zip"', "1 24 "):
            self.assertIn(value, text)
        self.assertIn('level="asInvoker"', manifest)
        self.assertIn('version="0.4.4.0"', manifest)
        with self.assertRaises(ValueError):
            write_resources(folder, "bad", description='a"b', filename="DekuForge.exe", version="1.0.0", icon=icon)


@unittest.skipUnless(shutil.which("cc") or shutil.which("gcc") or shutil.which("clang"), "host C compiler")
class ArchiveListingTests(unittest.TestCase):
    """bsdtar listings are checked before Windows tar.exe extracts anything."""

    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        base = Path(cls.folder.name)
        (base / "harness.c").write_text(HARNESS, encoding="utf-8")
        compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
        cls.program = base / "harness"
        subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "launcher"),
                        str(base / "harness.c"), str(ROOT / "launcher/archive_check.c"), "-o", str(cls.program)],
                       check=True, timeout=120)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def check(self, names, details=None, entries=100, expanded=1000, prefix=None, newline="\n"):
        if details is None:
            details = [detail(name, 0, "d") if name.endswith("/") else detail(name) for name in names]
        base = Path(self.folder.name)
        (base / "names.txt").write_bytes(newline.join(names).encode("latin-1") + newline.encode())
        (base / "details.txt").write_bytes(newline.join(details).encode("latin-1") + newline.encode())
        args = [str(self.program), str(base / "names.txt"), str(base / "details.txt"), str(entries), str(expanded)]
        result = subprocess.run(args + ([prefix] if prefix else []), check=True, capture_output=True, text=True, timeout=30)
        return result.stdout.strip()

    def test_safe_runtime_and_wheel_listings_are_accepted(self):
        self.assertEqual(self.check(["python/", "python/python.exe", "python/Lib/os.py"], prefix="python/"), "OK")
        self.assertEqual(self.check(["PIL/", "PIL/Image.py", "pillow-12.0.0.dist-info/RECORD"]), "OK")
        self.assertEqual(self.check(["python/", "python/python.exe"], prefix="python/", newline="\r\n"), "OK")

    def test_traversal_absolute_and_reserved_names_are_refused(self):
        for name in ("../evil.py", "python/../../evil", "/etc/passwd", "C:/evil", "a\\b", "a/./b", "a//b",
                     "PIL/CON", "PIL/aux.txt", "PIL/com1", "PIL/name.", "PIL/name ", "PIL/\u00e9.py", "PIL/a*b"):
            self.assertNotEqual(self.check([name]), "OK", name)

    def test_links_devices_and_unknown_formats_are_refused(self):
        for line in (detail("PIL/link", kind="l"), detail("PIL/hard", kind="h"), detail("PIL/dev", kind="c"),
                     "garbage", "-rw-r--r--  x 0 0 10 Nov 10 12:00 PIL/x", "-rw-r--r--  0 0 0 -5 Nov 10 PIL/x"):
            self.assertNotEqual(self.check(["PIL/x"], [line]), "OK", line)

    def test_case_collisions_duplicates_and_folder_aliases_are_refused(self):
        self.assertIn("duplicate", self.check(["PIL/Image.py", "PIL/image.py"]))
        self.assertIn("duplicate", self.check(["PIL/x", "PIL/x"]))
        self.assertIn("duplicate", self.check(["PIL/", "PIL"], [detail("PIL/", 0, "d"), detail("PIL")]))

    def test_bounds_prefix_and_disagreeing_listings_are_refused(self):
        self.assertIn("too many", self.check(["a", "b", "c"], entries=2))
        self.assertIn("beyond", self.check(["a", "b"], [detail("a", 600), detail("b", 600)]))
        self.assertIn("beyond", self.check(["a"], [detail("a", 2**64 - 1)]))
        self.assertIn("outside", self.check(["python/x", "other/x"], prefix="python/"))
        self.assertIn("disagree", self.check(["a", "b"], [detail("a")]))
        self.assertIn("empty", self.check(["a", "", "b"]))
        self.assertIn("empty", self.check([]))
