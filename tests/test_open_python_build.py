from importlib.metadata import PackageNotFoundError
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dekuforge.open_python_build import PACKAGES, provision


class OwnedPythonDependenciesTests(unittest.TestCase):
    def test_missing_dependencies_never_install_into_external_interpreter(self):
        with (patch('dekuforge.open_python_build.version', side_effect=PackageNotFoundError('fixture')),
              patch('dekuforge.open_python_build.sys.executable', str(Path(__file__).resolve().parent/'external-python.exe')),
              patch('dekuforge.open_python_build.subprocess.run') as run):
            with self.assertRaisesRegex(RuntimeError, 'external Python is never modified'):
                provision()
            run.assert_not_called()

    def test_only_owned_interpreter_receives_hash_enforced_binary_wheels(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve()
            own=root/'python/fixture/python.exe'
            own.parent.mkdir(parents=True)
            own.touch()
            (own.parent/'.dekuforge-runtime.json').write_text('{}')
            calls = iter([PackageNotFoundError('fixture') for _ in PACKAGES] + list(PACKAGES.values()))
            def package_version(name):
                result=next(calls)
                if isinstance(result,Exception):
                    raise result
                return result
            with (patch('dekuforge.open_python_build.ROOT',root),
                  patch('dekuforge.open_python_build.COMPONENTS',{'python':{'id':'fixture'}}),
                  patch('dekuforge.open_python_build.sys.executable',str(own)),
                  patch('dekuforge.open_python_build.version',side_effect=package_version),
                  patch('dekuforge.open_python_build.subprocess.run') as run):
                provision(lambda line: None)
                arguments=run.call_args.args[0]
                self.assertEqual(arguments[0],str(own))
                self.assertIn('--require-hashes',arguments)
                self.assertIn('--only-binary=:all:',arguments)


class RequirementsMatchPackagesTests(unittest.TestCase):
    def test_every_provisioned_package_is_hash_pinned_to_the_checked_version(self):
        text = (Path(__file__).resolve().parents[1]/'requirements-open-engine.txt').read_text(encoding='utf-8')
        pins = {}
        for line in text.splitlines():
            if line.strip() and not line.startswith('#'):
                spec, *options = line.split()
                name, version = spec.split('==')
                self.assertTrue(any(option.startswith('--hash=sha256:') for option in options), name)
                pins[name.lower()] = version
        self.assertEqual(pins, {name.lower(): version for name, version in PACKAGES.items()})

    def test_instruction_lifter_disassembler_is_provisioned(self):
        # nx2/lift.py imports capstone at module load; without it the translation step fails at once.
        self.assertEqual(PACKAGES['capstone'], '5.0.9')
