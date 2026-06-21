import os
import json
import time
import pandas as pd
import requests
import gspread

from datetime import datetime
from zoneinfo import ZoneInfo
from oauth2client.service_account import ServiceAccountCredentials

print("=================================")
print("SOCIAL MEDIA SCHEDULER V5")
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
        "ig_id": os.getenv("MEINL_PERC_IG_ID")
    },

    "Meinl Cymbals": {
        "token": os.getenv("MEINL_CYM_TOKEN"),
        "ig_id": os.getenv("MEINL_CYM_IG_ID")
    },

    "Pearl": {
        "token": os.getenv("PEARL_TOKEN"),
        "ig_id": os.getenv("PEARL_IG_ID")
    },

    "Konig": {
        "token": os.getenv("KM_TOKEN"),
        "ig_id": os.getenv("KM_IG_ID")
    },

    # Backward Compatibility

    "Meinl Percussion India": {
        "token": os.getenv("MEINL_PERC_TOKEN"),
        "ig_id": os.getenv("MEINL_PERC_IG_ID")
    },

    "Meinl Cymbals India": {
        "token": os.getenv("MEINL_CYM_TOKEN"),
        "ig_id": os.getenv("MEINL_CYM_IG_ID")
    },

    "Pearl Drums India": {
        "token": os.getenv("PEARL_TOKEN"),
        "ig_id": os.getenv("PEARL_IG_ID")
    },

    "Konig & Meyer India": {
        "token": os.getenv("KM_TOKEN"),
        "ig_id": os.getenv("KM_IG_ID")
    }

}

# =========================
# META USER TOKEN
# =========================

META_USER_TOKEN = os.getenv(
    "META_USER_TOKEN"
)

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


def update_data_access_expiry(
    token,
    row_number
):

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
            .get("expires_at")
        )

        if expiry:

            expiry_date = datetime.fromtimestamp(
                expiry
            ).strftime(
                "%d-%m-%Y %H:%M:%S"
            )

            worksheet.update_cell(
                row_number,
                12,
                expiry_date
            )

    except Exception as e:

        print(
            "DATA ACCESS ERROR:",
            str(e)
        )


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

            return expiry_date.strftime(
                "%d-%m-%Y"
            )

        return "Unknown"

    except Exception as e:

        print(
            "TOKEN EXPIRY ERROR:",
            str(e)
        )

        return "Unknown"


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

        status = str(row["Status"]).strip()

        post_id = str(row["PostID"]).strip()

        if status == "Posted":
            continue

        if status != "Approved":
            continue

        if post_id != "":
            print(
                "ALREADY POSTED - SKIPPING"
            )
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

        ACCESS_TOKEN = BRANDS[brand]["token"]
        IG_ACCOUNT_ID = BRANDS[brand]["ig_id"]

        worksheet.update_cell(
            index + 2,
            10,
            "Checking"
        )

        token_ok = validate_token(
            ACCESS_TOKEN,
            brand
        )

        update_last_check(
            index + 2
        )

        if token_ok:

            update_token_status(
                index + 2,
                "Valid"
            )

            update_data_access_expiry(
                ACCESS_TOKEN,
                index + 2
            )

        else:

            update_token_status(
                index + 2,
                "Invalid"
            )

        if not token_ok:

            worksheet.update_cell(
                index + 2,
                8,
                "Failed"
            )

            continue

        content_type = str(row["ContentType"]).strip()

        caption = str(row["Caption"]).strip()

        media_urls = str(
            row["MediaURLs"]
        ).split("|")

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

                worksheet.update_cell(
                    index + 2,
                    8,
                    "Failed"
                )

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

                worksheet.update_cell(
                    index + 2,
                    8,
                    "Failed"
                )

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

                print(
                    "Creating carousel image:",
                    media_url
                )

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

                    media_ids.append(
                        create_result["id"]
                    )

            if len(media_ids) == 0:

                worksheet.update_cell(
                    index + 2,
                    8,
                    "Failed"
                )

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

                worksheet.update_cell(
                    index + 2,
                    8,
                    "Failed"
                )

                continue

            publish_response = requests.post(
                f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media_publish",
                data={
                    "creation_id": carousel_result["id"],
                    "access_token": ACCESS_TOKEN
                }
            )

            publish_result = publish_response.json()

        print("Publish Result:")
        print(publish_result)

        if "id" in publish_result:

            worksheet.update_cell(
                index + 2,
                8,
                "Posted"
            )

            worksheet.update_cell(
                index + 2,
                9,
                publish_result["id"]
            )

            print("POSTED SUCCESSFULLY")

        else:

            worksheet.update_cell(
                index + 2,
                8,
                "Failed"
            )

            print("POST FAILED")

    except Exception as e:

        print("ERROR:", str(e))


print("=================================")
print("SCHEDULER FINISHED")
print("=================================")
