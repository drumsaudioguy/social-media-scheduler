import os
import json
import requests
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials

print("=================================")
print("CAPTION REWRITER V1")
print("=================================")

# =========================
# GOOGLE AUTH
# =========================

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

service_account_info = json.loads(os.environ["GOOGLE_CREDENTIALS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(os.environ["SPREADSHEET_ID"])
worksheet = sheet.worksheet("Sheet1")
data = worksheet.get_all_records()
df = pd.DataFrame(data)

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"

rewritten_count = 0

# =========================
# PROCESS ROWS
# =========================

for index, row in df.iterrows():

    status      = str(row.get("Status", "")).strip()
    instruction = str(row.get("AI Rewrite Instruction", "")).strip()
    caption     = str(row.get("Caption", "")).strip()
    brand       = str(row.get("Brand", "")).strip()

    # Skip if no instruction
    if not instruction:
        continue

    # Skip if already posted
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
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 1500
            },
            timeout=30
        )
        result = response.json()
        print(f"  Groq response: {result}")
        if "choices" not in result:
        print(f"  GROQ ERROR: {result.get('error', result)}")
        continue
        new_caption = result["choices"][0]["message"]["content"].strip()

        print(f"  Rewritten   : {new_caption[:80]}...")

        # Col E (5) = Caption, Col O (15) = AI Rewrite Instruction
        worksheet.update_cell(index + 2, 5, new_caption)
        worksheet.update_cell(index + 2, 15, "")

        print(f"  Row {index + 2}: Done — caption updated, instruction cleared")
        rewritten_count += 1

    except Exception as e:
        print(f"  ERROR on row {index + 2}: {str(e)}")

# =========================
# SUMMARY
# =========================

print("=================================")
print(f"CAPTION REWRITER DONE: {rewritten_count} rewritten")
print("=================================")
