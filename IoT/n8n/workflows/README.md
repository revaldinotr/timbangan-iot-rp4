# WhatsApp Chatbot (n8n)

An n8n workflow that lets vendors check stock data over WhatsApp.

---

## Import

n8n → **Workflows** → **Import from File** → select
`workflows/manajemen-stok-sayur-wa-pin.n8n.json`

The workflow is intentionally shipped **without credentials and without a spreadsheet ID** —
everything must be filled in after importing.

## What You Must Fill In

| Node | What to change |
|---|---|
| `Ambil Data Sheets` | Replace `YOUR_GOOGLE_SHEET_ID`; select the Google Sheets credential |
| `Ambil Link Foto` | Same as above |
| `Groq Chat Model` | Select the Groq credential |
| `Balas Pesan Auth` | Select the Header Auth (Fonnte) credential |
| `Kirim ke WhatsApp` | Select the Header Auth credential |
| `Balas Pesan Tidak Valid` | Select the Header Auth credential |
| `Kirim Foto ke WhatsApp` | Select the Header Auth credential |

## Required Credentials

| Name | Type | Source |
|---|---|---|
| Google Sheets account | Google Sheets OAuth2 API | Google Cloud Console |
| Header Auth account | Header Auth — Name `Authorization`, Value token | [fonnte.com](https://fonnte.com) |
| Groq account | Groq API | [console.groq.com/keys](https://console.groq.com/keys) |

## Set the PIN

```
STOK_PIN=<at least 6 digits>
```

**n8n Cloud:** Settings → Variables
**Self-host:** set it in `.env`, and make sure `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`

Do not rely on the fallback value `0000` in the code.

## Connect the Webhook

Activate the workflow → copy the **Production URL** from the `WhatsApp Webhook` node →
paste it into Fonnte → **Device** → **Webhook URL**.

---

# Troubleshooting

## The bot doesn't reply at all

**1. Check that the workflow is active.** The **Active** toggle in the top right must be on.
The test webhook only stays alive for 120 seconds after clicking "Listen".

**2. Check the webhook URL in Fonnte.** It must be the **Production URL**, not the Test URL.
Copy it again from the `WhatsApp Webhook` node.

**3. Check that the Fonnte device is connected.** Fonnte panel → the device status must be
`connected`. If it's `disconnected`, rescan the QR code.

**4. Look at the execution history.** n8n → **Executions**. If it's empty, the webhook never
received anything — the problem is on the Fonnte or network side.

**5. Self-host: check `WEBHOOK_URL`.** If it's wrong, n8n shows a URL that can't be reached
from outside. It must be a public URL ending with a trailing slash.

## Error 429 / rate limit

**From Groq:** the free quota is used up. Wait for the reset or upgrade.
**From Fonnte:** you've exceeded your plan's message limit.

Both HTTP nodes already retry 3×, but retrying doesn't help when the quota is genuinely exhausted.

## Error 401 / 403

There's a problem with a credential:

| Service | Common cause |
|---|---|
| Fonnte | Wrong token, or the header isn't `Authorization` |
| Google | OAuth expired/revoked, or the API isn't enabled |
| Groq | Wrong API key, or it has been deleted |

---
