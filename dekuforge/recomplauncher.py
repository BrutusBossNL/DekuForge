"""Build and play a RecompLauncher-managed copy with DekuForge's existing backend."""

import argparse
from contextlib import closing
import os
from pathlib import Path
import shutil
import subprocess
import sys

from . import COMPONENTS
from .core import ROOT
from .gameplan import TITLE
from .nup import Archive
from .open_engine_runtime import launch_options
from .open_game_build import owned
from .update_package import atomic_json
from .update_status import read_record


def input_archive(filename):
    archive = Archive(filename)
    if not any(item.title == TITLE and item.kind == 0 for item in archive.packages):
        raise ValueError("Pick your own Ocarina of Time Switch NUP with the 1.1.1 update.")
    updates = sorted((item for item in archive.packages if item.title == TITLE + 0x800 and item.kind == 1),
                     key=lambda item: item.version, reverse=True)
    if updates:
        main = dict(archive.tree(updates[0].exefs)).get(Path("main")) if updates[0].exefs != 0xffffffff else None
        if main:
            with closing(archive.chunks(main)) as chunks:
                header = next(chunks, b"")
            if header[:4] == b"NSO0" and header[64:96].hex().startswith("e0f3ccfaf50065ae4ea01eb5aeb13b1a"):
                return archive
    raise ValueError("This NUP does not have the supported Ocarina of Time 1.1.1 executable.")


def progress(fraction, message):
    print(f"progress {fraction:g} {message}", flush=True)


def build_output(index):
    if not isinstance(index, str) or len(index) != 64 or any(c not in "0123456789abcdef" for c in index):
        raise ValueError("The RecompLauncher build receipt is missing or invalid. Run Set Up again.")
    return owned(ROOT / "build/recomplauncher" / index[:24], ROOT / "build")


def prepared_game(index):
    output = build_output(index)
    game = output / "DekuForgeGame.exe"
    if game.is_file() and (output / ".dekuforge-native").is_file() and launch_options(game) is not None:
        return game
    return None


def build_identity():
    return {name: COMPONENTS[name]["version"] for name in ("engine", "buildkit")}


def prepare(filename, receipt):
    progress(0, "Checking your NUP")
    archive = input_archive(filename)
    identity = {"nup": archive.index_sha256, "size": archive.size, **build_identity()}
    if read_record(receipt) == identity:
        try:
            if prepared_game(identity["nup"]):
                progress(1, "Already built")
                return 0
        except (OSError, ValueError):
            pass
    receipt.unlink(missing_ok=True)
    progress(0.01, "Preparing verified Windows build tools")
    subprocess.run([sys.executable, "-B", str(ROOT / "tools/prepare_installation.py")], cwd=ROOT, check=True)
    from .independent_engine import build

    def notify(kind, value):
        if kind == "log":
            if value.startswith("progress "):
                parts = value.split(maxsplit=2)
                if len(parts) == 3:
                    try:
                        fraction = float(parts[1])
                    except ValueError:
                        fraction = -1
                    if 0 <= fraction <= 1:
                        progress(0.05 + 0.85 * fraction, parts[2].strip())
                        return
            print(value.rstrip(), flush=True)

    progress(0.05, "Building the game locally")
    build(str(archive.path), notify, build_output(identity["nup"]))
    atomic_json(receipt, identity)
    progress(1, "Game ready")
    return 0


def play(data, receipt):
    recorded = read_record(receipt)
    if any(recorded.get(name) != version for name, version in build_identity().items()):
        raise ValueError("This release needs a local build. Run Set Up again.")
    game = prepared_game(recorded.get("nup"))
    if game is None:
        raise ValueError("The locally built game is missing. Run Set Up again.")
    from .open_engine_mods import prepare_mods
    from .reports import read_log
    options = prepare_mods(game, launch_options(game))
    user = owned(data / "user", ROOT)
    user.mkdir(exist_ok=True)
    options["args"][-1] = str(user)
    shared_settings = owned(data / "hookshot_options.ini", ROOT)
    game_settings = owned(game.parent / shared_settings.name, ROOT / "build")
    if shared_settings.is_file():
        shutil.copyfile(shared_settings, game_settings)
    code = subprocess.run(options["args"], cwd=game.parent, env=options["env"]).returncode
    if game_settings.is_file():
        temporary = owned(shared_settings.with_suffix(".tmp"), ROOT)
        shutil.copyfile(game_settings, temporary)
        temporary.replace(shared_settings)
    try:
        log = game.parent / "hookshot_log.txt"
        if log.is_file() and not log.is_symlink():
            destination = owned(data / "logs/game.log", ROOT)
            destination.parent.mkdir(exist_ok=True)
            destination.write_text(read_log(log), encoding="utf-8")
    except (OSError, ValueError) as error:
        print(f"DekuForge could not preserve the last game log: {error}", file=sys.stderr)
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--recomp-prepare", action="store_true")
    action.add_argument("--recomp-play", action="store_true")
    parser.add_argument("--game", type=Path)
    args = parser.parse_args()
    if os.name != "nt" or os.environ.get("RECOMPLAUNCHER") != "1":
        parser.error("Use these actions from RecompLauncher on Windows.")
    if args.recomp_prepare != (args.game is not None):
        parser.error("Set Up requires --game with your own .nup.")
    try:
        data = ROOT / "recompdata"
        if Path(os.environ.get("RECOMPLAUNCHER_DATA", "")).resolve() != data:
            raise ValueError("RecompLauncher must use the recompdata folder in this installation.")
        data = owned(data, ROOT)
        data.mkdir(exist_ok=True)
        receipt = owned(data / "dekuforge-ready.json", ROOT)
        import msvcrt
        with owned(data / "session.lock", ROOT).open("a+b") as lock:
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise ValueError("Close the running DekuForge game or setup and try again.") from None
            return prepare(args.game, receipt) if args.recomp_prepare else play(data, receipt)
    except subprocess.CalledProcessError as error:
        print(f"DekuForge could not prepare the build tools (exit {error.returncode}). See the lines above.", file=sys.stderr)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"DekuForge: {error}", file=sys.stderr)
    return 1
