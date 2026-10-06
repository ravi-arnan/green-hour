import { describe, expect, it } from "vitest";

import {
  addDaysISO,
  computeStreak,
  parseRow,
  summarizeWeek,
  topCounts,
  type Entry,
  type EntryRow,
} from "../src/journal";

const entry = (localDate: string, outdoors: boolean, extra: Partial<Entry> = {}): Entry => ({
  id: 1,
  createdAt: `${localDate}T09:00:00Z`,
  localDate,
  outdoors,
  summary: "Walk",
  location: null,
  weather: null,
  mood: null,
  notable: [],
  species: [],
  source: "voice",
  ...extra,
});

describe("addDaysISO", () => {
  it("moves across month and year boundaries", () => {
    expect(addDaysISO("2026-10-01", -1)).toBe("2026-09-30");
    expect(addDaysISO("2026-01-01", -1)).toBe("2025-12-31");
    expect(addDaysISO("2026-02-28", 1)).toBe("2026-03-01");
  });
});

describe("computeStreak", () => {
  it("counts consecutive days", () => {
    const days = new Set(["2026-10-04", "2026-10-05", "2026-10-06"]);
    expect(computeStreak(days, "2026-10-06")).toBe(3);
  });

  it("survives a quiet morning", () => {
    // No walk yet today: an evening walker shouldn't see the streak reset.
    const days = new Set(["2026-10-04", "2026-10-05"]);
    expect(computeStreak(days, "2026-10-06")).toBe(2);
  });

  it("breaks on a gap", () => {
    const days = new Set(["2026-10-02", "2026-10-03", "2026-10-06"]);
    expect(computeStreak(days, "2026-10-06")).toBe(1);
  });

  it("is zero with no walks", () => {
    expect(computeStreak(new Set(), "2026-10-06")).toBe(0);
  });

  it("is zero when the last walk was two days ago", () => {
    expect(computeStreak(new Set(["2026-10-03"]), "2026-10-06")).toBe(0);
  });
});

describe("topCounts", () => {
  it("orders by count then name", () => {
    expect(topCounts(["magpie", "wren", "magpie"])).toEqual([
      { name: "magpie", count: 2 },
      { name: "wren", count: 1 },
    ]);
  });
});

describe("summarizeWeek", () => {
  it("counts only outdoor walks and aggregates the interesting fields", () => {
    const stats = summarizeWeek(
      [
        entry("2026-10-06", true, { species: ["magpie", "wren"], notable: ["frost"] }),
        entry("2026-10-05", true, { species: ["magpie"] }),
        entry("2026-10-06", false),
      ],
      "2026-09-30",
      "2026-10-06",
    );
    expect(stats.walks).toBe(2);
    expect(stats.daysOut).toBe(2);
    expect(stats.species[0]).toEqual({ name: "magpie", count: 2 });
    expect(stats.notable).toEqual([{ name: "frost", count: 1 }]);
  });
});

describe("parseRow", () => {
  it("decodes JSON columns and the outdoors flag", () => {
    const row: EntryRow = {
      id: 7,
      created_at: "2026-10-06T09:00:00Z",
      local_date: "2026-10-06",
      outdoors: 1,
      summary: "River loop.",
      location: "the river loop",
      weather: null,
      mood: "calm",
      notable: '["first jacaranda blooms"]',
      species: '["magpie"]',
      transcript: null,
      source: "voice",
      model: null,
    };
    const parsed = parseRow(row);
    expect(parsed.outdoors).toBe(true);
    expect(parsed.species).toEqual(["magpie"]);
    expect(parsed.notable).toEqual(["first jacaranda blooms"]);
  });

  it("survives a corrupt JSON column", () => {
    const row = { ...({} as EntryRow), notable: "not json", species: "[]" };
    expect(parseRow(row).notable).toEqual([]);
  });
});
