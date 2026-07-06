import os
import json
import requests
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials

from datetime import datetime
from zoneinfo import ZoneInfo
from email.mime.text import MIMEText

print("=================================")
print("CAPTION REWRITER V1.2")
print("=================================")

# =========================
# CONFIG
# =========================

# Google credentials (match the secret name used in your workflows)
service_account_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# Telegram (for alerts)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")

GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

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
        print("TELEGRAM SENT:", response.status_code, response.text[:200])
    except Exception as e:
        print("TELEGRAM ERROR:", str(e))

# =========================
# GOOGLE AUTH
# =========================

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(os.environ["GOOGLE_SHEET_ID"])
worksheet = sheet.worksheet("Sheet1")

# Load all rows into a DataFrame for iteration
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
            prompt = f"""You are a professional social media caption writer.

Original Caption:
{caption}

Rewrite Instruction:
{instruction}

Rules:
- Follow the instruction exactly
- Keep all hashtags unless told to change them
- Keep all emojis unless told to change them
- Return ONLY the rewritten caption — no explanations, no quotes, no preamble"""

            response = requests.post(
                GROQ_URL,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 1500
                },
                timeout=30
            )

            result = response.json()
            print(f"  Groq HTTP status : {response.status_code}")

            if response.status_code != 200:
                print(f"  GROQ ERROR RESPONSE: {result}")
                # Do not overwrite existing caption; continue to next row
                continue

            if "error" in result:
                print(f"  GROQ API ERROR   : {result['error']}")
                continue

            if "choices" not in result:
                print(f"  GROQ UNEXPECTED  : {result}")
                continue

            new_caption = result["choices"][0]["message"]["content"].strip()
            print(f"  Rewritten   : {new_caption[:80]}...")

            # Col G (7) = Caption, Col O (15) = AI Rewrite Instruction
            worksheet.update_cell(index + 2, 7, new_caption)
            worksheet.update_cell(index + 2, 15, "")

            print(f"  Row {index + 2}: Done — caption updated, instruction cleared")
            rewritten_count += 1

        except Exception as e:
            err = str(e)
            print(f"  ERROR on row {index + 2}: {err}")
            # Send alert for row-level failure but continue processing
            send_telegram(f"❌ <b>Caption rewrite error</b> — Row {index + 2}: {err}")

    # End for loop

    send_telegram(f"✏️ <b>Caption Rewriter Done</b>\n{rewritten_count} caption(s) rewritten")

except Exception as ex:
    # Top-level failure: notify and re-raise so CI/workflow sees the error
    err = str(ex)
    send_telegram(f"❌ <b>Caption Rewriter FAILED</b>\n{err}")
    raise
