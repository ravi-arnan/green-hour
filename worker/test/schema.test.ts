import { describe, expect, it } from "vitest";

import { fieldEntryFromDict, firstObject, parseFieldEntry } from "../src/schema";

// Built from parts: the closing slash is easy to lose in source.
const OPEN = "<" + "think" + ">";
const CLOSE = "<" + "/" + "think" + ">";

describe("parseFieldEntry", () => {
  it("parses plain JSON", () => {
    const entry = parseFieldEntry('{"outdoors": true, "summary": "A walk."}');
    expect(entry.outdoors).toBe(true);
    expect(entry.summary).toBe("A walk.");
    expect(entry.species).toEqual([]);
  });

  it("unwraps fenced JSON with leading prose", () => {
    const entry = parseFieldEntry('Sure!\n```json\n{"outdoors": false, "summary": "At my desk."}\n```\n');
    expect(entry.outdoors).toBe(false);
    expect(entry.summary).toBe("At my desk.");
  });

  it("ignores braces inside strings and trailing prose", () => {
    const entry = parseFieldEntry(
      '{"outdoors": true, "summary": "He said {hello} loudly.", "species": ["magpie"]} hope that helps',
    );
    expect(entry.summary).toBe("He said {hello} loudly.");
    expect(entry.species).toEqual(["magpie"]);
  });

  it("drops a closed reasoning block that contains braces", () => {
    const raw =
      OPEN + 'the user said {maybe} this is indoors...' + CLOSE +
      '{"outdoors": true, "summary": "River loop."}';
    expect(parseFieldEntry(raw).summary).toBe("River loop.");
  });

  it("still finds the answer when reasoning is never closed", () => {
    // No CLOSE tag at all: the candidate scan takes the last object.
    const raw = OPEN + 'hmm, {maybe} let me think. ' + '{"outdoors": true, "summary": "Ridge track."}';
    expect(parseFieldEntry(raw).summary).toBe("Ridge track.");
  });

  it("coerces sloppy field types", () => {
    const entry = parseFieldEntry('{"outdoors": "yes", "summary": "Walk", "species": "magpie, kookaburra"}');
    expect(entry.outdoors).toBe(true);
    expect(entry.species).toEqual(["magpie", "kookaburra"]);
  });

  it("defaults optional fields to null", () => {
    const entry = parseFieldEntry('{"outdoors": true, "summary": "Walk"}');
    expect(entry.location).toBeNull();
    expect(entry.weather).toBeNull();
    expect(entry.mood).toBeNull();
  });

  it.each([
    "no json here at all",
    '{"summary": "missing outdoors"}',
    '{"outdoors": true}',
    '{"outdoors": true, "summary": "   "}',
    '{"outdoors": true, "summary": "unterminated',
  ])("rejects unusable output: %s", (text) => {
    expect(() => parseFieldEntry(text)).toThrow();
  });
});

describe("fieldEntryFromDict", () => {
  it("rejects non-objects", () => {
    expect(() => fieldEntryFromDict("nope")).toThrow();
    expect(() => fieldEntryFromDict([])).toThrow();
  });

  it("treats a null list as empty", () => {
    const entry = fieldEntryFromDict({ outdoors: false, summary: "Indoors.", notable: null });
    expect(entry.notable).toEqual([]);
  });
});

describe("firstObject", () => {
  it("returns null when there is no object", () => {
    expect(firstObject("nothing here")).toBeNull();
  });

  it("returns the first balanced object only", () => {
    expect(firstObject('prefix {"a": 1} then {"b": 2}')).toBe('{"a": 1}');
  });
});
