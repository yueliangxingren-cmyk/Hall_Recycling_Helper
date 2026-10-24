from io import BytesIO
import json
import socket
import ssl
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from providers import ModelProvider, ProviderError, Settings


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.provider = ModelProvider(Settings(
            llm_api_key="test-chat-key", llm_base_url="https://chat.example/v1",
            llm_model="test-chat-model",
            embedding_api_key="test-embedding-key", embedding_base_url="https://embed.example/v1",
            embedding_model="test-embedding-model",
        ))

    @patch("providers.urlopen")
    def test_embedding_batches_reorders_and_uses_separate_endpoint(self, send):
        def response(request, timeout):
            self.assertEqual(request.full_url, "https://embed.example/v1/embeddings")
            self.assertEqual(request.get_header("Authorization"), "Bearer test-embedding-key")
            self.assertEqual(timeout, 15)
            texts = json.loads(request.data)["input"]
            self.assertLessEqual(len(texts), 10)
            return BytesIO(json.dumps({"data": [
                {"index": i, "embedding": [i + 1, 1]} for i in reversed(range(len(texts)))
            ]}).encode())
        send.side_effect = response
        result = self.provider.embed([f"item {i}" for i in range(23)])
        self.assertEqual(len(result), 23)
        self.assertEqual(send.call_count, 3)
        self.assertEqual(result[0], [1, 1])

    @patch("providers.urlopen")
    def test_malformed_embeddings_are_rejected(self, send):
        invalid_rows = [
            [], [{"index": 1, "embedding": [1, 0]}],
            [{"index": 0, "embedding": [0, 0]}],
            [{"index": 0, "embedding": [float("nan"), 1]}],
            [{"index": 0, "embedding": [True, 1]}],
            [{"index": 0, "embedding": "not a vector"}],
        ]
        for rows in invalid_rows:
            with self.subTest(rows=rows):
                send.return_value = BytesIO(json.dumps({"data": rows}).encode())
                with self.assertRaises(ProviderError):
                    self.provider.embed(["item"])

    @patch("providers.urlopen")
    def test_chat_uses_json_mode_and_correct_credentials(self, send):
        send.return_value = BytesIO(json.dumps({"choices": [{"message": {"content": '{"message": "ok"}'}}]}).encode())
        self.assertEqual(self.provider.complete_json("rules only", {"item": "bottle"}), {"message": "ok"})
        request = send.call_args.args[0]
        self.assertEqual(request.full_url, "https://chat.example/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-chat-key")
        self.assertEqual(json.loads(request.data)["response_format"], {"type": "json_object"})
        self.assertNotIn("enable_thinking", json.loads(request.data))

    @patch("providers.urlopen")
    def test_provider_errors_and_malformed_chat_are_sanitized(self, send):
        send.side_effect = URLError("secret or upstream error")
        with self.assertRaisesRegex(ProviderError, "^Provider request failed$"):
            self.provider.embed(["item"])
        send.side_effect = None
        for payload in ([], {}, {"choices": []}, {"choices": [{"message": {"content": "not JSON"}}]}):
            with self.subTest(payload=payload):
                send.return_value = BytesIO(json.dumps(payload).encode())
                with self.assertRaises(ProviderError):
                    self.provider.complete_json("rules only", {})

    def test_no_credentials_means_no_provider_calls(self):
        provider = ModelProvider(Settings())
        self.assertFalse(provider.chat_enabled)
        self.assertFalse(provider.embeddings_enabled)
        with self.assertRaises(ProviderError):
            provider.embed(["item"])

    def test_key_alone_does_not_enable_an_unknown_provider(self):
        provider = ModelProvider(Settings(llm_api_key="test", embedding_api_key="test"))
        self.assertFalse(provider.chat_enabled)
        self.assertFalse(provider.embeddings_enabled)

    @patch("providers.urlopen")
    def test_http_diagnostics_report_status_without_exposing_upstream_data(self, send):
        for status, code in ((400, "invalid_request"), (401, "authentication_error"),
                             (403, "access_denied"), (404, "not_found"),
                             (429, "rate_limit"), (503, "service_error")):
            with self.subTest(status=status):
                send.side_effect = HTTPError(
                    "https://private.example/secret", status, "sensitive upstream message",
                    {}, BytesIO(b'{"error":{"message":"test-chat-key"}}'),
                )
                with self.assertRaises(ProviderError) as caught:
                    self.provider.complete_json("rules only", {})
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(caught.exception.status_code, status)
                diagnostic = caught.exception.diagnostic
                self.assertIn(f"HTTP {status}", diagnostic)
                for secret in ("private.example", "test-chat-key", "sensitive upstream message"):
                    self.assertNotIn(secret, diagnostic)

    @patch("providers.urlopen")
    def test_network_diagnostics_distinguish_dns_timeout_and_tls(self, send):
        for failure, code in (
            (URLError(socket.gaierror("sensitive DNS message")), "dns_error"),
            (URLError(TimeoutError("sensitive timeout message")), "timeout"),
            (TimeoutError("sensitive timeout message"), "timeout"),
            (URLError(ssl.SSLError("sensitive TLS message")), "tls_error"),
        ):
            with self.subTest(code=code):
                send.side_effect = failure
                with self.assertRaises(ProviderError) as caught:
                    self.provider.complete_json("rules only", {})
                self.assertEqual(caught.exception.code, code)
                self.assertNotIn("sensitive", caught.exception.diagnostic)

    @patch("providers.urlopen")
    def test_chat_identifies_truncated_and_invalid_json(self, send):
        for choice, code in (
            ({"finish_reason": "length", "message": {"content": ""}}, "output_truncated"),
            ({"finish_reason": "content_filter", "message": {"content": None}}, "content_filtered"),
            ({"finish_reason": "stop", "message": {"content": "not JSON"}}, "invalid_json"),
        ):
            with self.subTest(code=code):
                send.return_value = BytesIO(json.dumps({"choices": [choice]}).encode())
                with self.assertRaises(ProviderError) as caught:
                    self.provider.complete_json("rules only", {})
                self.assertEqual(caught.exception.code, code)


if __name__ == "__main__":
    unittest.main()
