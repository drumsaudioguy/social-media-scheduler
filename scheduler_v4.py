import os
import json
import time
import pandas as pd
import requests
import gspread

from datetime import datetime, timedelta
from urllib.parse import unquote
import boto3
from zoneinfo import ZoneInfo
from oauth2client.service_account import ServiceAccountCredentials

print("=================================")
print("SOCIAL MEDIA SCHEDULER V7")
print("=================================")

# =========================
# GOOGLE AUTH
# =========================

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

service_account_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(os.environ["GOOGLE_SHEET_ID"])
worksheet = sheet.worksheet("Sheet1")
data = worksheet.get_all_records()
df = pd.DataFrame(data)
print(df)

# =========================
# BRANDS
# =========================

BRANDS = {
    "Meinl Percussion": {
        "token": os.getenv("MEINL_PERC_TOKEN"),
        "ig_id": os.getenv("MEINL_PERC_IG_ID"),
        "fb_page_id": "1491070334469768"
    },
    "Meinl Cymbals": {
        "token": os.getenv("MEINL_CYM_TOKEN"),
        "ig_id": os.getenv("MEINL_CYM_IG_ID"),
        "fb_page_id": "1493683980877757"
    },
    "Pearl": {
        "token": os.getenv("PEARL_TOKEN"),
        "ig_id": os.getenv("PEARL_IG_ID"),
        "fb_page_id": "983549558331087"
    },
    "Konig": {
        "token": os.getenv("KM_TOKEN"),
        "ig_id": os.getenv("KM_IG_ID"),
        "fb_page_id": "101189549616697"
    },
    "MSB": {
        "token": os.getenv("MSB_TOKEN"),
        "ig_id": os.getenv("MSB_IG_ID"),
        "fb_page_id": "331266536738875"
    },
    "Meinl Sticks and Brush India": {
        "token": os.getenv("MSB_TOKEN"),
        "ig_id": os.getenv("MSB_IG_ID"),
        "fb_page_id": "331266536738875"
    },
    # Backward Compatibility
    "Meinl Percussion India": {
        "token": os.getenv("MEINL_PERC_TOKEN"),
        "ig_id": os.getenv("MEINL_PERC_IG_ID"),
        "fb_page_id": "1491070334469768"
    },
    "Meinl Cymbals India": {
        "token": os.getenv("MEINL_CYM_TOKEN"),
        "ig_id": os.getenv("MEINL_CYM_IG_ID"),
        "fb_page_id": "1493683980877757"
    },
    "Pearl Drums India": {
        "token": os.getenv("PEARL_TOKEN"),
        "ig_id": os.getenv("PEARL_IG_ID"),
        "fb_page_id": "983549558331087"
    },
    "Konig & Meyer India": {
        "token": os.getenv("KM_TOKEN"),
        "ig_id": os.getenv("KM_IG_ID"),
        "fb_page_id": "101189549616697"
    },
    "Meinl Stick and Brush": {
        "token": os.getenv("MSB_TOKEN"),
        "ig_id": os.getenv("MSB_IG_ID"),
        "fb_page_id": "331266536738875"
    }
}

# =========================
# CONFIG
# =========================

META_USER_TOKEN    = os.getenv("META_USER_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")
UPTIME_PING_URL    = os.getenv("UPTIME_PING_URL")

# =========================
# R2 CLIENT
# =========================

R2_ACCOUNT_ID        = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID     = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME       = os.getenv("R2_BUCKET_NAME")

r2_client = boto3.client(
    "s3",
    endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    region_name="auto"
)

# =========================
# RUN COUNTERS
# =========================

posted_count  = 0
failed_count  = 0
skipped_count = 0

# =========================
# TELEGRAM
# =========================

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML"
            },
            timeout=10
        )
    except Exception as e:
        print("TELEGRAM ERROR:", str(e))

# =========================
# R2 DELETE
# =========================

def delete_r2_files(media_urls):
    all_success = True
    for media_url in media_urls:
        media_url = media_url.strip()
        if not media_url:
            continue
        try:
            parts = media_url.split(".r2.dev/")
            if len(parts) < 2:
                print("R2 DELETE: Could not parse URL:", media_url)
                all_success = False
                continue
            file_key = unquote(parts[1])
            print("R2 DELETE: Deleting file:", file_key)
            r2_client.delete_object(Bucket=R2_BUCKET_NAME, Key=file_key)
            print("R2 DELETE: Success:", file_key)
        except Exception as e:
            print("R2 DELETE ERROR:", str(e))
            all_success = False
    return all_success

# =========================
# TOKEN VALIDATION
# =========================

def validate_token(token, brand):
    try:
        response = requests.get(
            "https://graph.facebook.com/v23.0/me",
            params={"access_token": token}
        )
        result = response.json()
        if "error" in result:
            print("=================================")
            print("TOKEN FAILED:", brand)
            print(result)
            print("=================================")
            send_telegram(
                f"❌ <b>TOKEN FAILED</b>: {brand}\n"
                f"{result.get('error', {}).get('message', '')}"
            )
            return False
        print("TOKEN OK:", brand)
        return True
    except Exception as e:
        print("TOKEN CHECK ERROR:", brand, str(e))
        return False


def update_token_status(row_number, status):
    worksheet.update_cell(row_number, 10, status)


def update_last_check(row_number):
    worksheet.update_cell(
        row_number, 11,
        datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d-%m-%Y %H:%M:%S")
    )


def update_data_access_expiry(token, row_number, brand):
    try:
        response = requests.get(
            "https://graph.facebook.com/debug_token",
            params={"input_token": token, "access_token": META_USER_TOKEN}
        )
        result = response.json()
        print("TOKEN DEBUG:")
        print(result)
        expiry = result.get("data", {}).get("data_access_expires_at")
        if expiry:
            expiry_dt = datetime.fromtimestamp(expiry)
            expiry_date = expiry_dt.strftime("%d-%m-%Y %H:%M:%S")
            worksheet.update_cell(row_number, 12, expiry_date)
            days_left = (expiry_dt - datetime.now()).days
            if days_left <= 7:
                msg = (
                    f"⚠️ <b>TOKEN EXPIRING SOON</b>: {brand}\n"
                    f"Expires: {expiry_date} ({days_left} days left)"
                )
                print(msg)
                send_telegram(msg)
    except Exception as e:
        print("DATA ACCESS ERROR:", str(e))

# =========================
# CAPTION VALIDATION
# =========================

def validate_caption(caption, brand):
    if len(caption) > 2200:
        msg = f"⚠️ Caption too long for {brand} ({len(caption)} chars, max 2200)"
        print(msg)
        send_telegram(msg)
    hashtag_count = caption.count("#")
    if hashtag_count > 30:
        msg = f"⚠️ Too many hashtags for {brand} ({hashtag_count}, max 30)"
        print(msg)
        send_telegram(msg)

# =========================
# REEL STATUS POLLING
# =========================

def wait_for_media_ready(creation_id, access_token, max_wait=300):
    print("Polling media status...")
    elapsed = 0
    while elapsed < max_wait:
        response = requests.get(
            f"https://graph.facebook.com/v23.0/{creation_id}",
            params={"fields": "status_code,status", "access_token": access_token}
        )
        result = response.json()
        status_code = result.get("status_code")
        print(f"  Media status: {status_code} ({elapsed}s elapsed)")
        if status_code == "FINISHED":
            return True
        elif status_code == "ERROR":
            print("  Media processing ERROR:", result)
            return False
        time.sleep(30)
        elapsed += 30
    print("  Media processing TIMEOUT after", max_wait, "seconds")
    return False

# =========================
# PUBLISH WITH RETRY
# =========================

def publish_with_retry(ig_account_id, creation_id, access_token, retries=3):
    for attempt in range(1, retries + 1):
        print(f"Publishing attempt {attempt}/{retries}...")
        response = requests.post(
            f"https://graph.facebook.com/v23.0/{ig_account_id}/media_publish",
            data={"creation_id": creation_id, "access_token": access_token}
        )
        result = response.json()
        if "id" in result:
            return result
        print(f"  Attempt {attempt} failed:", result)
        if attempt < retries:
            time.sleep(30)
    return result

# =========================
# FACEBOOK POSTING
# =========================

def post_to_facebook(content_type, media_urls, caption, access_token, fb_page_id):
    try:
        # ---- REEL ----
        if content_type.lower() == "reel":
            media_url = media_urls[0].strip()
            print("FB: Uploading reel:", media_url)
            upload_response = requests.post(
                f"https://graph.facebook.com/v23.0/{fb_page_id}/videos",
                data={
                    "file_url": media_url,
                    "description": caption,
                    "published": "true",
                    "access_token": access_token
                }
            )
            upload_result = upload_response.json()
            print("FB Reel Result:", upload_result)
            if "id" in upload_result:
                return upload_result["id"]
            print("FB REEL FAILED:", upload_result)
            return None

        # ---- SINGLE IMAGE ----
        elif len(media_urls) == 1:
            media_url = media_urls[0].strip()
            print("FB: Uploading image:", media_url)
            photo_response = requests.post(
                f"https://graph.facebook.com/v23.0/{fb_page_id}/photos",
                data={
                    "url": media_url,
                    "caption": caption,
                    "published": "true",
                    "access_token": access_token
                }
            )
            photo_result = photo_response.json()
            print("FB Image Result:", photo_result)
            if "id" in photo_result:
                return photo_result["id"]
            print("FB IMAGE FAILED:", photo_result)
            return None

        # ---- CAROUSEL ----
        else:
            fb_photo_ids = []
            for media_url in media_urls:
                media_url = media_url.strip()
                if not media_url:
                    continue
                print("FB: Uploading carousel image:", media_url)
                photo_response = requests.post(
                    f"https://graph.facebook.com/v23.0/{fb_page_id}/photos",
                    data={
                        "url": media_url,
                        "published": "false",
                        "access_token": access_token
                    }
                )
                photo_result = photo_response.json()
                print("FB Carousel Item:", photo_result)
                if "id" in photo_result:
                    fb_photo_ids.append(photo_result["id"])

            if not fb_photo_ids:
                print("FB CAROUSEL FAILED: No images uploaded")
                return None

            attached_media = [{"media_fbid": pid} for pid in fb_photo_ids]
            feed_response = requests.post(
                f"https://graph.facebook.com/v23.0/{fb_page_id}/feed",
                json={
                    "message": caption,
                    "attached_media": attached_media,
                    "access_token": access_token
                }
            )
            feed_result = feed_response.json()
            print("FB Carousel Result:", feed_result)
            if "id" in feed_result:
                return feed_result["id"]
            print("FB CAROUSEL FAILED:", feed_result)
            return None

    except Exception as e:
        print("FB POST ERROR:", str(e))
        return None

# =========================
# AUTO ARCHIVE
# =========================

def archive_posted_rows():
    try:
        fresh_data = worksheet.get_all_records()
        fresh_df   = pd.DataFrame(fresh_data)

        posted_indices = [
            i for i, row in fresh_df.iterrows()
            if str(row.get("Status", "")).strip() == "Posted"
        ]

        if not posted_indices:
            print("ARCHIVE: No posted rows to archive")
            return

        try:
            archive_ws = sheet.worksheet("Archive")
        except Exception:
            archive_ws = sheet.add_worksheet(title="Archive", rows=1000, cols=20)
            headers = worksheet.row_values(1)
            archive_ws.append_row(headers)

        sheet_row_indices = sorted([i + 2 for i in posted_indices], reverse=True)

        rows_archived = 0
        for row_idx in sheet_row_indices:
            row_data = worksheet.row_values(row_idx)
            archive_ws.append_row(row_data)
            worksheet.delete_rows(row_idx)
            rows_archived += 1

        print(f"ARCHIVE: Moved {rows_archived} posted rows to Archive sheet")
        send_telegram(f"🗂️ Archived {rows_archived} posted rows to Archive sheet")

    except Exception as e:
        print("ARCHIVE ERROR:", str(e))

# =========================
# PROCESS POSTS
# =========================

for index, row in df.iterrows():

    try:

        worksheet.update_cell(
            index + 2, 11,
            datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d-%m-%Y %H:%M:%S")
        )

        status  = str(row["Status"]).strip()
        post_id = str(row["PostID"]).strip()

        if status == "Posted":
            continue

        if status != "Approved":
            continue

        if post_id != "":
            print("ALREADY POSTED - SKIPPING")
            skipped_count += 1
            continue

        # Skip empty MediaURLs
        media_urls_raw = str(row.get("MediaURLs", "")).strip()
        if not media_urls_raw:
            print("SKIPPING: Empty MediaURLs for row", index + 2)
            skipped_count += 1
            continue

        date_string = f"{row['PublishDate']} {row['PublishTime']}"
        publish_datetime = datetime.strptime(
            date_string, "%d-%m-%Y %H:%M"
        ).replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        current_time = datetime.now(ZoneInfo("Asia/Kolkata"))

        print("Scheduled:", publish_datetime)
        print("Current:", current_time)

        if current_time < publish_datetime:
            print("Not yet time to publish.")
            continue

        brand = str(row["Brand"]).strip()

        if brand not in BRANDS:
            print("Unknown Brand:", brand)
            continue

        ACCESS_TOKEN  = BRANDS[brand]["token"]
        IG_ACCOUNT_ID = BRANDS[brand]["ig_id"]
        FB_PAGE_ID    = BRANDS[brand]["fb_page_id"]

        worksheet.update_cell(index + 2, 10, "Checking")
        token_ok = validate_token(ACCESS_TOKEN, brand)
        update_last_check(index + 2)

        if token_ok:
            update_token_status(index + 2, "Valid")
            update_data_access_expiry(ACCESS_TOKEN, index + 2, brand)
        else:
            update_token_status(index + 2, "Invalid")
            worksheet.update_cell(index + 2, 8, "Failed")
            worksheet.update_cell(index + 2, 16, "Token Invalid")
            failed_count += 1
            continue

        content_type = str(row["ContentType"]).strip()
        caption      = str(row["Caption"]).strip()
        media_urls   = media_urls_raw.split("|")

        print("Brand:", brand)
        print("Type:", content_type)

        validate_caption(caption, brand)

        media_ids = []

        # =========================
        # REEL
        # =========================

        if content_type.lower() == "reel":

            media_url = media_urls[0].strip()
            print("Creating reel:", media_url)

            create_response = requests.post(
                f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media",
                data={
                    "media_type": "REELS",
                    "video_url": media_url,
                    "caption": caption,
                    "access_token": ACCESS_TOKEN
                }
            )
            create_result = create_response.json()
            print(create_result)

            if "id" not in create_result:
                err = str(create_result.get("error", {}).get("message", "Container failed"))
                worksheet.update_cell(index + 2, 8, "Failed")
                worksheet.update_cell(index + 2, 16, err)
                failed_count += 1
                send_telegram(f"❌ <b>REEL FAILED</b>: {brand}\n{err}")
                continue

            creation_id = create_result["id"]
            ready = wait_for_media_ready(creation_id, ACCESS_TOKEN, max_wait=300)

            if not ready:
                worksheet.update_cell(index + 2, 8, "Failed")
                worksheet.update_cell(index + 2, 16, "Reel processing failed or timed out")
                failed_count += 1
                send_telegram(f"❌ <b>REEL TIMEOUT</b>: {brand}")
                continue

            publish_result = publish_with_retry(IG_ACCOUNT_ID, creation_id, ACCESS_TOKEN)

        # =========================
        # SINGLE IMAGE
        # =========================

        elif len(media_urls) == 1:

            media_url = media_urls[0].strip()
            print("Creating image:", media_url)

            create_response = requests.post(
                f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media",
                data={
                    "image_url": media_url,
                    "caption": caption,
                    "access_token": ACCESS_TOKEN
                }
            )
            create_result = create_response.json()
            print(create_result)

            if "id" not in create_result:
                err = str(create_result.get("error", {}).get("message", "Container failed"))
                worksheet.update_cell(index + 2, 8, "Failed")
                worksheet.update_cell(index + 2, 16, err)
                failed_count += 1
                send_telegram(f"❌ <b>IMAGE FAILED</b>: {brand}\n{err}")
                continue

            print("Waiting for image processing...")
            time.sleep(30)

            publish_result = publish_with_retry(IG_ACCOUNT_ID, create_result["id"], ACCESS_TOKEN)

        # =========================
        # CAROUSEL
        # =========================

        else:

            for media_url in media_urls:
                media_url = media_url.strip()
                if not media_url:
                    continue
                print("Creating carousel image:", media_url)
                create_response = requests.post(
                    f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media",
                    data={
                        "image_url": media_url,
                        "is_carousel_item": "true",
                        "access_token": ACCESS_TOKEN
                    }
                )
                create_result = create_response.json()
                print(create_result)
                if "id" in create_result:
                    media_ids.append(create_result["id"])

            if not media_ids:
                worksheet.update_cell(index + 2, 8, "Failed")
                worksheet.update_cell(index + 2, 16, "No carousel items created")
                failed_count += 1
                continue

            carousel_response = requests.post(
                f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media",
                data={
                    "media_type": "CAROUSEL",
                    "children": ",".join(media_ids),
                    "caption": caption,
                    "access_token": ACCESS_TOKEN
                }
            )
            carousel_result = carousel_response.json()
            print(carousel_result)

            if "id" not in carousel_result:
                err = str(carousel_result.get("error", {}).get("message", "Carousel failed"))
                worksheet.update_cell(index + 2, 8, "Failed")
                worksheet.update_cell(index + 2, 16, err)
                failed_count += 1
                send_telegram(f"❌ <b>CAROUSEL FAILED</b>: {brand}\n{err}")
                continue

            print("Waiting for carousel processing...")
            time.sleep(30)

            publish_result = publish_with_retry(IG_ACCOUNT_ID, carousel_result["id"], ACCESS_TOKEN)

        # =========================
        # PUBLISH RESULT
        # =========================

        print("Instagram Publish Result:")
        print(publish_result)

        if "id" in publish_result:

            worksheet.update_cell(index + 2, 8, "Posted")
            worksheet.update_cell(index + 2, 9, publish_result["id"])
            posted_count += 1
            print("INSTAGRAM POSTED SUCCESSFULLY")
            send_telegram(
                f"✅ <b>POSTED</b>: {brand} ({content_type})\n"
                f"IG ID: {publish_result['id']}"
            )

            print("Now posting to Facebook...")
            fb_post_id = post_to_facebook(
                content_type, media_urls, caption, ACCESS_TOKEN, FB_PAGE_ID
            )
            if fb_post_id:
                worksheet.update_cell(index + 2, 13, fb_post_id)
                print("FACEBOOK POSTED SUCCESSFULLY:", fb_post_id)
            else:
                print("FACEBOOK POST FAILED - Instagram was still successful")

            print("Cleaning up R2 files...")
            urls_to_delete = [u.strip() for u in media_urls if u.strip()]
            delete_success = delete_r2_files(urls_to_delete)
            worksheet.update_cell(index + 2, 14, "Deleted" if delete_success else "DeleteFailed")

        else:

            err = str(publish_result.get("error", {}).get("message", "Publish failed"))
            worksheet.update_cell(index + 2, 8, "Failed")
            worksheet.update_cell(index + 2, 16, err)
            failed_count += 1
            print("INSTAGRAM POST FAILED")
            send_telegram(f"❌ <b>POST FAILED</b>: {brand} ({content_type})\n{err}")

    except Exception as e:

        print("ERROR:", str(e))
        failed_count += 1

# =========================
# AUTO ARCHIVE
# =========================

archive_posted_rows()

# =========================
# RUN SUMMARY
# =========================

summary = (
    f"📊 <b>Scheduler Run Complete</b>\n"
    f"✅ Posted: {posted_count}\n"
    f"❌ Failed: {failed_count}\n"
    f"⏭️ Skipped: {skipped_count}"
)

print("=================================")
print(f"POSTED: {posted_count} | FAILED: {failed_count} | SKIPPED: {skipped_count}")
print("=================================")

send_telegram(summary)

# =========================
# UPTIME PING
# =========================

if UPTIME_PING_URL:
    try:
        requests.get(UPTIME_PING_URL, timeout=5)
        print("UPTIME PING: Sent")
    except Exception:
        pass

print("=================================")
print("SCHEDULER FINISHED")
print("=================================")
