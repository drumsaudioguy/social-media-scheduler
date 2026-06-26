import os
import re
import json
import boto3
import gspread
import google.generativeai as genai

from datetime import datetime, date
from zoneinfo import ZoneInfo
from botocore.config import Config
from oauth2client.service_account import ServiceAccountCredentials

# =========================
# R2 SCANNER V1
# =========================

print("=================================")
print("R2 SCANNER V1")
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

GEMINI_API_KEY      = os.getenv("GEMINI_API_KEY")
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
# GEMINI SETUP
# =========================

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

print("Gemini connected ✅")

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
    """List all files under a given R2 prefix."""
    files = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=R2_BUCKET_NAME, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            # Skip folder placeholders
            if not key.endswith("/"):
                files.append(key)
    return files

# =========================
# HELPER: GET EXISTING URLS FROM SHEET
# =========================

def get_existing_media_urls():
    """Returns a flat set of all URLs already in Column F (MediaURLs)."""
    all_values = worksheet.col_values(6)  # Column F = MediaURLs
    existing = set()
    for cell in all_values:
        if cell:
            for url in cell.split("|"):
                existing.add(url.strip())
    return existing

# =========================
# HELPER: GENERATE CAPTION WITH GEMINI
# =========================

def generate_caption(brand_name, content_type, urls, tone):
    """Send media to Gemini Vision and get a creative caption."""
    try:
        if content_type == "Reel":
            prompt = (
                f"You are a creative social media copywriter for {brand_name}. "
                f"Brand tone: {tone}. "
                f"Watch this video and write one short, punchy caption for an Instagram Reel. "
                f"No emojis, no hashtags, no generic phrases. "
                f"Be original and unexpected. Write like a human, not a marketer. "
                f"One caption only."
            )
            media_part = {"mime_type": "video/mp4", "uri": urls[0]}
            response = model.generate_content([prompt, media_part])

        elif content_type == "Image":
            prompt = (
                f"You are a creative social media copywriter for {brand_name}. "
                f"Brand tone: {tone}. "
                f"Look at this image and write one short, punchy caption for an Instagram post. "
                f"No emojis, no hashtags, no generic phrases. "
                f"Be original and unexpected. Write like a human, not a marketer. "
                f"One caption only."
            )
            import urllib.request
            import tempfile
            import mimetypes
            # Download image temporarily for Gemini
            suffix = "." + urls[0].split(".")[-1]
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                urllib.request.urlretrieve(urls[0], tmp.name)
                img_data = genai.upload_file(tmp.name)
            response = model.generate_content([prompt, img_data])

        elif content_type == "Carousel":
            prompt = (
                f"You are a creative social media copywriter for {brand_name}. "
                f"Brand tone: {tone}. "
                f"Look at all these {len(urls)} images together as one cohesive carousel post. "
                f"Write ONE single caption for the entire carousel, not per image. "
                f"No emojis, no hashtags, no generic phrases. "
                f"Be original and unexpected. Write like a human, not a marketer. "
                f"One caption only."
            )
            import urllib.request
            import tempfile
            parts = [prompt]
            for url in urls:
                suffix = "." + url.split(".")[-1]
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    urllib.request.urlretrieve(url, tmp.name)
                    img_data = genai.upload_file(tmp.name)
                parts.append(img_data)
            response = model.generate_content(parts)

        caption = response.text.strip()
        print(f"  Gemini caption: {caption[:80]}...")
        return caption

    except Exception as e:
        print(f"  Gemini error: {e}")
        return f"New post from {brand_name}."

# =========================
# HELPER: GET NEXT PUBLISH SLOT
# =========================

def get_next_publish_slot():
    """Returns today's date and a time slot (next round 30-min from now)."""
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    # Round up to next 30-min slot
    minute = now.minute
    if minute < 30:
        slot_minute = 30
        slot_hour = now.hour
    else:
        slot_minute = 0
        slot_hour = now.hour + 1
    if slot_hour >= 24:
        slot_hour = 9  # fallback to 9am
    publish_date = now.strftime("%d-%m-%Y")
    publish_time = f"{slot_hour:02d}:{slot_minute:02d}"
    return publish_date, publish_time

# =========================
# HELPER: ADD ROW TO SHEET
# =========================

def add_row_to_sheet(brand, content_type, media_urls_str, caption, publish_date, publish_time):
    """Appends a new Pending row to the Google Sheet."""
    new_row = [
        brand,          # A - Brand
        "Instagram",    # B - Platform
        content_type,   # C - ContentType
        publish_date,   # D - PublishDate
        publish_time,   # E - PublishTime
        media_urls_str, # F - MediaURLs
        caption,        # G - Caption
        "Pending",      # H - Status (Pending until you approve)
        "",             # I - PostID
        "",             # J - TokenStatus
        "",             # K - LastCheck
        "",             # L - DataAccessExpiry
        "",             # M - Facebook PostID
        "",             # N - R2Status
        "",             # O - AI Rewrite Instruction
    ]
    worksheet.append_row(new_row, value_input_option="USER_ENTERED")
    print(f"  ✅ Row added: {brand} | {content_type} | {publish_date} {publish_time}")

# =========================
# MAIN SCANNER LOGIC
# =========================

existing_urls = get_existing_media_urls()
print(f"\nFound {len(existing_urls)} existing URLs in sheet")
new_rows_added = 0

for brand_name, brand_config in BRANDS.items():
    folder = brand_config["r2_folder"]
    tone = brand_config["tone"]

    print(f"\n--- Scanning: {brand_name} ({folder}/) ---")

    # ── PHOTOS ──────────────────────────────────────────
    photo_keys = [
        k for k in list_r2_files(f"{folder}/Photos/")
        if k.lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    for key in photo_keys:
        public_url = f"{R2_BASE_URL}/{key}"
        if public_url in existing_urls:
            print(f"  SKIP (exists): {key.split('/')[-1]}")
            continue
        print(f"  NEW Photo: {key.split('/')[-1]}")
        caption = generate_caption(brand_name, "Image", [public_url], tone)
        publish_date, publish_time = get_next_publish_slot()
        add_row_to_sheet(brand_name, "Image", public_url, caption, publish_date, publish_time)
        existing_urls.add(public_url)
        new_rows_added += 1

    # ── REELS ────────────────────────────────────────────
    reel_keys = [
        k for k in list_r2_files(f"{folder}/Reels/")
        if k.lower().endswith(".mp4")
    ]
    # Also check "Reel" (singular) folder variant
    reel_keys += [
        k for k in list_r2_files(f"{folder}/Reel/")
        if k.lower().endswith(".mp4")
    ]
    for key in reel_keys:
        public_url = f"{R2_BASE_URL}/{key}"
        if public_url in existing_urls:
            print(f"  SKIP (exists): {key.split('/')[-1]}")
            continue
        print(f"  NEW Reel: {key.split('/')[-1]}")
        caption = generate_caption(brand_name, "Reel", [public_url], tone)
        publish_date, publish_time = get_next_publish_slot()
        add_row_to_sheet(brand_name, "Reel", public_url, caption, publish_date, publish_time)
        existing_urls.add(public_url)
        new_rows_added += 1

    # ── CAROUSEL ─────────────────────────────────────────
    carousel_base = f"{folder}/Carousel/"
    all_carousel_keys = [
        k for k in list_r2_files(carousel_base)
        if k.lower().endswith((".jpg", ".jpeg", ".png"))
    ]

    # Group by subfolder (e.g. Tl-2030)
    carousel_groups = {}
    for key in all_carousel_keys:
        parts = key.split("/")
        # parts: [Brand, Carousel, SubFolder, filename]
        if len(parts) >= 4:
            subfolder = parts[2]
        else:
            subfolder = "default"
        carousel_groups.setdefault(subfolder, []).append(key)

    for subfolder, keys in carousel_groups.items():
        urls = [f"{R2_BASE_URL}/{k}" for k in keys]
        urls = sorted(urls, key=natural_sort_key)

        # Check if ANY url from this group already exists
        if any(u in existing_urls for u in urls):
            print(f"  SKIP Carousel (exists): {subfolder}")
            continue

        print(f"  NEW Carousel: {subfolder} ({len(urls)} images)")
        media_urls_str = "|".join(urls)
        caption = generate_caption(brand_name, "Carousel", urls, tone)
        publish_date, publish_time = get_next_publish_slot()
        add_row_to_sheet(brand_name, "Carousel", media_urls_str, caption, publish_date, publish_time)
        for u in urls:
            existing_urls.add(u)
        new_rows_added += 1

# =========================
# SUMMARY
# =========================

print("\n=================================")
print(f"SCANNER FINISHED — {new_rows_added} new rows added")
print("=================================")
