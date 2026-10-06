/**
 * Telegram Bot API helpers.
 *
 * The Worker receives updates by webhook (there is no process to long-poll),
 * and downloads voice notes itself before handing them to Whisper.
 */

const API = "https://api.telegram.org";

export interface TgFileRef {
  file_id: string;
  mime_type?: string;
  duration?: number;
}

export interface TgMessage {
  message_id: number;
  from?: { id: number };
  chat: { id: number };
  text?: string;
  voice?: TgFileRef;
  audio?: TgFileRef;
  document?: TgFileRef;
}

export interface TgUpdate {
  update_id: number;
  message?: TgMessage;
  edited_message?: TgMessage;
}

async function call(token: string, method: string, body?: unknown): Promise<unknown> {
  const res = await fetch(`${API}/bot${token}/${method}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  const data = (await res.json()) as { ok: boolean; result?: unknown; description?: string };
  if (!data.ok) throw new Error(`telegram ${method}: ${data.description ?? res.status}`);
  return data.result;
}

export async function sendMessage(token: string, chatId: string | number, text: string): Promise<void> {
  await call(token, "sendMessage", {
    chat_id: chatId,
    text,
    disable_web_page_preview: true,
  });
}

/** Resolve a file_id to a downloadable path (valid for at least an hour). */
export async function getFilePath(token: string, fileId: string): Promise<string> {
  const result = (await call(token, "getFile", { file_id: fileId })) as { file_path?: string };
  if (!result?.file_path) throw new Error("telegram getFile returned no file_path");
  return result.file_path;
}

export async function downloadFile(token: string, filePath: string): Promise<ArrayBuffer> {
  const res = await fetch(`${API}/file/bot${token}/${filePath}`);
  if (!res.ok) throw new Error(`telegram download ${res.status}`);
  return res.arrayBuffer();
}

/** The first attachment reference on a message, if any. */
export function attachmentOf(message: TgMessage): TgFileRef | undefined {
  return message.voice ?? message.audio ?? message.document;
}
