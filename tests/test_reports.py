import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit
from dekuforge import reports


class ReportTests(unittest.TestCase):
    def context(self):
        return {"metadata":{"system":{"os":"Windows 11 build test","cpu":"Test CPU","gpus":[{"model":"Test GPU","driver":"1.2.3"}],"ram_gib":32}},
                "logs":[{"name":"game.log","text":"FATAL: synthetic graphics failure\n"}]}

    def test_redaction_removes_credentials_paths_and_email_but_keeps_urls(self):
        raw='C:\\Users\\Alice\\game\\crash.log\nAuthorization: Bearer secret\nghp_1234567890abcdef\nalice@example.test\nhttps://github.com/BrutusBossNL/DekuForge'
        clean=reports.sanitize(raw)
        for private in ("Alice","Bearer secret","ghp_1234567890abcdef","alice@example.test"):
            self.assertNotIn(private,clean)
        self.assertIn("https://github.com/BrutusBossNL/DekuForge",clean)

    def test_collect_includes_hardware_versions_and_only_bounded_text_logs(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();game=root/"game";(game/"logs").mkdir(parents=True)
            (game/"game.exe").write_bytes(b"MZ never read")
            (game/"own.nup").write_bytes(b"NUP\1 never included")
            (game/"logs/game.log").write_text("start\n"+"line\n"*10000+"FATAL tail\n",encoding="utf-8")
            (game/"logs/renamed.log").write_bytes(b"NUP\1\0binary data")
            with patch.object(reports,"hardware",return_value=self.context()["metadata"]["system"]):
                result=reports.collect(root,str(game/"game.exe"))
            self.assertEqual(result["metadata"]["system"]["cpu"],"Test CPU")
            self.assertEqual(result["metadata"]["system"]["gpus"][0]["driver"],"1.2.3")
            self.assertIn("launcher",result["metadata"]["versions"])
            self.assertEqual(len(result["logs"]),1)
            self.assertIn("FATAL tail",result["logs"][0]["text"])
            self.assertLess(len(result["logs"][0]["text"]),17000)

    def test_browser_issue_contains_description_hardware_and_log_excerpt(self):
        draft={"title":"Graphics failure","details":"Steps to reproduce","expected":"Visible terrain","include_logs":True}
        url=reports.browser_url(draft,self.context())
        self.assertLessEqual(len(url),7500)
        query=parse_qs(urlsplit(url).query)
        self.assertIn("Test GPU",query["body"][0])
        self.assertIn("FATAL",query["body"][0])
        self.assertEqual(query["title"],["Graphics failure"])
        draft["include_logs"]=False
        self.assertNotIn("synthetic graphics failure",reports.body(draft,self.context()))
        draft["details"]="a"*100000
        self.assertIn("Test GPU",parse_qs(urlsplit(reports.browser_url(draft,self.context())).query)["body"][0])

    def test_direct_submission_posts_reviewed_text_without_any_file_upload(self):
        draft={"title":"Crash","details":"Reproduction","expected":"No crash","include_logs":True}
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.read.return_value=json.dumps({"html_url":"https://github.com/BrutusBossNL/DekuForge/issues/123"}).encode()
        with patch.object(reports,"github_token",return_value="test-token"),patch.object(reports,"build_opener") as opener:
            opener.return_value.open.return_value=response
            url=reports.submit(draft,self.context())
            request=opener.return_value.open.call_args.args[0]
            self.assertEqual(request.method,"POST")
            self.assertEqual(request.full_url,"https://api.github.com/repos/BrutusBossNL/DekuForge/issues")
            posted=json.loads(request.data)
            self.assertIn("Test CPU",posted["body"])
            self.assertIn("FATAL",posted["body"])
            self.assertNotIn("test-token",posted["body"])
            self.assertEqual(url,"https://github.com/BrutusBossNL/DekuForge/issues/123")

    def test_submission_requires_description_and_existing_authentication(self):
        with self.assertRaisesRegex(ValueError,"report_required"):reports.body({"title":"","details":""},self.context())
        with patch.object(reports,"github_token",return_value=None),patch.object(reports,"build_opener") as opener:
            with self.assertRaisesRegex(ValueError,"report_signin"):reports.submit({"title":"Crash","details":"test"},self.context())
            opener.assert_not_called()

    def test_nonzero_game_exit_is_detected_without_inferring_a_crash_from_normal_exit(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();process=Mock(pid=123)
            reports.record_run(root,process,"game.exe")
            self.assertIsNone(reports.record_exit(root,0))
            self.assertIsNone(reports.previous_incident(root))
            incident=reports.record_exit(root,3221225477)
            self.assertEqual(incident["exit_code"],3221225477)
            self.assertEqual(reports.previous_incident(root)["exit_code"],3221225477)

    def test_fast_fail_reports_recent_vulkan_import_errors(self):
        import os
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            logs = root/"game"
            logs.mkdir()
            executable = logs/"DekuForgeGame.exe"
            log = logs/"nx2navi.log"
            log.write_text("vk: pool 0x1000: host memory import failed (-1000072003)\n", encoding="utf-8")
            os.utime(log, (1000, 1000))
            reports.record_run(root, Mock(pid=123), executable)
            self.assertNotIn("gpu_memory_import_errors", reports.record_exit(root, 3221226505))

            reports.record_run(root, Mock(pid=124), executable)
            log.write_text("vk: pool 0x1000: not imported (VkResult -1000072003)\n", encoding="utf-8")
            started = log.stat().st_mtime + 2
            os.utime(log, (started, started))
            incident = reports.record_exit(root, -1073740791)
            self.assertEqual(incident["windows_status"], "0xC0000409")
            self.assertEqual(incident["gpu_memory_import_errors"], 1)
            self.assertEqual(reports.previous_incident(root), incident)
            self.assertTrue(reports.can_retry_copied_buffers(root, executable))
            reports.record_run(root, Mock(pid=125), executable, copied_gpu_buffers=True)
            reports.record_exit(root, -1073740791)
            self.assertFalse(reports.can_retry_copied_buffers(root, executable))
