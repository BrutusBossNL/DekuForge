"""Exercise the real PowerShell setup validator without extracting/installing."""
import ctypes
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import tempfile
import unittest
import zipfile


@unittest.skipUnless(os.name == 'nt' and shutil.which('powershell.exe'), 'Windows PowerShell required')
class SetupPayloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='DekuForge setup payload ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.driver = self.root/'validate.ps1'
        self.driver.write_text(r'''
param([string]$Source, [string]$Cases)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
Add-Type -AssemblyName System.IO.Compression.FileSystem
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile($Source,[ref]$tokens,[ref]$errors)
if ($errors.Count) { throw 'Installer PowerShell syntax errors' }
$definition=$ast.Find({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Get-InstallerStaging'},$true)
if (-not $definition) { throw 'Missing production payload validator' }
. ([scriptblock]::Create($definition.Extent.Text))
$results=@(foreach ($case in (Get-Content -LiteralPath $Cases -Raw | ConvertFrom-Json)) {
    try { $stage=Get-InstallerStaging $case; @{ok=$true;stage=$stage} }
    catch { @{ok=$false;error=$_.Exception.Message} }
})
[Console]::WriteLine((ConvertTo-Json -InputObject $results -Compress))
''', encoding='utf-8')

    def validate(self, paths):
        cases=self.root/'cases.json'
        cases.write_text(json.dumps([str(p) for p in paths]),encoding='utf-8')
        script=Path(__file__).resolve().parents[1]/'installer/install.ps1'
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',
                               '-File',str(self.driver),'-Source',str(script),'-Cases',str(cases)],
                              capture_output=True,text=True,encoding='utf-8',check=True,timeout=30)
        return json.loads(result.stdout)

    def archive(self, filename, entries):
        path=self.root/filename
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as bundle:
            for name in entries:
                bundle.writestr(name,b'synthetic launcher fixture')
        return path

    def test_long_spaced_and_dot_segment_payload_paths_share_canonical_root(self):
        payload=self.archive('launcher.zip',['DekuForge.exe','tools/install_package.py'])
        (self.root/'through').mkdir()
        results=self.validate([payload,self.root/'through/../launcher.zip'])
        for result in results:
            self.assertTrue(result['ok'],result)
            self.assertEqual(Path(result['stage']),self.root/'application')
        self.assertFalse((self.root/'application').exists())

    def test_windows_short_temp_alias_is_accepted_without_extracting(self):
        payload=self.archive('launcher.zip',['DekuForge.exe','tools/install_package.py'])
        buffer=ctypes.create_unicode_buffer(32768)
        if not ctypes.windll.kernel32.GetShortPathNameW(str(payload),buffer,len(buffer)) or '~' not in buffer.value:
            self.skipTest('This volume does not expose 8.3 aliases')
        result=self.validate([buffer.value])[0]
        self.assertTrue(result['ok'],result)
        self.assertEqual(Path(result['stage']).resolve(),self.root/'application')
        self.assertFalse((self.root/'application').exists())

    def test_traversal_absolute_ads_backslash_and_case_aliases_remain_blocked(self):
        names=[['../escape.txt'],['../application-neighbour/escape.txt'],['/absolute.txt'],
               ['C:/absolute.txt'],['tools/file.txt:stream'],['tools\\file.txt'],['tools/A.txt','tools/a.txt']]
        paths=[self.archive(f'bad-{n}.zip',entries) for n,entries in enumerate(names)]
        # ZipInfo normalizes backslashes when creating fixtures on Windows;
        # retain a real backslash entry in both ZIP headers for this case.
        paths[5].write_bytes(paths[5].read_bytes().replace(b'tools/file.txt',b'tools\\file.txt'))
        for path,result in zip(paths,self.validate(paths)):
            self.assertFalse(result['ok'],(path.name,result))
            self.assertIn('Unsafe installer payload',result['error'])
        self.assertFalse((self.root/'application').exists())
        self.assertFalse((self.root/'escape.txt').exists())

    def test_symlink_and_oversize_payload_remain_blocked(self):
        link=zipfile.ZipInfo('tools/link')
        link.create_system=3
        link.external_attr=(stat.S_IFLNK|0o777)<<16
        linked=self.archive('link.zip',[link])
        large=self.archive('large.zip',['oversize.txt'])
        data=bytearray(large.read_bytes())
        central=data.index(b'PK\x01\x02')
        struct.pack_into('<I',data,central+24,257*1024**2)
        struct.pack_into('<I',data,22,257*1024**2)
        large.write_bytes(data)
        for result in self.validate([linked,large]):
            self.assertFalse(result['ok'],result)
            self.assertIn('Unsafe installer payload',result['error'])
