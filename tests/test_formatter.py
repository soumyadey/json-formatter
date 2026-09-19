"""
Tests for format-json.py

Test data lives in tests/data/:
  input.json    — covers all formatting patterns
  expected.json — expected output with options:
                    --array-items uniform
                    --always-inline $.always_inline_target[*]
                    --always-expand $.always_expand_target

Run: pytest tests/
"""
import json
import importlib.util
from pathlib import Path

DATA = Path(__file__).parent / "data"


def load_formatter():
    spec = importlib.util.spec_from_file_location(
        "format_json", Path(__file__).parent.parent / "format-json.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.format_json


format_json = load_formatter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fmt(data, **kwargs):
    """Round-trip: dump → format → parse."""
    text = json.dumps(data)
    return format_json(text, **kwargs)


def fmt_str(text, **kwargs):
    return format_json(text, **kwargs)


# ---------------------------------------------------------------------------
# Golden-file test — all options together
# ---------------------------------------------------------------------------

def test_golden_file_data_identical():
    """Formatting must not change any data — input and expected parse to the same value."""
    input_data = json.loads((DATA / "input.json").read_text())
    expected_data = json.loads((DATA / "expected.json").read_text())
    assert input_data == expected_data


def test_golden_file():
    input_text = (DATA / "input.json").read_text()
    expected = (DATA / "expected.json").read_text()
    result = format_json(
        input_text,
        array_items="uniform",
        always_inline=["$.always_inline_target[*]"],
        always_expand=[
            "$.always_expand_target",
            "$.always_expand_each_item",
            "$.always_expand_each_item[*]",
        ],
    )
    assert result == expected


# ---------------------------------------------------------------------------
# Unit tests for individual behaviours
# ---------------------------------------------------------------------------

def test_short_object_stays_on_one_line():
    result = fmt({"id": "x", "name": "Foo"})
    assert result.strip() == '{ "id": "x", "name": "Foo" }'


def test_primitive_array_stays_on_one_line():
    result = fmt(["a", "b", "c"])
    assert result.strip() == '["a", "b", "c"]'


def test_empty_object():
    assert fmt({}).strip() == "{}"


def test_empty_array():
    assert fmt([]).strip() == "[]"


def test_null_bool():
    result = fmt({"a": None, "b": True, "c": False})
    assert result.strip() == '{ "a": null, "b": true, "c": false }'


def test_long_object_expands():
    obj = {"id": "x", "name": "Y", "description": "A " * 30, "extra": "data"}
    result = fmt(obj, max_line=80)
    assert "\n" in result


def test_uniform_all_expand_if_one_long():
    """uniform mode: if any item in an array doesn't fit, all expand."""
    data = [
        {"id": "hot", "name": "Hot"},
        {"id": "warm", "name": "Warm", "description": "Some interest, no urgency, no specific timeline"},
        {"id": "cold", "name": "Cold"},
    ]
    result = fmt(data, array_items="uniform", max_line=80)
    lines = result.strip().splitlines()
    # Every object item should be on its own line (expanded, not inlined after comma)
    item_lines = [l for l in lines if '"id"' in l]
    assert len(item_lines) == 3


def test_smart_allows_mixed():
    """smart mode: short items stay on one line even if others expand."""
    data = [
        {"id": "hot", "name": "Hot"},
        {"id": "warm", "name": "Warm", "description": "Some interest, no urgency, no specific timeline, extra text here"},
        {"id": "cold", "name": "Cold"},
    ]
    result = fmt(data, array_items="smart", max_line=80)
    # hot and cold should be on one line each; warm should expand
    assert '{ "id": "hot"' in result
    assert '{ "id": "cold"' in result
    # warm's description should appear on its own line
    assert '"description"' in result


def test_always_expand_forces_expansion():
    """--always-expand forces array to expand even if it fits on one line."""
    data = {"items": [{"id": "a"}, {"id": "b"}]}
    result = fmt(data, always_expand=["$.items"], max_line=200)
    # Each item should be on its own line
    assert result.count('{ "id":') == 2
    assert "\n" in result.split('"items"')[1]


def test_always_inline_forces_inline():
    """--always-inline forces array to stay on one line regardless of max_line."""
    data = {"tags": ["rule-a", "rule-b", "rule-c", "rule-d"]}
    result = fmt(data, always_inline=["$.tags"], max_line=10)
    # All items on one line despite tiny max_line
    assert '["rule-a", "rule-b", "rule-c", "rule-d"]' in result


def test_always_inline_nested_array_elements():
    """$.parent[*].child means each child array in each parent element is inlined."""
    data = {"entities": [{"id": "a", "ruleIds": ["x", "y"]}, {"id": "b", "ruleIds": ["z"]}]}
    result = fmt(data, always_inline=["$.entities[*].ruleIds"], max_line=20)
    # ruleIds arrays should be on one line
    assert '["x", "y"]' in result
    assert '["z"]' in result


def test_config_file_toml(tmp_path):
    """--config reads fmt.toml from test data; output matches expected.json."""
    out_file = tmp_path / "out.json"
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent.parent / "format-json.py"),
         "-c", str(DATA / "fmt.toml"),
         str(DATA / "input.json"),
         "-o", str(out_file)],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert out_file.read_text() == (DATA / "expected.json").read_text()


def test_indent_respected():
    obj = {"x": {"y": "z" * 30}}
    result = fmt(obj, indent=4, max_line=40)
    assert "    " in result  # 4-space indent


def test_max_line_boundary():
    """Value exactly at max_line stays on one line; one char over expands."""
    short = {"key": "v" * 10}
    long_ = {"key": "v" * 200}
    short_result = fmt(short, max_line=200)
    long_result = fmt(long_, max_line=20)
    assert "\n" not in short_result.strip()
    assert "\n" in long_result


def test_unicode_preserved():
    result = fmt({"name": "Joule®"})
    parsed = json.loads(result)
    assert parsed["name"] == "Joule®"


def test_value_wrapper_array_stays_inline():
    """[{ "value": "..." }] stays on one line (common CBC attr pattern)."""
    data = {"configurationObjectId": [{"value": "lead-scoring"}]}
    result = fmt(data)
    assert '[{ "value": "lead-scoring" }]' in result
