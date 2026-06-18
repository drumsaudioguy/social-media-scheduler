import os
import json
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

    # Backward compatibility

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

# PROCESS POSTS

for index, row in df.iterrows():

    try:

        status = str(row["Status"]).strip()

        if status != "Approved":
            continue

        date_string = f"{row['PublishDate']} {row['PublishTime']}"

        publish_datetime = None

        try:
            publish_datetime = datetime.strptime(
                date_string,
                "%d/%m/%Y %H:%M"
            )
        except:
            pass

        if publish_datetime is None:
            try:
                publish_datetime = datetime.strptime(
                    date_string,
                    "%Y-%m-%d %H:%M"
                )
            except:
                pass

        if publish_datetime is None:
            print("INVALID DATE FORMAT:", date_string)
            continue

        current_time = datetime.now()

        print("Scheduled:", publish_datetime)
        print("Current:", current_time)

        if current_time < publish_datetime:
            print("Not yet time to publish.")
            continue

        brand = str(row["Brand"]).strip()

        if brand not in BRANDS:
            print("Unknown Brand:", brand)
            continue

        ACCESS_TOKEN = BRANDS[brand]["token"]
        IG_ACCOUNT_ID = BRANDS[brand]["ig_id"]

        caption = str(row["Caption"])

        media_urls = str(row["MediaURLs"]).split("|")

        media_ids = []

        for media_url in media_urls:

            media_url = media_url.strip()

            if media_url == "":
                continue

            print("Creating media:", media_url)

            create_response = requests.post(
                f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media",
                data={
                    "image_url": media_url,
                    "access_token": ACCESS_TOKEN
                }
            )

            create_result = create_response.json()

            print(create_result)

            if "id" in create_result:
                media_ids.append(create_result["id"])

        if len(media_ids) == 0:

            worksheet.update_cell(
                index + 2,
                8,
                "Failed"
            )

            print("No media created.")
            continue

        # SINGLE IMAGE

        if len(media_ids) == 1:

            container_id = media_ids[0]

            publish_response = requests.post(
                f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media_publish",
                data={
                    "creation_id": container_id,
                    "access_token": ACCESS_TOKEN
                }
            )

            publish_result = publish_response.json()

        # CAROUSEL

        else:

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
