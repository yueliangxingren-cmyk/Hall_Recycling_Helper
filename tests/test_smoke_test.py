from contextlib import redirect_stdout
from io import BytesIO, StringIO
import json
import unittest
from unittest.mock import patch

from retrieval import RULES
from scripts.smoke_test import main


class SmokeRunnerTests(unittest.TestCase):
    def response(self, method, grounding):
        rule = RULES[0]
        return {
            "status": "ok", "matched_item": rule["item"],
            "bin": rule["hku_hall_bin"], "prep_step": rule["prep_step"],
            "source_url": rule["hku_source_url"], "date_checked": rule["date_checked"],
            "retrieval_method": method, "grounding": grounding,
            "similarity": 0.95 if method == "embedding" else None,
        }

    def run_case(self, flags, data):
        with patch("sys.argv", ["smoke_test.py", *flags]), patch(
            "scripts.smoke_test.urlopen", return_value=BytesIO(json.dumps(data).encode())
        ) as send, redirect_stdout(StringIO()):
            code = main()
        return code, json.loads(send.call_args.args[0].data)

    def test_chat_only_mode_requires_llm_and_uses_exact_item(self):
        code, request = self.run_case(["--exact"], self.response("exact", "llm"))
        self.assertEqual(code, 0)
        self.assertEqual(request["item"], "plastic bottle")
        code, _ = self.run_case(["--exact"], self.response("exact", "published_rule"))
        self.assertEqual(code, 1)

    def test_default_requires_semantic_retrieval_and_live_grounding(self):
        for method, grounding, expected in (
            ("embedding", "llm", 0), ("exact", "llm", 1),
            ("embedding", "published_rule", 1),
        ):
            with self.subTest(method=method, grounding=grounding):
                code, request = self.run_case([], self.response(method, grounding))
                self.assertEqual(code, expected)
                self.assertEqual(request["item"], "plastic beverage bottle")

    def test_offline_mode_allows_published_rule_fallback(self):
        code, _ = self.run_case(["--offline"], self.response("exact", "published_rule"))
        self.assertEqual(code, 0)

    def test_in_process_offline_runs_real_app_without_provider_calls(self):
        with patch("sys.argv", ["smoke_test.py", "--offline", "--in-process"]), patch(
            "providers.urlopen", side_effect=AssertionError("Offline test contacted provider")
        ), redirect_stdout(StringIO()) as output:
            code = main()
        self.assertEqual(code, 0)
        self.assertIn('"grounding": "published_rule"', output.getvalue())
        self.assertIn('"matched_item": "plastic bottle"', output.getvalue())

    def test_in_process_live_mode_does_not_pass_without_chat_credentials(self):
        from providers import Settings

        with patch("sys.argv", ["smoke_test.py", "--exact", "--in-process"]), patch(
            "providers.Settings.from_env", return_value=Settings()
        ), redirect_stdout(StringIO()) as output:
            code = main()
        self.assertEqual(code, 1)
        self.assertIn("FAIL: validated live LLM", output.getvalue())

    def test_non_object_response_fails_cleanly(self):
        code, _ = self.run_case([], [])
        self.assertEqual(code, 1)

    def test_non_finite_similarity_fails(self):
        data = self.response("embedding", "llm")
        data["similarity"] = float("inf")
        code, _ = self.run_case([], data)
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
