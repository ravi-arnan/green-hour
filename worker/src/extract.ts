/**
 * Turning a walk's transcript into a FieldEntry.
 *
 * Runs on Workers AI, which serves open-weight models on the free daily
 * allowance — so the default path needs no API key at all. A `tinker` backend
 * is intentionally left as a seam: the fine-tuned adapter produced by
 * train/train_tinker.py is the same shape of call, just a different endpoint.
 */

import { DEFAULT_MODEL } from "./env";
import { JSON_SCHEMA, parseFieldEntry, type FieldEntry } from "./schema";

export const SYSTEM_PROMPT =
  "You turn a short, messy spoken voice note from a walk into one structured " +
  "field-journal entry. Transcription noise, filler words and half sentences " +
  "are expected; infer politely and never invent specifics that were not said. " +
  "Write the summary in a warm, plain naturalist's voice, first person, one or " +
  "two sentences. Set outdoors=true only when the speaker is plainly outside " +
  "(weather, birds, being on a trail, etc.); if they are indoors or it is " +
  "ambiguous, set it false. Return JSON only.";

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export function buildMessages(transcript: string): ChatMessage[] {
  return [
    { role: "system", content: SYSTEM_PROMPT },
    {
      role: "user",
      content:
        `Voice note transcript:\n"""\n${transcript.trim()}\n"""\n\n` +
        `Return one JSON object matching this schema:\n${JSON.stringify(JSON_SCHEMA)}`,
    },
  ];
}

export interface ExtractResult {
  entry: FieldEntry;
  model: string;
  raw: string;
}

/** Chat models on Workers AI return `{ response: string }`. */
function textOf(output: unknown): string {
  if (typeof output === "string") return output;
  if (output && typeof output === "object") {
    const o = output as Record<string, unknown>;
    if (typeof o.response === "string") return o.response;
    if (typeof o.result === "string") return o.result;
  }
  throw new Error("unexpected Workers AI response shape");
}

export async function extract(
  ai: Ai,
  transcript: string,
  model: string = DEFAULT_MODEL,
): Promise<ExtractResult> {
  const output = await ai.run(model as never, {
    messages: buildMessages(transcript),
    max_tokens: 400,
    temperature: 0.2,
  } as never);

  const raw = textOf(output);
  return { entry: parseFieldEntry(raw), model, raw };
}
