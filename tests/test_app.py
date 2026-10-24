import json
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app import create_app
from providers import ModelProvider, Settings
from retrieval import RULES


class AppTests(unittest.TestCase):
    def setUp(self):
        self.provider = Mock(chat_enabled=True, embeddings_enabled=True)
        self.provider.complete_json.side_effect = lambda system, rule: {
            "bin": rule["bin"], "prep_step": rule["prep_step"],
            "message": rule["allowed_messages"][0],
        }
        self.client = TestClient(create_app(self.provider))

    def ask(self, item, context="hku_hall"):
        return self.client.post("/ask", json={"item": item, "context": context})

    def test_hazard_gate_prevents_every_model_call(self):
        for item in ("lithium battery", "power    bank", "paintbrush"):
            self.assertEqual(self.ask(item).json()["status"], "refused")
        self.provider.embed.assert_not_called()
        self.provider.complete_json.assert_not_called()

    def test_context_unsupported_and_unknown_do_not_call_llm(self):
        self.assertEqual(self.ask("coffee cup", "epd_smart").json()["status"], "not_covered")
        self.provider.embeddings_enabled = False
        self.assertEqual(self.ask("dinosaur fossil").json()["status"], "not_covered")
        self.provider.complete_json.assert_not_called()

    def test_request_validation(self):
        for item in ("", " \n ", "a" * 501):
            self.assertEqual(self.ask(item).status_code, 422)
        self.assertEqual(self.ask("bottle", "unknown").status_code, 422)
        self.provider.embed.assert_not_called()
        self.provider.complete_json.assert_not_called()

    def test_app_serves_form_and_exact_rule_without_credentials(self):
        client = TestClient(create_app(ModelProvider(Settings())))
        self.assertIn("Hall Recycling Helper", client.get("/").text)
        data = client.post("/ask", json={"item": "water bottle", "context": "hku_hall"}).json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["grounding"], "published_rule")
        self.assertEqual(data["retrieval_method"], "exact")

    def test_single_end_to_end_case_with_mocked_provider_transport(self):
        """Exercise HTTP routing, real provider adapters, retrieval and grounding.

        Only the external HTTP transport is mocked. This is not live API evidence.
        """
        from io import BytesIO

        settings = Settings(llm_api_key="test-chat", llm_base_url="https://chat.example/v1",
                            llm_model="test-chat-model", embedding_api_key="test-embed",
                            embedding_base_url="https://embed.example/v1",
                            embedding_model="test-embedding-model")
        client = TestClient(create_app(ModelProvider(settings)))
        calls = []
        def respond(request, timeout):
            calls.append(request.full_url)
            payload = json.loads(request.data)
            if request.full_url.endswith("/embeddings"):
                rows = []
                for i, text in enumerate(payload["input"]):
                    matches = text.startswith("plastic bottle;") or text == "plastic beverage bottle"
                    rows.append({"index": i, "embedding": [1, 0] if matches else [0, 1]})
                data = {"data": rows}
            else:
                self.assertNotIn("plastic beverage bottle", payload["messages"][1]["content"])
                rule = json.loads(payload["messages"][1]["content"])
                content = {"bin": rule["bin"], "prep_step": rule["prep_step"],
                           "message": rule["allowed_messages"][1]}
                data = {"choices": [{"message": {"content": json.dumps(content)}}]}
            return BytesIO(json.dumps(data).encode())

        with patch("providers.urlopen", side_effect=respond):
            response = client.post("/ask", json={"item": "plastic beverage bottle", "context": "hku_hall"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["matched_item"], "plastic bottle")
        self.assertEqual(data["retrieval_method"], "embedding")
        self.assertEqual(data["grounding"], "llm")
        self.assertEqual(data["bin"], RULES[0]["hku_hall_bin"])
        self.assertEqual(data["prep_step"], RULES[0]["prep_step"])
        self.assertEqual(data["source_url"], RULES[0]["hku_source_url"])
        self.assertEqual(data["date_checked"], RULES[0]["date_checked"])
        self.assertEqual(len(calls), 5)  # Three rule batches, one query, one chat.


if __name__ == "__main__":
    unittest.main()
