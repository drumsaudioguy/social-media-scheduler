import os
import json
import re
import gspread
import boto3
import requests

from groq import Groq
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from botocore.config import Config
from urllib.parse import unquote, quote
from oauth2client.service_account import ServiceAccountCredentials

# =========================
# R2 SCANNER V2
# =========================

print("=================================")
print("R2 SCANNER V2")
print("=================================")

# =========================
# CONFIG
# =========================

R2_BUCKET_NAME     = os.getenv("R2_BUCKET_NAME")
R2_ACCOUNT_ID      = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY      = os.getenv("R2_ACCESS_KEY")
R2_SECRET_KEY      = os.getenv("R2_SECRET_KEY")
R2_BASE_URL        = "https://pub-32b66fd1abca4fbb80e6e1facbabb289.r2.dev"
R2_ENDPOINT        = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

GROQ_API_KEY       = os.getenv("GROQ_API_KEY")
SPREADSHEET_ID     = os.getenv("SPREADSHEET_ID")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

SHEET_NAME         = "Sheet1"

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
    "Meinl Sticks and Brush India": {
        "tone": "focused, craftsmanship, drummer essentials, stick and brush artistry",
        "r2_folder": "Meinl Stick and Brush"
    },
    "Konig": {
        "tone": "innovative, precision engineering, music stands",
        "r2_folder": "Konig and Meyer"
    }
}

# =========================
# GOOGLE SHEETS AUTH
# =========================

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = json.loads(GOOGLE_CREDENTIALS)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
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
# GROQ CLIENT
# =========================

groq_client = Groq(api_key=GROQ_API_KEY)

print("Groq connected ✅")

# =========================
# HELPERS
# =========================

def natural_sort_key(s):
    return [
        int(c) if c.isdigit() else c.lower()
        for c in re.split(r'(\d+)', s)
    ]


def list_r2_files(prefix):
    try:
        response = s3.list_objects_v2(
            Bucket=R2_BUCKET_NAME,
            Prefix=prefix
        )
        return [
            obj["Key"]
            for obj in response.get("Contents", [])
            if not obj["Key"].endswith("/")
        ]
    except Exception as e:
        print(f"R2 LIST ERROR: {e}")
        return []


def encode_url(url):
    parts = url.split(".r2.dev/", 1)
    if len(parts) == 2:
        encoded_path = quote(unquote(parts[1]), safe="/")
        return f"{parts[0]}.r2.dev/{encoded_path}"
    return url


def get_existing_urls():
    rows = worksheet.get_all_records()
    urls = set()
    for row in rows:
        media = str(row.get("MediaURLs", "")).strip()
        if media:
            for u in media.split("|"):
                u = u.strip()
                if u:
                    urls.add(unquote(u))
    return urls


def get_next_publish_slot():
    rows = worksheet.get_all_records()
    ist = ZoneInfo("Asia/Kolkata")
    now = datetime.now(ist)

    scheduled = []
    for row in rows:
        try:
            dt_str = f"{row['PublishDate']} {row['PublishTime']}"
            dt = datetime.strptime(dt_str, "%d-%m-%Y %H:%M").replace(tzinfo=ist)
            scheduled.append(dt)
        except Exception:
            continue

    candidate = now.replace(second=0, microsecond=0)
    if candidate.minute < 30:
        candidate = candidate.replace(minute=30)
    else:
        candidate = candidate.replace(minute=0) + timedelta(hours=1)

    if candidate <= now + timedelta(minutes=29):
        candidate += timedelta(minutes=30)

    while True:
        if candidate not in scheduled:
            return (
                candidate.strftime("%d-%m-%Y"),
                candidate.strftime("%H:%M")
            )
        candidate += timedelta(minutes=30)


def add_row_to_sheet(brand, content_type, media_urls_str, caption, publish_date, publish_time):
    worksheet.append_row([
        brand,
        "Instagram",
        content_type,
        publish_date,
        publish_time,
        media_urls_str,
        caption,
        "Approved",
        "",   # PostID (Col I)
        "",   # TokenStatus (Col J)
        "",   # LastCheck (Col K)
        "",   # DataAccessExpiry (Col L)
        "",   # FB PostID (Col M)
        ""    # R2Status (Col N)
    ])
    print(f"  ✅ Row added: {brand} | {content_type} | {publish_date} {publish_time}")


# =========================
# CAPTION GENERATION (GROQ)
# =========================

def generate_caption(brand_name, content_type, media_urls, tone):
    try:
        if content_type in ("Image", "Carousel"):
            image_url = media_urls[0]
            print(f"  Generating vision caption for: {image_url}")

            response = groq_client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url}
                            },
                            {
                                "type": "text",
                                "text": (
                                    f"You are a social media manager for {brand_name}. "
                                    f"Brand tone: {tone}. "
                                    f"Look at this image carefully and write an engaging Instagram caption "
                                    f"that describes what you see and connects it to the brand. "
                                    f"Keep it under 150 words. End with exactly 5 relevant hashtags."
                                )
                            }
                        ]
                    }
                ],
                max_tokens=300
            )

        else:
            print(f"  Generating text caption for reel...")

            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"You are a social media manager for {brand_name}. "
                            f"Brand tone: {tone}. "
                            f"Write an engaging Instagram Reel caption for a new product/brand video. "
                            f"Keep it under 150 words. End with exactly 5 relevant hashtags."
                        )
                    }
                ],
                max_tokens=300
            )

        caption = response.choices[0].message.content.strip()
        print(f"  Caption generated ✅")
        return caption

    except Exception as e:
        print(f"  Groq caption error: {e}")
        return f"New content from {brand_name}. #music #drums #percussion #instruments #india"


# =========================
# MAIN SCAN LOOP
# =========================

data = worksheet.get_all_records()
existing_urls = get_existing_urls()

print(f"\nFound {len(existing_urls)} existing URLs in sheet\n")

new_rows_added = 0

for brand_name, config in BRANDS.items():

    folder = config["r2_folder"]
    tone   = config["tone"]

    print(f"--- Scanning: {brand_name} ({folder}/) ---")

    # ── PHOTOS ───────────────────────────────────────────
    photo_keys = [
        k for k in list_r2_files(f"{folder}/Photos/")
        if k.lower().endswith((".jpg", ".jpeg", ".png"))
    ]

    for key in photo_keys:
        public_url = unquote(f"{R2_BASE_URL}/{key}")

        if public_url in existing_urls:
            print(f"  SKIP (exists): {key.split('/')[-1]}")
            continue

        print(f"  NEW Photo: {key.split('/')[-1]}")
        caption = generate_caption(brand_name, "Image", [encode_url(f"{R2_BASE_URL}/{key}")], tone)
        publish_date, publish_time = get_next_publish_slot()
        add_row_to_sheet(brand_name, "Image", encode_url(f"{R2_BASE_URL}/{key}"), caption, publish_date, publish_time)
        existing_urls.add(public_url)
        new_rows_added += 1

    # ── REELS ────────────────────────────────────────────
    reel_keys = [
        k for k in list_r2_files(f"{folder}/Reels/")
        if k.lower().endswith(".mp4")
    ]
    reel_keys += [
        k for k in list_r2_files(f"{folder}/Reel/")
        if k.lower().endswith(".mp4")
    ]

    for key in reel_keys:
        public_url = unquote(f"{R2_BASE_URL}/{key}")

        if public_url in existing_urls:
            print(f"  SKIP (exists): {key.split('/')[-1]}")
            continue

        print(f"  NEW Reel: {key.split('/')[-1]}")
        caption = generate_caption(brand_name, "Reel", [encode_url(f"{R2_BASE_URL}/{key}")], tone)
        publish_date, publish_time = get_next_publish_slot()
        add_row_to_sheet(brand_name, "Reel", encode_url(f"{R2_BASE_URL}/{key}"), caption, publish_date, publish_time)
        existing_urls.add(public_url)
        new_rows_added += 1

    # ── CAROUSEL ─────────────────────────────────────────
    carousel_base = f"{folder}/Carousel/"

    all_carousel_keys = [
        k for k in list_r2_files(carousel_base)
        if k.lower().endswith((".jpg", ".jpeg", ".png"))
    ]

    carousel_groups = {}
    for key in all_carousel_keys:
        parts = key.split("/")
        subfolder = parts[2] if len(parts) >= 4 else "default"
        carousel_groups.setdefault(subfolder, []).append(key)

    for subfolder, keys in carousel_groups.items():
        urls = [encode_url(f"{R2_BASE_URL}/{k}") for k in keys]
        urls = sorted(urls, key=natural_sort_key)
        raw_urls = [unquote(u) for u in urls]

        if any(u in existing_urls for u in raw_urls):
            print(f"  SKIP Carousel (exists): {subfolder}")
            continue

        print(f"  NEW Carousel: {subfolder} ({len(urls)} images)")
        caption = generate_caption(brand_name, "Carousel", urls, tone)
        publish_date, publish_time = get_next_publish_slot()
        add_row_to_sheet(brand_name, "Carousel", "|".join(urls), caption, publish_date, publish_time)

        for u in raw_urls:
            existing_urls.add(u)
        new_rows_added += 1

print(f"\n=================================")
print(f"SCANNER FINISHED — {new_rows_added} new rows added")
print(f"=================================")
