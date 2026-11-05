"""Thin JSON-only LLM wrapper. Every call returns a dict.

Offline mode returns canned replies keyed by (step, domain) so the whole pipeline
can be demoed and tested without keys.
"""
import json
import re

from . import config


class LLMError(RuntimeError):
    pass


def _canned(step, domain):
    data = json.loads(config.CANNED_LLM.read_text())
    try:
        return data[step][domain]
    except KeyError:
        raise LLMError(f"no canned reply for step={step} domain={domain}")


def _parse(text):
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise LLMError(f"model did not return JSON: {text[:200]}")
    return json.loads(m.group(0))


def _gemini(prompt):
    from google import genai

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    resp = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=prompt,
        config={"temperature": config.TEMPERATURE, "response_mime_type": "application/json"},
    )
    return resp.text


def _anthropic(prompt):
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=1500,
        temperature=config.TEMPERATURE,
        system="Reply with a single JSON object and nothing else.",
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


def ask(step, domain, prompt):
    if config.OFFLINE:
        return _canned(step, domain)
    call = _anthropic if config.LLM_PROVIDER == "anthropic" else _gemini
    last = None
    for _ in range(2):  # one retry on malformed JSON
        try:
            return _parse(call(prompt))
        except (json.JSONDecodeError, LLMError) as e:
            last = e
    raise LLMError(f"{step}/{domain}: {last}")
