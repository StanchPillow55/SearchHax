"""extract_json_object recovers a JSON object from prose-wrapped model output."""

import json

from exploration.backend.llm import extract_json_object


def test_recovers_object_wrapped_in_prose():
    text = 'Here is the result: {"relationships": [], "gaps": []} hope that helps'
    assert json.loads(extract_json_object(text)) == {"relationships": [], "gaps": []}


def test_recovers_object_in_code_fence():
    text = "```json\n{\"a\": 1}\n```"
    assert json.loads(extract_json_object(text)) == {"a": 1}


def test_braces_inside_strings_do_not_end_the_object():
    text = '{"nested": {"x": "has } brace"}, "ok": true}'
    assert json.loads(extract_json_object(text)) == {"nested": {"x": "has } brace"}, "ok": True}


def test_plain_object_is_unchanged():
    assert json.loads(extract_json_object('{"a": 1}')) == {"a": 1}


def test_truncated_model_output_reports_why_it_failed(monkeypatch):
    """Live run 2026-11-20 recorded only "JSONDecodeError". The blocker now says why, offline."""
    import httpx

    from exploration.backend.extraction import extract_document
    from exploration.backend.llm import OpenAICompatibleClient

    body = {"choices": [{"message": {"content": '{"relationships": [{"subject": "NVIDIA", "quote": "NVIDIA has inv'}, "finish_reason": "length"}]}

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return body

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def post(self, *args, **kwargs):
            return _Response()

    monkeypatch.setattr(httpx, "Client", _Client)
    client = OpenAICompatibleClient(api_key="offline-test-placeholder", base_url="https://api.anthropic.com/v1", timeout=1)
    batch = extract_document(
        "A page about GPU capacity with no disclosed investment sentence.",
        url="https://example.test/page",
        document_id="doc_t",
        version_id="ver_t",
        version_hash="hash_t",
        question="How do NVIDIA's investments reinforce capacity?",
        llm=client,
    )
    assert batch.live_extraction_blocked is True
    assert batch.relationships == []  # nothing is invented from a partial answer
    assert "LLMResponseNotJSON" in batch.blocker
    assert "finish_reason=length" in batch.blocker and "max_tokens=1024" in batch.blocker
