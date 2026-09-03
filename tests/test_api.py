import unittest

from product_engineering.api import OpenAIClient, OpenAIError, extract_output_text


class ApiTests(unittest.TestCase):
    def test_extract_output_text_skips_tool_items(self) -> None:
        response = {
            "output": [
                {"type": "web_search_call", "id": "search_1"},
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": '{"ok": true}'}],
                },
            ]
        }
        self.assertEqual(extract_output_text(response), '{"ok": true}')

    def test_create_json_uses_schema_and_web_search(self) -> None:
        captured = {}

        def requester(url, payload, headers, timeout):
            captured.update(url=url, payload=payload, headers=headers, timeout=timeout)
            return {
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": '{"value": "done"}'}],
                    }
                ],
            }

        client = OpenAIClient(api_key="test-key", requester=requester)
        schema = {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        }
        result = client.create_json(
            prompt="test",
            schema=schema,
            schema_name="test_schema",
            use_web_search=True,
        )
        self.assertEqual(result, {"value": "done"})
        self.assertEqual(captured["url"], "https://api.openai.com/v1/responses")
        self.assertEqual(captured["payload"]["text"]["format"]["schema"], schema)
        self.assertEqual(captured["payload"]["tools"][0]["type"], "web_search_preview")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer test-key")

    def test_retries_rate_limit(self) -> None:
        attempts = 0
        sleeps = []

        def requester(url, payload, headers, timeout):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                error = OpenAIError("rate limited")
                error.status_code = 429
                error.retry_after = "0.1"
                raise error
            return {"output_text": '{"ok": true}'}

        client = OpenAIClient(
            api_key="test-key",
            requester=requester,
            sleeper=sleeps.append,
        )
        result = client.create_json(
            prompt="test",
            schema={"type": "object"},
            schema_name="retry",
        )
        self.assertEqual(result, {"ok": True})
        self.assertEqual(attempts, 2)
        self.assertEqual(sleeps, [0.1])


if __name__ == "__main__":
    unittest.main()
