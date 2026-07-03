import os
import json
import time
import pandas as pd
import requests
import gspread

from datetime import datetime, timezone
from urllib.parse import unquote
import boto3
from zoneinfo import ZoneInfo
from oauth2client.service_account import ServiceAccountCredentials

print("=================================")
print("SOCIAL MEDIA SCHEDULER V6")
print("=================================")

# =========================
# GOOGLE AUTH
# =========================

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

service_account_info = json.loads(
    os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
)

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
# META USER TOKEN
# =========================

META_USER_TOKEN = os.getenv("META_USER_TOKEN")

# =========================
# R2 CLIENT (boto3)
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

            r2_client.delete_object(
                Bucket=R2_BUCKET_NAME,
                Key=file_key
            )

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

            return False

        print("TOKEN OK:", brand)

        return True

    except Exception as e:

        print("TOKEN CHECK ERROR:", brand)
        print(str(e))

        return False


def update_token_status(row_number, status):

    worksheet.update_cell(row_number, 10, status)


def update_last_check(row_number):

    worksheet.update_cell(
        row_number,
        11,
        datetime.now(
            ZoneInfo("Asia/Kolkata")
        ).strftime("%d-%m-%Y %H:%M:%S")
    )


def update_data_access_expiry(token, row_number):

    try:

        response = requests.get(
            "https://graph.facebook.com/debug_token",
            params={
                "input_token": token,
                "access_token": META_USER_TOKEN
            }
        )

        result = response.json()

        print("TOKEN DEBUG:")
        print(result)

        expiry = result.get("data", {}).get("data_access_expires_at")

        if expiry:

            expiry_date = datetime.fromtimestamp(expiry).strftime(
                "%d-%m-%Y %H:%M:%S"
            )

            worksheet.update_cell(row_number, 12, expiry_date)

    except Exception as e:

        print("DATA ACCESS ERROR:", str(e))


# =========================
# FACEBOOK POSTING
# =========================

def post_to_facebook(
    content_type,
    media_urls,
    caption,
    access_token,
    fb_page_id
):

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
            else:
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
            else:
                print("FB IMAGE FAILED:", photo_result)
                return None

        # ---- CAROUSEL ----
        else:

            fb_photo_ids = []

            for media_url in media_urls:

                media_url = media_url.strip()

                if media_url == "":
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

            if len(fb_photo_ids) == 0:
                print("FB CAROUSEL FAILED: No images uploaded")
                return None

            attached_media = [
                {"media_fbid": pid}
                for pid in fb_photo_ids
            ]

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
            else:
                print("FB CAROUSEL FAILED:", feed_result)
                return None

    except Exception as e:

        print("FB POST ERROR:", str(e))
        return None


# =========================
# PROCESS POSTS
# =========================

for index, row in df.iterrows():

    try:

        worksheet.update_cell(
            index + 2,
            11,
            datetime.now(
                ZoneInfo("Asia/Kolkata")
            ).strftime("%d-%m-%Y %H:%M:%S")
        )

        status  = str(row["Status"]).strip()
        post_id = str(row["PostID"]).strip()

        if status == "Posted":
            continue

        if status != "Approved":
            continue

        if post_id != "":
            print("ALREADY POSTED - SKIPPING")
            continue

        date_string = f"{row['PublishDate']} {row['PublishTime']}"

        publish_datetime = datetime.strptime(
            date_string,
            "%d-%m-%Y %H:%M"
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
            update_data_access_expiry(ACCESS_TOKEN, index + 2)
        else:
            update_token_status(index + 2, "Invalid")

        if not token_ok:
            worksheet.update_cell(index + 2, 8, "Failed")
            continue

        content_type = str(row["ContentType"]).strip()
        caption      = str(row["Caption"]).strip()
        media_urls   = str(row["MediaURLs"]).split("|")

        print("Brand:", brand)
        print("Type:", content_type)

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
                worksheet.update_cell(index + 2, 8, "Failed")
                continue

            creation_id = create_result["id"]

            print("Waiting for reel processing...")

            time.sleep(180)

            publish_response = requests.post(
                f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media_publish",
                data={
                    "creation_id": creation_id,
                    "access_token": ACCESS_TOKEN
                }
            )

            publish_result = publish_response.json()

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
                worksheet.update_cell(index + 2, 8, "Failed")
                continue

            print("Waiting for image processing...")
            time.sleep(30)

            publish_response = requests.post(
                f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media_publish",
                data={
                    "creation_id": create_result["id"],
                    "access_token": ACCESS_TOKEN
                }
            )

            publish_result = publish_response.json()

        # =========================
        # CAROUSEL
        # =========================

        else:

            for media_url in media_urls:

                media_url = media_url.strip()

                if media_url == "":
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

            if len(media_ids) == 0:
                worksheet.update_cell(index + 2, 8, "Failed")
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
                worksheet.update_cell(index + 2, 8, "Failed")
                continue

            publish_response = requests.post(
                f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media_publish",
                data={
                    "creation_id": carousel_result["id"],
                    "access_token": ACCESS_TOKEN
                }
            )

            publish_result = publish_response.json()

        print("Instagram Publish Result:")
        print(publish_result)

        if "id" in publish_result:

            worksheet.update_cell(index + 2, 8, "Posted")
            worksheet.update_cell(index + 2, 9, publish_result["id"])
            print("INSTAGRAM POSTED SUCCESSFULLY")

            # =========================
            # FACEBOOK POSTING
            # (must happen BEFORE R2 delete — FB needs the URLs alive)
            # =========================

            print("Now posting to Facebook...")

            fb_post_id = post_to_facebook(
                content_type,
                media_urls,
                caption,
                ACCESS_TOKEN,
                FB_PAGE_ID
            )

            if fb_post_id:
                worksheet.update_cell(index + 2, 13, fb_post_id)
                print("FACEBOOK POSTED SUCCESSFULLY:", fb_post_id)
            else:
                print("FACEBOOK POST FAILED - Instagram was still successful")

            # =========================
            # R2 CLEANUP
            # (after BOTH Instagram + Facebook are done)
            # =========================

            print("Cleaning up R2 files...")

            urls_to_delete = [
                u.strip()
                for u in media_urls
                if u.strip() != ""
            ]

            delete_success = delete_r2_files(urls_to_delete)

            if delete_success:
                worksheet.update_cell(index + 2, 14, "Deleted")
            else:
                worksheet.update_cell(index + 2, 14, "DeleteFailed")

        else:

            worksheet.update_cell(index + 2, 8, "Failed")
            print("INSTAGRAM POST FAILED")

    except Exception as e:

        print("ERROR:", str(e))


print("=================================")
print("SCHEDULER FINISHED")
print("=================================")
