/**
 * Валидация Telegram Web App initData.
 *
 * Схема (по документации Telegram):
 *   1. secret_key = HMAC_SHA256(key="WebAppData", message=bot_token)
 *   2. hash       = HMAC_SHA256(key=secret_key, message=data_check_string)
 *
 * data_check_string — отсортированные по алфавиту пары key=value,
 * разделённые переносом строки, без поля hash.
 */

async function hmacSha256Hex(key: string, message: string): Promise<string> {
  const enc = new TextEncoder();
  const keyData = await crypto.subtle.importKey(
    "raw",
    enc.encode(key),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign("HMAC", keyData, enc.encode(message));
  return [...new Uint8Array(signature)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export async function validateInitData(token: string, initData: string): Promise<boolean> {
  if (!initData) return false;

  const params = new URLSearchParams(initData);
  const hash = params.get("hash");
  if (!hash) return false;

  params.delete("hash");

  const dataCheckString = [...params.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, value]) => `${key}=${value}`)
    .join("\n");

  const secretKey = await hmacSha256Hex("WebAppData", token);
  const calculatedHash = await hmacSha256Hex(secretKey, dataCheckString);

  return calculatedHash === hash;
}