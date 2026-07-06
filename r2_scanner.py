import os
import re
import json
import boto3
import gspread
import requests

from datetime import datetime, date
from zoneinfo import ZoneInfo
from botocore.config import Config
from oauth2client.service_account import ServiceAccountCredentials

print("=================================")
print("R2 SCANNER V2.1")
print("=================================")

# =========================
# CONFIG
# =========================

R2_BUCKET_NAME      = os.getenv("R2_BUCKET_NAME")
R2_ACCOUNT_ID       = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY       = os.getenv("R2_ACCESS_KEY")
R2_SECRET_KEY       = os.getenv("R2_SECRET_KEY")
R2_BASE_URL         = "https://pub-32b66fd1abca4fbb80e6e1facbabb289.r2.dev"
R2_ENDPOINT         = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

GROQ_API_KEY        = os.getenv("GROQ_API_KEY")
SPREADSHEET_ID      = os.getenv("SPREADSHEET_ID")
GOOGLE_CREDENTIALS  = os.getenv("GOOGLE_CREDENTIALS")

SHEET_NAME          = "Sheet1"

# =========================
# BRANDS CONFIG
# =========================

BRANDS = {
    "Pearl": {
        "tone": "passionate, premium, drummer community",
        "r2_folder": "Pearl"
    },
    "Meinl Cymbals": {
        "tone": "professional, inspiring, percussionist community",
        "r2_folder": "Meinl Cymbals"
    },
    "Meinl Percussion": {
        "tone": "vibrant, world music, rhythmic",
        "r2_folder": "Meinl Percussion"
    },
    "Meinl Stick and Brush": {
        "tone": "focused, craftsmanship, drummer essentials",
        "r2_folder": "Meinl Stick and Brush"
    },
    "Konig": {
        "tone": "innovative, precision engineering, music stands",
        "r2_folder": "Konig and Meyer"
    },
    "MSB": {
        "tone": "focused, craftsmanship, drummer essentials",
        "r2_folder": "MSB"
    }
}

# =========================
# GOOGLE SHEETS AUTH
# =========================

creds_dict = json.loads(GOOGLE_CREDENTIALS)
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    creds_dict,
    ["https://spreadsheets.google.com/feeds",
     "https://www.googleapis.com/auth/drive"]
)
gc = gspread.authorize(creds)
spreadsheet = gc.open_by_key(SPREADSHEET_ID)
worksheet = spreadsheet.worksheet(SHEET_NAME)

print("Google Sheets connected ✅")

# =========================
# R2 CLIENT
# =========================

s3 = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY,
    aws_secret_access_key=R2_SECRET_KEY,
    config=Config(signature_version="s3v4"),
    region_name="auto"
)

print("R2 connected ✅")

# =========================
# HELPER: NATURAL SORT
# =========================

def natural_sort_key(url):
    filename = url.split("/")[-1]
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', filename)]

# =========================
# HELPER: LIST R2 FILES
# =========================

def list_r2_files(prefix):
    files = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=R2_BUCKET_NAME, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.endswith("/"):
                files.append(key)
    return files

# =========================
# HELPER: GET EXISTING URLS FROM SHEET
# =========================

def get_existing_media_urls():
    all_values = worksheet.col_values(6)  # Column F = MediaURLs
    existing = set()
    for cell in all_values:
        if cell:
            for url in cell.split("|"):
                existing.add(url.strip())
    return existing

# =========================
# HELPER: GENERATE CAPTION WITH GROQ
# =========================

def generate_caption(brand_name, content_type, urls, tone):
    try:
        print(f"  GROQ: Generating caption for {brand_name} - {content_type}")

        if content_type == "Reel":
            prompt = (
                f"You are a creative social media copywriter for {brand_name}. "
                f"Brand tone: {tone}. "
                f"Write one short, punchy caption for an Instagram Reel. "
                f"No emojis, no hashtags, no generic phrases. "
                f"Be original and unexpected. Write like a human, not a marketer. "
                f"One caption only, under 150 words. "
                f"Add 5-8 relevant hashtags at the end."
            )
        elif content_type == "Image":
            prompt = (
                f"You are a creative social media copywriter for {brand_name}. "
                f"Brand tone: {tone}. "
                f"Write one short, punchy caption for an Instagram photo post. "
                f"No generic phrases. "
                f"Be original and unexpected. Write like a human, not a marketer. "
                f"One caption only, under 150 words. "
                f"Add 5-8 relevant hashtags at the end."
            )
        else:  # Carousel
            prompt = (
                f"You are a creative social media copywriter for {brand_name}. "
                f"Brand tone: {tone}. "
                f"Write ONE single caption for an Instagram carousel post with {len(urls)} images. "
                f"No generic phrases. "
                f"Be original and unexpected. Write like a human, not a marketer. "
                f"One caption only, under 150 words. "
                f"Add 5-8 relevant hashtags at the end."
            )

        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.7
            }
        )

        result = response.json()

        if "choices" not in result:
            print("GROQ FULL RESPONSE:", result)
            return f"New post from {brand_name}."

        caption = result["choices"][0]["message"]["content"].strip()
        print(f"  GROQ caption: {caption[:80]}...")
        return caption

    except Exception as e:
        print(f"  GROQ error: {e}")
        return f"New post from {brand_name}."

# =========================
# HELPER: GET NEXT PUBLISH SLOT
# =========================

def get_next_publish_slot():
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    minute = now.minute
    if minute < 30:
        slot_minute = 30
        slot_hour = now.hour
    else:
        slot_minute = 0
        slot_hour = now.hour + 1
    if slot_hour >= 24:
        slot_hour = 9
    publish_date = now.strftime("%d-%m-%Y")
    publish_time = f"{slot_hour:02d}:{slot_minute:02d}"
    return publish_date, publish_time

# =========================
# HELPER: ADD ROW TO SHEET
# =========================

def add_row_to_sheet(brand, content_type, media_urls_str, caption, publish_date, publish_time):
    new_row = [
        brand,          # A - Brand
        "Instagram",    # B - Platform
        content_type,   # C - ContentType
        publish_date,   # D - PublishDate
        publish_time,   # E - PublishTime
        media_urls_str, # F - MediaURLs
        caption,        # G - Caption
        "Pending",      # H - Status
        "",             # I - PostID
        "",             # J - TokenStatus
        "",             # K - LastCheck
        "",             # L - DataAccessExpiry
        "",             # M - FacebookPostID
        "",             # N - R2Status
        "",             # O - AI Rewrite Instr
