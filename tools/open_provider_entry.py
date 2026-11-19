"""Fresh-process entry for the pinned experimental GPL builder and its children.

This composes owned build orchestration with the provider's public Python CLI;
original source files are not rewritten. Only explicitly owned build paths run.
"""
import importlib
import os
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'local/devdeps')]
sys.dont_write_bytecode = True


def main():
    from dekuforge.open_engine import manifest, verify_tree
    source = Path(os.environ['DEKUFORGE_OPEN_SOURCE']).absolute()
    work = Path(os.environ['DEKUFORGE_OPEN_WORK']).absolute()
    output = Path(os.environ['DEKUFORGE_OPEN_OUTPUT']).absolute()
    for path in (source, work, output):
        if path.resolve() != path or not path.is_relative_to(ROOT/'build') or path == ROOT/'build':
            raise ValueError('Provider paths must stay in this independent build folder')
    if any(source.is_relative_to(p) or p.is_relative_to(source) for p in (work, output)):
        raise ValueError('Provider source cannot overlap generated output')
    record = manifest('hookshot')
    verify_tree(source, record)
    script = Path(sys.argv[1]).absolute()
    if (script.parent != source/'nx2' or script.suffix != '.py' or not script.is_file()
            or script.relative_to(source).as_posix() not in record['files']):
        raise ValueError('Only a verified provider CLI can be invoked')
    sys.path.insert(0, str(source/'nx2'))
    sys.argv = [str(script), *sys.argv[2:]]
    if script.name == 'build.py':
        module = importlib.import_module('build')
        from dekuforge.open_engine_branding import configure
        configure(module, source, work)
        return module.main()
    if script.name == 'make_game.py':
        module = importlib.import_module('make_game')
        import hashlib
        from dekuforge import open_engine_cheat_lift
        lift_key = module.lift_key
        hook_source = Path(open_engine_cheat_lift.__file__).read_bytes()

        def key_with_hooks(*args, **kwargs):
            return hashlib.sha1(lift_key(*args, **kwargs).encode() + hook_source,
                                usedforsecurity=False).hexdigest()

        module.lift_key = key_with_hooks
        module.LANGUAGES = [*module.LANGUAGES, ('system', 'System language')]
        build_language = module.build_language

        def select_language(args, folder):
            if not args.language and not module.folder_language(folder):
                return 'system'
            return build_language(args, folder)

        module.build_language = select_language
        # Child interpreters also receive branding and the explicit local deps.
        module.PY = [sys.executable, '-B', '-u', str(Path(__file__).resolve())]
        # Never let an upstream convenience routine end another game process.
        module.end_stale_games = lambda paths: []
        original_clear = module.clear_folder

        def clear_owned(path):
            target = Path(path).absolute()
            if target.resolve() != target or not any(target.is_relative_to(p) and target != p for p in (work, output)):
                raise ValueError('Refusing to clear an unowned provider path')
            if target.exists():
                for child in target.rglob('*'):
                    if child.is_symlink() or getattr(child, 'is_junction', lambda: False)():
                        raise ValueError('Refusing to clear a linked provider tree')
            return original_clear(path)

        module.clear_folder = clear_owned
        result = module.main()
        if not result and (output/'prompts/rsizetable.zs').is_file():
            from dekuforge.world_assets import prepare
            prepare(output, output/'romfs', lambda kind, line: print(line, end='', flush=True))
        return result
    if script.name == 'lift.py':
        importlib.import_module('kit')
        fov = importlib.import_module('oot_fov')
        from dekuforge.open_engine_cheat_lift import install
        original_install = fov.install

        def install_with_cheats(lifter, image, build_id):
            install(lifter, image, build_id)
            return original_install(lifter, image, build_id)

        fov.install = install_with_cheats
    runpy.run_path(str(script), run_name='__main__')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
