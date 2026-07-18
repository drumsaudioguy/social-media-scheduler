import os
import json
import requests
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials

from datetime import datetime
from zoneinfo import ZoneInfo

print("=================================")
print("CAPTION REWRITER V2.0")
print("=================================")

# =========================
# CONFIG
# =========================

service_account_info = json.loads(
    os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")

GEMINI_URL = (
    "https://generativelanguage.googleapis.com"
    "/v1beta/models/gemini-2.0-flash:generateContent"
)

# =========================
# TELEGRAM HELPER
# =========================

def send_telegram(message):

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("TELEGRAM: Token or Chat ID missing, skipping")
        return

    try:

        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML"
            },
            timeout=10
        )

        print(
            "TELEGRAM SENT:",
            response.status_code,
            response.text[:200]
        )

    except Exception as e:

        print("TELEGRAM ERROR:", str(e))

# =========================
# GEMINI HELPER
# =========================

def call_gemini(prompt):

    response = requests.post(
        GEMINI_URL,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY
        },
        json={
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 1500
            }
        },
        timeout=30
    )

    print("GEMINI HTTP STATUS:", response.status_code)

    result = response.json()

    if response.status_code != 200:
        print("GEMINI ERROR RESPONSE:", result)
        return None

    if "error" in result:
        print("GEMINI API ERROR:", result["error"])
        return None

    if "candidates" not in result:
        print("GEMINI UNEXPECTED RESPONSE:", result)
        return None

    return (
        result["candidates"][0]
        ["content"]["parts"][0]["text"]
        .strip()
    )

# =========================
# GOOGLE AUTH
# =========================

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    service_account_info,
    scope
)

client = gspread.authorize(creds)

sheet = client.open_by_key(
    os.environ["GOOGLE_SHEET_ID"]
)

worksheet = sheet.worksheet("Sheet1")

data = worksheet.get_all_records()

df = pd.DataFrame(data)

rewritten_count = 0

# =========================
# PROCESS ROWS
# =========================

try:

    for index, row in df.iterrows():

        status      = str(row.get("Status", "")).strip()
        instruction = str(row.get("AI Rewrite Instruction", "")).strip()
        caption     = str(row.get("Caption", "")).strip()
        brand       = str(row.get("Brand", "")).strip()

        if not instruction:
            continue

        if status == "Posted":
            print(f"Row {index + 2}: Skipping — already Posted")
            continue

        print(f"Row {index + 2}: Rewriting caption for {brand}")
        print(f"  Instruction : {instruction}")
        print(f"  Original    : {caption[:80]}...")

        try:

            prompt = f"""You are a professional social media caption writer specialising in music instruments and audio equipment brands.

Brand: {brand}

Original Caption:
{caption}

Rewrite Instruction:
{instruction}

Rules:
- Follow the instruction exactly
- Keep all hashtags unless told to change them
- Keep all emojis unless told to change them
- Match the tone of a premium music brand (professional, passionate, inspiring)
- Return ONLY the rewritten caption — no explanations, no quotes, no preamble"""

            new_caption = call_gemini(prompt)

            if not new_caption:
                print(f"  Row {index + 2}: Gemini returned nothing, skipping")
                continue

            print(f"  Rewritten   : {new_caption[:80]}...")

            # Col G (7) = Caption, Col O (15) = AI Rewrite Instruction
            worksheet.update_cell(index + 2, 7, new_caption)
            worksheet.update_cell(index + 2, 15, "")

            print(f"  Row {index + 2}: Done — caption updated, instruction cleared")

            rewritten_count += 1

        except Exception as e:

            err = str(e)
            print(f"  ERROR on row {index + 2}: {err}")
            send_telegram(
                f"❌ <b>Caption rewrite error</b> — Row {index + 2}: {err}"
            )

    send_telegram(
        f"✏️ <b>Caption Rewriter Done</b>\n{rewritten_count} caption(s) rewritten"
    )

except Exception as ex:

    err = str(ex)
    send_telegram(f"❌ <b>Caption Rewriter FAILED</b>\n{err}")
    raise
