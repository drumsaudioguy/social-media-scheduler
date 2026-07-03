import os
import json
import time
import pandas as pd
import requests
import gspread

from datetime import datetime, timezone
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

service_account_info = json.loads(os.environ["GOOGLE_CREDENTIALS"])

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    service_account_info,
    scope
)

client = gspread.authorize(creds)

sheet = client.open_by_key(os.environ["SPREADSHEET_ID"])

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

    for media_url in media_urls:

        media_url = media_url.strip()

        if not media_url:
            continue

        try:

            parts = media_url.split(".r2.dev/")

            if len(parts) < 2:
                print("R2 DELETE: Could not parse URL:", media_url)
                continue

            file_key = parts[1]

            print("R2 DELETE: Deleting file:", file_key)

            r2_client.delete_object(
                Bucket=R2_BUCKET_NAME,
                Key=file_key
            )

            print("R2 DELETE: Success:", file_key)

        except Exception as e:

            print("R2 DELETE ERROR:", str(e))


# =========================
# TOKEN VALIDATION
# =========================

def validate_token(token, brand):

    try:

        response = requests.get(
            "https://graph.facebook.com/v23.0/me",
            params={
                "access_token": token
            }
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

    worksheet.update_cell(
        row_number,
        10,
        status
    )


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

        expiry = (
            result
            .get("data", {})
            .get("data_access_expires_at")
        )

        if expiry:

            expiry_date = datetime.fromtimestamp(
                expiry
            ).strftime("%d-%m-%Y %H:%M:%S")

            worksheet.update_cell(
                row_number,
                12,
                expiry_date
            )

    except Exception as e:

        print("DATA ACCESS ERROR:", str(e))


def get_token_expiry(access_token):

    try:

        response = requests.get(
            "https://graph.facebook.com/debug_token",
            params={
                "input_token": access_token,
                "access_token": META_USER_TOKEN
            }
        )

        result = response.json()

        print("TOKEN DEBUG RESPONSE:")
        print(result)

        if (
            "data" in result and
            "data_access_expires_at" in result["data"]
        ):

            expiry_timestamp = result["data"][
                "data_access_expires_at"
            ]

            expiry_date = datetime.fromtimestamp(
                expiry_timestamp
            )

            return expiry_date.strftime("%d-%m-%Y")

        return "Unknown"

    except Exception as e:

        print("TOKEN EXPIRY ERROR:", str(e))

        return "Unknown"


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
                f"https://graph.facebook.com/v23.0/{fb_page_id}/video_reels",
                data={
                    "upload_phase": "start",
                    "access_token": access_token
                }
            )

            upload_result = upload_response.json()

            print("FB Reel Upload Start:", upload_result)

            if "video_id" not in upload_result:
                print("FB REEL ERROR: No video_id")
                return None

            video_id = upload_result["video_id"]

            finish_response = requests.post(
                f"https://graph.facebook.com/v23.0/{fb_page_id}/video_reels",
                data={
                    "upload_phase": "finish",
                    "video_id": video_id,
                    "video_state": "PUBLISHED",
                    "description": caption,
                    "file_url": media_url,
                    "access_token": access_token
                }
            )

            finish_result = finish_response.json()

            print("FB Reel Finish:", finish_result)

            if finish_result.get("success"):
                return video_id

            return None

        # ---- SINGLE IMAGE ----
        elif len(media_urls) == 1:

            media_url = media_urls[0].strip()

            print("FB: Posting image:", media_url)

            response = requests.post(
                f"https://graph.facebook.com/v23.0/{fb_page_id}/photos",
                data={
                    "url": media_url,
                    "caption": caption,
                    "access_token": access_token
                }
            )

            result = response.json()

            print("FB Image Result:", result)

            return result.get("post_id") or result.get("id")

        # ---- CAROUSEL ----
        else:

            photo_ids = []

            for media_url in media_urls:

                media_url = media_url.strip()

                if not media_url:
                    continue

                photo_response = requests.post(
                    f"https://graph.facebook.com/v23.0/{fb_page_id}/photos",
                    data={
                        "url": media_url,
                        "published": "false",
                        "access_token": access_token
                    }
                )

                photo_result = photo_response.json()

                print("FB Carousel Photo:", photo_result)

                if "id" in photo_result:
                    photo_ids.append(
                        {"media_fbid": photo_result["id"]}
                    )

            if not photo_ids:
                print("FB CAROUSEL ERROR: No photos uploaded")
                return None

            feed_response = requests.post(
                f"https://graph.facebook.com/v23.0/{fb_page_id}/feed",
                data={
                    "message": caption,
                    "attached_media": json.dumps(photo_ids),
                    "access_token": access_token
                }
            )

            feed_result = feed_response.json()

            print("FB Carousel Feed:", feed_result)

            return feed_result.get("id")

    except Exception as e:

        print("FB POST ERROR:", str(e))

        return None


# =========================
# PROCESS POSTS
# =========================

for index, row in df.iterrows():

    try:

        print("---------------------------------")
        print("Row:", index + 2)
        print(
            "Time:",
            datetime.now(
                ZoneInfo("Asia/Kolkata")
            ).strftime("%d-%m-%Y %H:%M:%S")
        )

        status = str(row["Status"]).strip()

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
        ).replace(
            tzinfo=ZoneInfo("Asia/Kolkata")
        )

        current_time = datetime.now(
            ZoneInfo("Asia/Kolkata")
        )

        print("Scheduled:", publish_datetime)
        print("Current:", current_time)
        print("Timezone:", current_time.tzinfo)

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

        caption = str(row["Caption"]).strip()

        media_urls = str(row["MediaURLs"]).split("|")

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

            if "error" in create_result:
                print("REEL ERROR:")
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
            # R2 CLEANUP
            # =========================

            print("Cleaning up R2 files...")

            urls_to_delete = [
                u.strip()
                for u in media_urls
                if u.strip() != ""
            ]

            delete_r2_files(urls_to_delete)

            worksheet.update_cell(index + 2, 14, "Deleted")

            # =========================
            # FACEBOOK POSTING
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

        else:

            worksheet.update_cell(index + 2, 8, "Failed")

            print("INSTAGRAM POST FAILED")

    except Exception as e:

        print("ERROR:", str(e))


print("=================================")
print("SCHEDULER FINISHED")
print("=================================")
