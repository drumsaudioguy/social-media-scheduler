import os
import re
import json
import boto3
import gspread
import requests

from google import genai
from google.genai import types

from datetime import datetime, date
from zoneinfo import ZoneInfo
from botocore.config import Config
from urllib.parse import quote
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

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

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
# HELPER: DOWNLOAD FILE FROM R2
# =========================

def download_file(url, suffix):
    """Download a file from R2 using requests and save to a temp file."""
    import tempfile
    headers = {"User-Agent": "Mozilla/5.0 (compatible; R2Scanner/1.0)"}
    response = requests.get(url, headers=headers, timeout=60)
    response.raise_for_status()
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(response.content)
    tmp.flush()
    tmp.close()
    return tmp.name

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
                f"No emojis, no generic phrases. End with exactly 5 relevant hashtags. "
                f"Be original and unexpected. Write like a human, not a marketer. "
                f"One caption only."
            )
            tmp_path = download_file(urls[0], ".mp4")
            uploaded = gemini_client.files.upload(file=tmp_path)
            response = gemini_client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[prompt, uploaded]
            )

        elif content_type == "Image":
            prompt = (
                f"You are a creative social media copywriter for {brand_name}. "
                f"Brand tone: {tone}. "
                f"Look at this image and write one short, punchy caption for an Instagram post. "
                f"No emojis, no generic phrases. End with exactly 5 relevant hashtags. "
                f"Be original and unexpected. Write like a human, not a marketer. "
                f"One caption only."
            )
            suffix = "." + urls[0].split(".")[-1].split("?")[0]
            tmp_path = download_file(urls[0], suffix)
            uploaded = gemini_client.files.upload(file=tmp_path)
            response = gemini_client.models.generate_content(
