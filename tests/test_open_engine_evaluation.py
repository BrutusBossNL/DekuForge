"""Developer evaluation must not reach a compiler through unsafe output/input paths."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import evaluate_open_engine as evaluate


class EvaluationBoundaries(unittest.TestCase):
    def test_paths_exclude_main_and_project_sources(self):
        for path in (evaluate.ROOT, evaluate.ROOT/'build', evaluate.ROOT/'assets',
                     evaluate.ROOT.parent/'DekuForge/build'):
            with self.assertRaises(ValueError):
                evaluate.owned_path(path)

    def test_unowned_work_directory_is_preserved_before_module_import(self):
        build=evaluate.ROOT/'build'
        build.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=build) as directory:
            root=Path(directory).resolve()
            self.assertTrue(root.is_relative_to(build))
            source=root/'source';source.mkdir()
            text=b'original synthetic source\n'
            (source/'LICENSE').write_bytes(text)
            record={'revision':'fixture','files':{'LICENSE':{'size':len(text),
                'sha1':hashlib.sha1(b'blob '+str(len(text)).encode()+b'\0'+text).hexdigest()}}}
            exefs=root/'inputs';exefs.mkdir()
            for name in ('main','main.npdm','rtld','sdk','subsdk0'):
                (exefs/name).write_bytes(b'synthetic fixture, not game data')
            work=root/'work';work.mkdir();(work/'keep.txt').write_text('keep')
            tool=root/'tools';tool.mkdir()
            args=['evaluate','compile','--source',str(source),'--exefs',str(exefs),
                  '--work',str(work),'--toolchain',str(tool),'--deps',str(tool)]
            with patch.object(evaluate,'manifest',return_value=record), patch('sys.argv',args), \
                 patch.object(evaluate.importlib,'import_module') as load:
                with self.assertRaisesRegex(ValueError,'unowned'):
                    evaluate.main()
            load.assert_not_called()
            self.assertEqual((work/'keep.txt').read_text(),'keep')
            self.assertFalse((work/'.dekuforge-open-evaluation.json').exists())
