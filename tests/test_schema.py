from __future__ import annotations

import pytest

from greenhour.schema import FieldEntry, parse


def test_parse_plain_json():
    entry = parse('{"outdoors": true, "summary": "A walk."}')
    assert entry.outdoors is True
    assert entry.summary == "A walk."
    assert entry.species == []


def test_parse_fenced_json():
    text = 'Sure!\n```json\n{"outdoors": false, "summary": "At my desk."}\n```\n'
    entry = parse(text)
    assert entry.outdoors is False
    assert entry.summary == "At my desk."


def test_parse_ignores_trailing_prose_and_braces_in_strings():
    text = '{"outdoors": true, "summary": "He said {hello} loudly.", "species": ["magpie"]} hope that helps'
    entry = parse(text)
    assert entry.summary == "He said {hello} loudly."
    assert entry.species == ["magpie"]


def test_coerces_sloppy_field_types():
    entry = parse('{"outdoors": "yes", "summary": "Walk", "species": "magpie, kookaburra"}')
    assert entry.outdoors is True
    assert entry.species == ["magpie", "kookaburra"]


def test_optional_fields_default_to_none():
    entry = parse('{"outdoors": true, "summary": "Walk"}')
    assert entry.location is None
    assert entry.weather is None
    assert entry.mood is None


@pytest.mark.parametrize(
    "text",
    [
        "no json here at all",
        '{"summary": "missing outdoors"}',
        '{"outdoors": true}',
        '{"outdoors": true, "summary": "   "}',
        '{"outdoors": true, "summary": "unterminated',
    ],
)
def test_bad_output_raises(text):
    with pytest.raises(ValueError):
        parse(text)


def test_round_trip():
    entry = FieldEntry(
        outdoors=True,
        summary="River loop.",
        location="the river loop",
        species=["magpie"],
        notable=["first jacaranda blooms"],
    )
    assert FieldEntry.from_dict(entry.to_dict()) == entry
