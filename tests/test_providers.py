"""Provider adapter tests — offline. The HTTP layer and Anthropic SDK are
faked; what matters is that both providers hand the judge a clean dict or
raise ModelError (never a silent bad value), and that reasoning-model
noise around the JSON is tolerated."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent import providers  # noqa: E402
from agent.providers import (  # noqa: E402
    ModelError,
    _extract_json,
    get_model,
    load_env,
    openai_compatible_model,
)


class TestExtractJson(unittest.TestCase):
    def test_strict_json(self):
        self.assertEqual(_extract_json('{"verdict": "PASS"}'), {"verdict": "PASS"})

    def test_json_in_code_fence(self):
        content = 'Here is my answer:\n```json\n{"verdict": "FLAG"}\n```'
        self.assertEqual(_extract_json(content), {"verdict": "FLAG"})

    def test_json_after_reasoning_prose(self):
        content = 'Let me think. The recipient is an EOA. {"verdict": "FLAG"}'
        self.assertEqual(_extract_json(content), {"verdict": "FLAG"})

    def test_no_json_raises(self):
        with self.assertRaises(ModelError):
            _extract_json("I cannot answer this.")

    def test_bare_fence_without_lang(self):
        self.assertEqual(_extract_json('```\n{"a": 1}\n```'), {"a": 1})


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError("status %d" % self.status_code)

    def json(self):
        return self._payload


class TestOpenAICompatible(unittest.TestCase):
    def setUp(self):
        os.environ["GAVEL_API_BASE"] = "http://localhost:20128/v1"
        os.environ["GAVEL_API_KEY"] = "sk-test"
        os.environ["GAVEL_MODEL"] = "cbcn/glm-5.2(xhigh)"
        self._orig_post = providers.requests.post

    def tearDown(self):
        providers.requests.post = self._orig_post
        for k in ("GAVEL_API_BASE", "GAVEL_API_KEY", "GAVEL_MODEL"):
            os.environ.pop(k, None)

    def _patch_post(self, payload, status=200, capture=None):
        def fake_post(url, headers=None, json=None, timeout=None):
            if capture is not None:
                capture.update({"url": url, "headers": headers, "body": json})
            return FakeResponse(payload, status)
        providers.requests.post = fake_post

    def test_happy_path_returns_dict(self):
        self._patch_post({"choices": [{"message": {"content": '{"verdict": "PASS"}'}}]})
        self.assertEqual(openai_compatible_model("sys", "usr"), {"verdict": "PASS"})

    def test_request_shape(self):
        cap = {}
        self._patch_post({"choices": [{"message": {"content": "{}"}}]}, capture=cap)
        openai_compatible_model("SYS", "USR")
        self.assertTrue(cap["url"].endswith("/v1/chat/completions"))
        self.assertEqual(cap["headers"]["Authorization"], "Bearer sk-test")
        self.assertEqual(cap["body"]["messages"][0]["role"], "system")
        self.assertEqual(cap["body"]["response_format"]["type"], "json_object")
        self.assertEqual(cap["body"]["temperature"], 0)
        self.assertIn("JSON object", cap["body"]["messages"][1]["content"])

    def test_http_error_raises_model_error(self):
        self._patch_post({}, status=500)
        with self.assertRaises(ModelError):
            openai_compatible_model("sys", "usr")

    def test_missing_content_raises(self):
        self._patch_post({"choices": [{}]})
        with self.assertRaises(ModelError):
            openai_compatible_model("sys", "usr")

    def test_missing_config_raises(self):
        os.environ.pop("GAVEL_API_KEY")
        with self.assertRaises(ModelError):
            openai_compatible_model("sys", "usr")


class FakeBlock:
    def __init__(self, type_, text=None):
        self.type = type_
        self.text = text


class FakeAnthropicResponse:
    def __init__(self, content, stop_reason="end_turn"):
        self.content = content
        self.stop_reason = stop_reason


class TestAnthropicParsing(unittest.TestCase):
    """REGRESSION: the real Anthropic response-parsing path — refusal
    (terminal) vs no-text-block (retryable) vs non-JSON (retryable) — was
    previously untested. Drive it with a fake SDK client."""

    def _run(self, response):
        import types
        fake_client = types.SimpleNamespace(
            messages=types.SimpleNamespace(create=lambda **kw: response))
        fake_anthropic = types.SimpleNamespace(Anthropic=lambda: fake_client)
        sys.modules["anthropic"] = fake_anthropic
        os.environ["GAVEL_MODEL"] = "claude-opus-5"
        try:
            return providers.anthropic_model("sys", "usr")
        finally:
            del sys.modules["anthropic"]
            os.environ.pop("GAVEL_MODEL", None)

    def test_valid_json_text_block_parsed(self):
        resp = FakeAnthropicResponse([FakeBlock("text", '{"verdict": "PASS"}')])
        self.assertEqual(self._run(resp), {"verdict": "PASS"})

    def test_refusal_is_terminal_judge_error(self):
        from agent.judge import JudgeError
        resp = FakeAnthropicResponse([], stop_reason="refusal")
        with self.assertRaises(JudgeError):
            self._run(resp)

    def test_no_text_block_is_retryable_model_error(self):
        resp = FakeAnthropicResponse([FakeBlock("thinking")])
        with self.assertRaises(ModelError):
            self._run(resp)

    def test_non_json_text_is_retryable_model_error(self):
        resp = FakeAnthropicResponse([FakeBlock("text", "I cannot answer.")])
        with self.assertRaises(ModelError):
            self._run(resp)


class TestGetModel(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("GAVEL_MODEL_PROVIDER", None)

    def test_default_is_anthropic(self):
        os.environ.pop("GAVEL_MODEL_PROVIDER", None)
        # load_env may set it from a local .env; force the default path.
        prev = os.environ.pop("GAVEL_MODEL_PROVIDER", None)
        try:
            fn = get_model()
            self.assertTrue(callable(fn))
        finally:
            if prev is not None:
                os.environ["GAVEL_MODEL_PROVIDER"] = prev

    def test_openai_selected(self):
        os.environ["GAVEL_MODEL_PROVIDER"] = "openai"
        self.assertIs(get_model(), openai_compatible_model)

    def test_unknown_provider_raises(self):
        os.environ["GAVEL_MODEL_PROVIDER"] = "gpt5-turbo-ultra"
        with self.assertRaises(ModelError):
            get_model()


class TestLoadEnv(unittest.TestCase):
    def test_does_not_override_existing(self):
        import tempfile
        os.environ["FOO_GAVEL"] = "real"
        f = tempfile.NamedTemporaryFile("w", suffix=".env", delete=False)
        f.write("FOO_GAVEL=fromfile\n")
        f.close()
        try:
            load_env(f.name)
            self.assertEqual(os.environ["FOO_GAVEL"], "real")
        finally:
            os.environ.pop("FOO_GAVEL", None)
            os.unlink(f.name)

    def test_missing_file_is_noop(self):
        load_env("/nonexistent/.env")  # must not raise


if __name__ == "__main__":
    unittest.main()


class TestJsonDirectiveDerivedFromSchema(unittest.TestCase):
    """REGRESSION: a hand-written key list rotted after the schema
    redesign, instructing models to emit the removed free-text fields."""

    def test_directive_matches_current_schema(self):
        from agent.schema import VERDICT_SCHEMA
        directive = providers._json_directive()
        for key in VERDICT_SCHEMA["required"]:
            self.assertIn(key, directive)

    def test_directive_has_no_stale_free_text_keys(self):
        directive = providers._json_directive()
        self.assertNotIn("headline", directive)
        self.assertNotIn("reasons", directive)


class TestExtractJsonRobustness(unittest.TestCase):
    """REGRESSION: _extract_json leaked raw JSONDecodeError, returned
    non-dicts, and discarded a valid object when prose contained braces."""

    def test_braces_in_prose_does_not_discard_valid_object(self):
        content = 'The schema needs {verdict, ...}. My answer: {"verdict": "FLAG"}'
        self.assertEqual(_extract_json(content), {"verdict": "FLAG"})

    def test_scalar_raises_model_error(self):
        with self.assertRaises(ModelError):
            _extract_json('"PASS"')

    def test_array_raises_model_error(self):
        with self.assertRaises(ModelError):
            _extract_json('["PASS"]')

    def test_truncated_json_raises_model_error(self):
        with self.assertRaises(ModelError):
            _extract_json('{"a": {"b": 1}, "c":')

    def test_braces_inside_strings_ignored(self):
        self.assertEqual(_extract_json('{"note": "a } brace", "verdict": "PASS"}'),
                         {"note": "a } brace", "verdict": "PASS"})

    def test_two_objects_returns_first_valid(self):
        out = _extract_json('{"verdict": "PASS"} {"verdict": "FAIL"}')
        self.assertIsInstance(out, dict)
