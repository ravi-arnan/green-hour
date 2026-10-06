/**
 * The structured field entry — the contract between the model and the journal.
 *
 * Port of skills/_lib/greenhour/schema.py. Keeping the shape in one place lets
 * the prompt, the validator and the training data stay in sync.
 */

export interface FieldEntry {
  outdoors: boolean;
  summary: string;
  location: string | null;
  weather: string | null;
  mood: string | null;
  notable: string[];
  species: string[];
}

/** Embedded in the extraction prompt. Keep in sync with `fieldEntryFromDict`. */
export const JSON_SCHEMA = {
  type: "object",
  required: ["outdoors", "summary"],
  properties: {
    outdoors: {
      type: "boolean",
      description: "True only if the speaker is clearly outside during this walk.",
    },
    summary: {
      type: "string",
      description: "One or two sentences, naturalist voice, about the walk.",
    },
    location: { type: ["string", "null"] },
    weather: { type: ["string", "null"] },
    mood: { type: ["string", "null"] },
    notable: { type: "array", items: { type: "string" } },
    species: { type: "array", items: { type: "string" } },
  },
} as const;

const THINK_RE = /<think(?:ing)?>[\s\S]*?<\/think(?:ing)?>/gi;
const FENCE_RE = /```(?:json)?\s*([\s\S]*?)```/;

function asStringList(value: unknown): string[] {
  if (value == null) return [];
  if (typeof value === "string") {
    // Models sometimes emit "a, b, c" instead of a list.
    return value
      .split(/[,\n;]/)
      .map((s) => s.trim())
      .filter(Boolean);
  }
  if (Array.isArray(value)) {
    return value.map((v) => String(v).trim()).filter(Boolean);
  }
  const s = String(value).trim();
  return s ? [s] : [];
}

function asBool(value: unknown): boolean {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    return ["true", "yes", "y", "1", "outdoors", "outside"].includes(value.trim().toLowerCase());
  }
  return Boolean(value);
}

function asOptString(value: unknown): string | null {
  if (value == null) return null;
  const s = String(value).trim();
  return s || null;
}

/** Validate and coerce a decoded object. Throws on anything unusable. */
export function fieldEntryFromDict(data: unknown): FieldEntry {
  if (typeof data !== "object" || data === null || Array.isArray(data)) {
    throw new Error("expected an object");
  }
  const d = data as Record<string, unknown>;
  if (!("outdoors" in d)) throw new Error("missing required field: outdoors");
  const summary = asOptString(d.summary);
  if (!summary) throw new Error("missing required field: summary");
  return {
    outdoors: asBool(d.outdoors),
    summary,
    location: asOptString(d.location),
    weather: asOptString(d.weather),
    mood: asOptString(d.mood),
    notable: asStringList(d.notable),
    species: asStringList(d.species),
  };
}

/** Strip reasoning blocks and markdown fences the model may have added. */
function clean(text: string): string {
  let t = text.replace(THINK_RE, "");
  // Some models open a reasoning block without closing it; drop everything up
  // to and including a stray closing marker.
  t = t.replace(/^[\s\S]*?<\/think(?:ing)?>/i, "");
  const match = FENCE_RE.exec(t);
  return (match?.[1] ?? t).trim();
}

/** Return the first balanced {...} block, ignoring braces inside strings. */
export function firstObject(text: string): string | null {
  return topLevelObjects(text)[0] ?? null;
}

/**
 * Every top-level balanced {...} block, in order.
 *
 * Used because a model that "thinks" may emit braces before the answer; we try
 * the candidates from last to first, which is where the answer normally is.
 */
export function topLevelObjects(text: string): string[] {
  const out: string[] = [];
  let depth = 0;
  let start = -1;
  let inString = false;
  let escaped = false;

  for (let i = 0; i < text.length; i++) {
    const ch = text[i]!;
    if (inString) {
      if (escaped) escaped = false;
      else if (ch === "\\") escaped = true;
      else if (ch === '"') inString = false;
      continue;
    }
    if (ch === '"') inString = true;
    else if (ch === "{") {
      if (depth === 0) start = i;
      depth++;
    } else if (ch === "}") {
      if (depth > 0) {
        depth--;
        if (depth === 0 && start !== -1) {
          out.push(text.slice(start, i + 1));
          start = -1;
        }
      }
    }
  }
  return out;
}

/** Parse a model response into a FieldEntry, tolerating fences and prose. */
export function parseFieldEntry(text: string): FieldEntry {
  const candidates = topLevelObjects(clean(text));
  if (candidates.length === 0) throw new Error("no JSON object found in model output");

  let lastError: Error | undefined;
  for (const candidate of [...candidates].reverse()) {
    try {
      return fieldEntryFromDict(JSON.parse(candidate));
    } catch (err) {
      lastError = err as Error;
    }
  }
  throw new Error(`no usable field entry in model output: ${lastError?.message ?? "unknown"}`);
}
