import unittest

from tools.check_source import forbidden
from tools.maintenance import make_report, summary


class RepositoryPolicyTests(unittest.TestCase):
    def test_game_content_cannot_be_hidden_by_renaming_files(self):
        for path, data in (("notes.txt", b"NUP\x01anything"), ("readme.txt", b"MZanything"),
                           ("module.txt", b"NSO0anything"), ("src/generated.c", b"// DEKUFORGE_RECOMP_GENERATED_FROM_GAME_CODE\n"),
                           ("dump/main", b""), ("data/own.rom", b""), ("code/native.obj", b"")):
            self.assertTrue(forbidden(path, data), path)
        self.assertFalse(forbidden("src/main.c", b"// Original source\nint main(void) { return 0; }"))
        self.assertFalse(forbidden("assets/branding/launcher.ico", b"\0\0\1\0"))

    def test_report_does_not_count_pull_requests_as_issues_or_claim_game_validation(self):
        report = make_report("owner/project", [{"number": 1, "title": "Bug"},
                                               {"number": 2, "title": "PR", "pull_request": {}}],
                             [{"number": 2, "title": "Fix", "draft": True, "mergeable_state": "dirty"}], "success")
        self.assertEqual(len(report["issues"]), 1)
        self.assertEqual(len(report["pull_requests"]), 1)
        self.assertIsNone(report["pull_requests"][0]["mergeable"])
        text = summary(report)
        self.assertIn("not establish a working game", text)
        self.assertIn("mergeability: dirty", text)

    def test_untrusted_issue_titles_remain_data(self):
        report = make_report("owner/project", [{"number": 3, "title": "<script>[click](javascript:bad)\nrun command"}], [])
        text = summary(report)
        self.assertNotIn("<script>", text)
        self.assertNotIn("[click]", text)
        with self.assertRaises(ValueError):
            make_report("owner/project/../../other", [], [])
