import os
import json
import time
import pandas as pd
import requests
import gspread

from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials

print("=================================")
print("SOCIAL MEDIA SCHEDULER STARTED")
print("=================================")

# GOOGLE AUTH

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

# BRAND CONFIGURATION

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

for index, row in df.iterrows():

    try:

        status = str(row["Status"]).strip()

        if status != "Approved":
            continue

        publish_datetime = datetime.strptime(
            f"{row['PublishDate']} {row['PublishTime']}",
            "%d-%m-%Y %H:%M"
        )

        if datetime.now() < publish_datetime:
            continue

        brand = str(row["Brand"]).strip()

        if brand not in BRANDS:
            print("Unknown Brand:", brand)
            continue

        ACCESS_TOKEN = BRANDS[brand]["token"]
        IG_ACCOUNT_ID = BRANDS[brand]["ig_id"]

        content_type = str(row["ContentType"]).strip()
        caption = str(row["Caption"]).strip()
        media_url = str(row["MediaURLs"]).strip()

        print("Brand:", brand)
        print("Type:", content_type)

        # =========================
        # REELS
        # =========================

        if content_type == "Reel":

            print("Creating Reel...")

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

            print("Waiting for Instagram processing...")
            time.sleep(180)

            publish_response = requests.post(
                f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media_publish",
                data={
                    "creation_id": creation_id,
                    "access_token": ACCESS_TOKEN
                }
            )

            publish_result = publish_response.json()

            print(publish_result)

        else:

            print("Non-reel content")
            continue

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
