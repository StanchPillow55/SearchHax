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
