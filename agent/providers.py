"""Model providers for the judge.

The judge treats the model as a swappable, potentially-compromised
component: the safety gates (schema, deny-list, clamp) live outside the
model and hold regardless of which provider answers. So the provider is
pure configuration.

Two providers ship:
- `anthropic`  — Claude via the Anthropic SDK, native structured output.
- `openai`     — any OpenAI-compatible endpoint (CodeBuddy CN, OpenRouter,
                 vLLM, …) via plain HTTP. Covers GLM / Kimi / DeepSeek /
                 MiniMax and anything else behind a /v1/chat/completions
                 route.

Selection is by env var so no code changes when switching:
    GAVEL_MODEL_PROVIDER  anthropic | openai   (default: anthropic)
    GAVEL_MODEL           model id
    GAVEL_API_BASE        base url incl. /v1    (openai provider)
    GAVEL_API_KEY         api key               (openai provider)

Both providers return a parsed dict; the judge validates it against the
verdict schema and retries, so a provider that returns slightly-off JSON
degrades into a retry rather than a bad verdict.
"""

import json
import os
import re

import requests

from .schema import VERDICT_SCHEMA

DEFAULT_ANTHROPIC_MODEL = "claude-opus-5"


def _json_directive() -> str:
    """Derive the key list from VERDICT_SCHEMA so the instruction can never
    drift from the contract the validator enforces. A hand-written copy
    silently rots the moment the schema changes — and the tempting fix
    for the resulting failures is to loosen validation, which is exactly
    the wrong direction."""
    keys = ", ".join(VERDICT_SCHEMA["required"])
    return ("\n\nReturn ONLY a single minified JSON object with exactly "
            "these keys: %s. No other keys, no prose, no code fences." % keys)


class ModelError(Exception):
    """Transport/parse failure. The judge retries, then fails closed."""


# -- .env loader (dependency-free) -------------------------------------------

def load_env(path: str = ".env") -> None:
    """Populate os.environ from a .env file if present. Never overrides an
    already-set variable, so real environment wins over the file."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


# -- JSON extraction ----------------------------------------------------------

def _balanced_objects(content: str):
    """Yield every brace-balanced candidate object, longest-first per start.

    Reasoning models emit prose that contains braces ("the schema needs
    {verdict, ...}"), so a naive first-brace/last-brace span captures
    garbage and discards a perfectly good answer. Scanning for balanced
    spans (ignoring braces inside strings) finds the real object.
    """
    depth = 0
    start = None
    in_string = False
    escape = False
    for i, ch in enumerate(content):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth:
                depth -= 1
                if depth == 0 and start is not None:
                    yield content[start:i + 1]
                    start = None


def _extract_json(content: str) -> dict:
    """Parse a JSON *object* from a chat completion.

    Always returns a dict or raises ModelError — never a scalar, list, or
    a raw JSONDecodeError, so the caller's contract holds and the judge
    treats failures as retryable rather than crashing.
    """
    content = content.strip()
    candidates = [content]
    fence = re.search(r"```(?:json)?\s*(.+?)\s*```", content, re.DOTALL)
    if fence:
        candidates.append(fence.group(1).strip())
    candidates.extend(_balanced_objects(content))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise ModelError("no JSON object in model response")


# -- providers ----------------------------------------------------------------

def anthropic_model(system_prompt: str, user_prompt: str) -> dict:
    import anthropic

    from .judge import JudgeError

    client = anthropic.Anthropic()
    model = os.environ.get("GAVEL_MODEL", DEFAULT_ANTHROPIC_MODEL)
    resp = client.messages.create(
        model=model,
        max_tokens=1024,
        system=[{"type": "text", "text": system_prompt,
                 "cache_control": {"type": "ephemeral"}}],
        output_config={"format": {"type": "json_schema", "schema": VERDICT_SCHEMA}},
        messages=[{"role": "user", "content": user_prompt}],
    )
    if getattr(resp, "stop_reason", None) == "refusal":
        raise JudgeError("model refused to judge this launch")  # terminal
    text = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), None)
    if text is None:
        raise ModelError("model returned no text block")  # retryable
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ModelError("model text was not JSON: %s" % e)  # retryable


def openai_compatible_model(system_prompt: str, user_prompt: str) -> dict:
    base = os.environ.get("GAVEL_API_BASE")
    key = os.environ.get("GAVEL_API_KEY")
    model = os.environ.get("GAVEL_MODEL")
    if not (base and key and model):
        raise ModelError("GAVEL_API_BASE, GAVEL_API_KEY, GAVEL_MODEL must be set")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt + _json_directive()},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }
    try:
        resp = requests.post(
            base.rstrip("/") + "/chat/completions",
            headers={"Authorization": "Bearer %s" % key,
                     "Content-Type": "application/json"},
            json=payload, timeout=120,
        )
        resp.raise_for_status()
        body = resp.json()
    except (requests.RequestException, json.JSONDecodeError) as e:
        raise ModelError("request failed: %s" % e)

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise ModelError("unexpected response shape: %s" % e)
    if not content:
        raise ModelError("empty completion content")
    return _extract_json(content)


PROVIDERS = {
    "anthropic": anthropic_model,
    "openai": openai_compatible_model,
}


def get_model():
    """Resolve the model function from GAVEL_MODEL_PROVIDER."""
    load_env()
    name = os.environ.get("GAVEL_MODEL_PROVIDER", "anthropic").lower()
    if name not in PROVIDERS:
        raise ModelError("unknown provider %r (choose from %s)"
                         % (name, sorted(PROVIDERS)))
    return PROVIDERS[name]
