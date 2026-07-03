import os
import re
import json
import boto3
import gspread
import requests

from openai import OpenAI
from datetime import datetime
from zoneinfo import ZoneInfo
from botocore.config import Config
from urllib.parse import quote, unquote
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

R2_BUCKET_NAME      = os.getenv("R2_BUCKET_NAME")
R2_ACCOUNT_ID       = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY       = os.getenv("R2_ACCESS_KEY")
R2_SECRET_KEY       = os.getenv("R2_SECRET_KEY")
R2_BASE_URL         = "https://pub-32b66fd1abca4fbb80e6e1facbabb289.r2.dev"
R2_ENDPOINT         = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

OPENAI_API_KEY      = os.getenv("OPENAI_API_KEY")
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
# OPENAI SETUP
# =========================

openai_client = OpenAI(api_key=OPENAI_API_KEY)

print("OpenAI connected ✅")

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
            if not key.endswith("/"):
                files.append(key)
    return files

# =========================
# HELPER: GET EXISTING URLS FROM SHEET
# =========================

def get_existing_media_urls():
    """Returns a flat set of all URLs already in Column F (MediaURLs)."""
    all_values = worksheet.col_values(6)
    existing = set()
    for cell in all_values:
        if cell:
            for url in cell.split("|"):
                existing.add(url.strip())
    return existing

# =========================
# HELPER: GENERATE CAPTION WITH GPT-4o
# =========================

def generate_caption(brand_name, content_type, urls, tone):
    """Use GPT-4o Vision to generate a creative caption."""
    try:
        if content_type == "Reel":
            # GPT-4o cannot watch video — use filename + brand tone for creative caption
            filename = urls[0].split("/")[-1].split("?")[0]
            prompt = (
                f"You are a creative social media copywriter for {brand_name}. "
                f"Brand tone: {tone}. "
                f"Write one short, punchy caption for an Instagram Reel for this brand. "
                f"The video filename is: {filename}. Use it as a clue about the content. "
                f"No emojis, no generic phrases. End with exactly 5 relevant hashtags. "
                f"Be original and unexpected. Write like a human, not a marketer. "
                f"One caption only."
            )
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300
            )

        elif content_type == "Image":
            prompt = (
                f"You are a creative social media copywriter for {brand_name}. "
                f"Brand tone: {tone}. "
                f"Look at this image carefully and write one short, punchy caption for an Instagram post. "
                f"No emojis, no generic phrases. End with exactly 5 relevant hashtags. "
                f"Be original and unexpected. Write like a human, not a marketer. "
                f"One caption only."
            )
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": urls[0], "detail": "high"}}
                    ]
                }],
                max_tokens=300
            )

        elif content_type == "Carousel":
            prompt = (
                f"You are a creative social media copywriter for {brand_name}. "
                f"Brand tone: {tone}. "
                f"Look at all {len(urls)} images together as one cohesive carousel post. "
                f"Write ONE single caption for the entire carousel, not per image. "
                f"No emojis, no generic phrases. End with exactly 5 relevant hashtags. "
                f"Be original and unexpected. Write like a human, not a marketer. "
                f"One caption only."
            )
            content_parts = [{"type": "text", "text": prompt}]
            for url in urls:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": url, "detail": "high"}
                })
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": content_parts}],
                max_tokens=300
            )

        caption = response.choices[0].message.content.strip()
        print(f"  GPT-4o caption: {caption[:80]}...")
        return caption

    except Exception as e:
        print(f"  GPT-4o error: {e}")
        return f"New post from {brand_name}."

# =========================
# HELPER: DELETE FROM R2
# =========================

def delete_from_r2(public_url):
    """Delete a file from R2 using its public URL."""
    try:
        # Strip base URL to get the key, then decode %20 etc back to real characters
        key = unquote(public_url.replace(f"{R2_BASE_URL}/", ""))
        s3.delete_object(Bucket=R2_BUCKET_NAME, Key=key)
        print(f"  🗑️ Deleted from R2: {key.split('/')[-1]}")
        return True
    except Exception as e:
        print(f"  ❌ R2 delete failed for {public_url.split('/')[-1]}: {e}")
        return False

# =========================
# HELPER: GET NEXT PUBLISH SLOT
# =========================

def get_next_publish_slot():
    """Returns today's date and a time slot (next round 30-min from now)."""
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
    """Appends a new Pending row to the Google Sheet."""
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
        "",             # M - Facebook PostID
        "",             # N - R2Status
        "",             # O - AI Rewrite Instruction
    ]
    worksheet.append_row(new_row, value_input_option="USER_ENTERED")
    print(f"  ✅ Row added: {brand} | {content_type} | {publish_date} {publish_time}")

# =========================
# HELPER: UPDATE R2 STATUS IN SHEET
# =========================

def update_r2_status(row_index, status):
    """Update Column N (R2Status) for a given row."""
    try:
        worksheet.update_cell(row_index, 14, status)
    except Exception as e:
        print(f"  ❌ Failed to update R2Status: {e}")

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
        public_url = f"{R2_BASE_URL}/{quote(key, safe='+/')}"
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
    reel_keys += [
        k for k in list_r2_files(f"{folder}/Reel/")
        if k.lower().endswith(".mp4")
    ]
    for key in reel_keys:
        public_url = f"{R2_BASE_URL}/{quote(key, safe='+/')}"
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

    carousel_groups = {}
    for key in all_carousel_keys:
        parts = key.split("/")
        if len(parts) >= 4:
            subfolder = parts[2]
        else:
            subfolder = "default"
        carousel_groups.setdefault(subfolder, []).append(key)

    for subfolder, keys in carousel_groups.items():
        urls = [f"{R2_BASE_URL}/{quote(k, safe='+/')}" for k in keys]
        urls = sorted(urls, key=natural_sort_key)

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
# R2 CLEANUP — DELETE POSTED FILES
# =========================

print("\n--- R2 Cleanup: Checking for posted files to delete ---")

all_rows = worksheet.get_all_values()
deleted_count = 0
failed_count = 0

for i, row in enumerate(all_rows):
    row_index = i + 1  # Google Sheets is 1-indexed

    # Skip header row
    if row_index == 1:
        continue

    # Need at least 14 columns
    if len(row) < 14:
        continue

    status    = row[7].strip()   # Column H - Status
    media_url = row[5].strip()   # Column F - MediaURLs
    r2_status = row[13].strip()  # Column N - R2Status

    # Only delete if posted and not already deleted
    if status != "Posted":
        continue
    if r2_status == "Deleted":
        continue
    if not media_url:
        continue

    # Handle multiple URLs (carousel uses | separator)
    urls_to_delete = [u.strip() for u in media_url.split("|") if u.strip()]
    all_deleted = True

    for url in urls_to_delete:
        success = delete_from_r2(url)
        if not success:
            all_deleted = False

    if all_deleted:
        update_r2_status(row_index, "Deleted")
        deleted_count += 1
    else:
        update_r2_status(row_index, "DeleteFailed")
        failed_count += 1

print(f"R2 Cleanup done — {deleted_count} deleted, {failed_count} failed")

# =========================
# SUMMARY
# =========================

print("\n=================================")
print(f"SCANNER FINISHED — {new_rows_added} new rows added")
print("=================================")
