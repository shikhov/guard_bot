/**
 * guard-bot для Cloudflare Workers.
 *
 * TypeScript-версия: вместо aiogram + FastAPI используем чистый fetch API.
 * Telegram работает с ботом через webhook, а не через polling.
 *
 * Всё приложение лежит в одной точке входа src/index.ts.
 */
import { validateInitData } from "./validation";

interface Env {
  TOKEN: string;
  CF_WORKER_URL?: string;
}

const ALLOWED_UPDATES = ["chat_join_request"];

// --- Telegram API helpers ---------------------------------------------------

async function telegramApi<T>(token: string, method: string, body?: unknown): Promise<T> {
  const res = await fetch(`https://api.telegram.org/bot${token}/${method}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = (await res.json()) as { ok: boolean; result?: T; description?: string };
  if (!data.ok) {
    throw new Error(`Telegram API ${method} failed: ${data.description ?? "unknown error"}`);
  }
  return data.result as T;
}

interface WebhookInfo {
  url: string;
}

async function getWebhookInfo(token: string): Promise<WebhookInfo> {
  return telegramApi<WebhookInfo>(token, "getWebhookInfo");
}

async function setWebhook(token: string, url: string): Promise<void> {
  await telegramApi(token, "setWebhook", {
    url,
    allowed_updates: ALLOWED_UPDATES,
    drop_pending_updates: true,
  });
}

async function answerChatJoinRequestQuery(token: string, queryId: string): Promise<void> {
  await telegramApi(token, "answerChatJoinRequestQuery", {
    chat_join_request_query_id: queryId,
    result: "approve",
  });
}

async function sendChatJoinRequestWebApp(
  token: string,
  queryId: string,
  webAppUrl: string,
): Promise<void> {
  await telegramApi(token, "sendChatJoinRequestWebApp", {
    chat_join_request_query_id: queryId,
    web_app_url: webAppUrl,
  });
}

// --- Webhook setup ----------------------------------------------------------

async function setupWebhook(env: Env, baseUrl: string): Promise<{ ok: boolean; changed: boolean; url: string }> {
  const webhookUrl = `${baseUrl}/webhook`;
  try {
    const info = await getWebhookInfo(env.TOKEN);
    if (info.url === webhookUrl) {
      return { ok: true, changed: false, url: info.url };
    }
    await setWebhook(env.TOKEN, webhookUrl);
    return { ok: true, changed: true, url: webhookUrl };
  } catch (err) {
    console.error("Failed to configure webhook:", err);
    return { ok: false, changed: false, url: webhookUrl };
  }
}

// --- HTML page --------------------------------------------------------------

const JOIN_REQUEST_HTML = `<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Вход</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        :root {
            --text-color: #f8fafc;
            --panel-border: rgba(255, 255, 255, 0.16);
            --button-shadow: rgba(20, 184, 166, 0.34);
            --button-disabled: #526073;
        }

        * {
            box-sizing: border-box;
        }

        body {
            min-height: 100vh;
            margin: 0;
            font-family: "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            color: var(--text-color);
            background:
                linear-gradient(125deg, rgba(14, 165, 233, 0.22) 0%, transparent 34%),
                linear-gradient(235deg, rgba(20, 184, 166, 0.2) 0%, transparent 38%),
                linear-gradient(160deg, #060b14 0%, #0b1220 48%, #17111f 100%);
            background-attachment: fixed;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
            overflow: hidden;
        }

        body::before {
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            background-image:
                linear-gradient(rgba(255, 255, 255, 0.055) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255, 255, 255, 0.055) 1px, transparent 1px);
            background-size: 38px 38px;
            mask-image: linear-gradient(to bottom, rgba(0, 0, 0, 0.88), transparent 82%);
        }

        body::after {
            content: "";
            position: fixed;
            inset: auto -15% -28% -15%;
            height: 48vh;
            pointer-events: none;
            background: linear-gradient(90deg, rgba(14, 165, 233, 0.2), rgba(20, 184, 166, 0.24), rgba(245, 158, 11, 0.16));
            filter: blur(58px);
            opacity: 0.9;
        }

        .join-request {
            width: 100%;
            max-width: 380px;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 22px;
            text-align: center;
            position: relative;
            z-index: 1;
            padding: 34px 24px 28px;
            border: 1px solid var(--panel-border);
            border-radius: 8px;
            background:
                linear-gradient(180deg, rgba(255, 255, 255, 0.13), rgba(255, 255, 255, 0.06)),
                rgba(8, 14, 28, 0.68);
            box-shadow: 0 26px 70px rgba(0, 0, 0, 0.38), inset 0 1px 0 rgba(255, 255, 255, 0.14);
            backdrop-filter: blur(18px);
        }

        .join-request::before {
            content: "";
            width: 54px;
            height: 5px;
            border-radius: 999px;
            background: linear-gradient(90deg, #22d3ee, #818cf8, #f59e0b);
            box-shadow: 0 0 24px rgba(34, 211, 238, 0.45);
        }

        h1 {
            margin: 0;
            max-width: 100%;
            font-size: 29px;
            line-height: 1.2;
            font-weight: 750;
            overflow-wrap: anywhere;
            text-shadow: 0 12px 34px rgba(0, 0, 0, 0.32);
        }

        button {
            width: 100%;
            min-height: 52px;
            border: 0;
            border-radius: 14px;
            color: #ffffff;
            background: linear-gradient(135deg, #0ea5e9 0%, #14b8a6 48%, #f59e0b 128%);
            font-size: 16px;
            font-weight: 750;
            cursor: pointer;
            letter-spacing: 0;
            box-shadow: 0 18px 42px var(--button-shadow), inset 0 1px 0 rgba(255, 255, 255, 0.32);
            position: relative;
            overflow: hidden;
            transition: box-shadow 0.2s, filter 0.2s, transform 0.2s;
        }

        button::before {
            content: "";
            position: absolute;
            inset: 0;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
            transform: translateX(-120%);
            transition: transform 0.45s;
        }

        button:hover:not(:disabled) {
            box-shadow: 0 22px 54px rgba(14, 165, 233, 0.34), inset 0 1px 0 rgba(255, 255, 255, 0.38);
            filter: saturate(1.1) brightness(1.04);
            transform: translateY(-2px);
        }

        button:hover:not(:disabled)::before {
            transform: translateX(120%);
        }

        button:focus-visible {
            outline: 3px solid rgba(34, 211, 238, 0.38);
            outline-offset: 4px;
        }

        button:disabled {
            background: var(--button-disabled);
            box-shadow: none;
            cursor: not-allowed;
            transform: none;
        }

        .status-message {
            min-height: 22px;
            font-size: 15px;
            line-height: 1.45;
            color: #5eead4;
            text-shadow: 0 0 18px rgba(94, 234, 212, 0.22);
        }
    </style>
</head>
<body>
    <main class="join-request">
        <h1 id="welcomeTitle">Добро пожаловать</h1>
        <button id="loginButton" type="button">Войти</button>
        <div class="status-message" id="statusMessage" aria-live="polite"></div>
    </main>

    <script>
        const webApp = window.Telegram && window.Telegram.WebApp;
        const initData = webApp ? webApp.initData : "";
        const loginButton = document.getElementById("loginButton");
        const statusMessage = document.getElementById("statusMessage");
        const welcomeTitle = document.getElementById("welcomeTitle");
        var url = new URL(window.location.href);
        var answerJoinRequestUrl = url.origin + '/answer_join_request';
        const urlParams = new URLSearchParams(window.location.search);
        const queryId = urlParams.get("query_id") || "";
        const chatTitle = urlParams.get("title") || "";

        if (chatTitle) {
            welcomeTitle.textContent = \`Добро пожаловать в чат "\${chatTitle}"!\`;
        }

        if (webApp) {
            webApp.ready();
        }

        loginButton.addEventListener("click", async () => {
            loginButton.disabled = true;

            try {
                const response = await fetch(answerJoinRequestUrl, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        "_auth": initData,
                        "query_id": queryId,
                    }),
                });

                if (response.status !== 200) {
                    throw new Error("Request failed");
                }

                startCloseCountdown();
            } catch (error) {
                console.error(error);
                loginButton.disabled = false;
            }
        });

        function startCloseCountdown() {
            let secondsLeft = 3;

            statusMessage.textContent = \`Успешно! Страница закроется через \${secondsLeft} секунд\`;

            const countdownTimer = window.setInterval(() => {
                secondsLeft -= 1;

                if (secondsLeft > 0) {
                    statusMessage.textContent = \`Успешно! Страница закроется через \${secondsLeft} секунд\`;
                    return;
                }

                window.clearInterval(countdownTimer);

                if (webApp) {
                    webApp.close();
                } else {
                    window.close();
                }
            }, 1000);
        }
    </script>
</body>
</html>`;

// --- Request handlers -------------------------------------------------------

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

async function handleJoinRequestPage(): Promise<Response> {
  return new Response(JOIN_REQUEST_HTML, {
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}

async function handleAnswerJoinRequest(request: Request, env: Env): Promise<Response> {
  if (!env.TOKEN) {
    return json({ ok: false, error: "TOKEN not configured" }, 500);
  }

  let body: { _auth?: string; query_id?: string };
  try {
    body = (await request.json()) as { _auth?: string; query_id?: string };
  } catch {
    return json({ ok: false, error: "Invalid JSON" }, 400);
  }

  const valid = await validateInitData(env.TOKEN, body._auth ?? "");
  if (!valid) {
    return json({ ok: false, error: "Unauthorized" }, 401);
  }

  const queryId = body.query_id;
  if (!queryId) {
    return json({ ok: false, error: "Missing query_id" }, 400);
  }

  try {
    await answerChatJoinRequestQuery(env.TOKEN, queryId);
  } catch (err) {
    console.error("Failed to answer join request:", err);
    return json({ ok: false, error: "Unknown error" }, 500);
  }

  return json({ ok: true });
}

async function handleWebhook(request: Request, env: Env): Promise<Response> {
  if (!env.TOKEN) {
    return json({ ok: false, error: "TOKEN not configured" }, 500);
  }

  const baseUrl = new URL(request.url).origin;

  let update: {
    chat_join_request?: {
      query_id?: string;
      chat?: { title?: string };
      from?: { id?: number };
      user_chat_id?: number;
    };
  };
  try {
    update = (await request.json()) as typeof update;
  } catch {
    return json({ ok: false }, 400);
  }

  const joinRequest = update.chat_join_request;
  if (joinRequest?.query_id) {
    const params = new URLSearchParams({
      query_id: joinRequest.query_id,
      title: joinRequest.chat?.title ?? "",
    });
    const webAppUrl = `${baseUrl}/join_request?${params.toString()}`;
    try {
      await sendChatJoinRequestWebApp(env.TOKEN, joinRequest.query_id, webAppUrl);
    } catch (err) {
      console.error("Failed to send web app:", err);
      return json({ ok: false }, 500);
    }
  }

  return json({ ok: true });
}

// --- Main handler -----------------------------------------------------------

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method === "GET" && path === "/") {
      return json({ status: "ok", service: "guard-bot" });
    }

    if (request.method === "GET" && path === "/join_request") {
      return handleJoinRequestPage();
    }

    if (request.method === "POST" && path === "/answer_join_request") {
      return handleAnswerJoinRequest(request, env);
    }

    if (request.method === "POST" && path === "/webhook") {
      return handleWebhook(request, env);
    }

    if (request.method === "POST" && path === "/setup-webhook") {
      return json(await setupWebhook(env, url.origin));
    }

    return json({ ok: false, error: "Not found" }, 404);
  },

  async scheduled(_event: ScheduledEvent, env: Env): Promise<void> {
    if (env.TOKEN) {
      // В scheduled-событии нет входящего запроса, поэтому используем
      // переменную окружения CF_WORKER_URL (если задана) или пропускаем.
      const baseUrl = env.CF_WORKER_URL;
      if (baseUrl) {
        await setupWebhook(env, baseUrl);
      }
    }
  },
};