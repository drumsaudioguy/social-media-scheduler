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
    }
}

for index, row in df.iterrows():

    try:

        status = str(row["Status"]).strip()

        if status != "Approved":
            continue

        publish_datetime = datetime.strptime(
            f"{row['PublishDate']} {row['PublishTime']}",
            "%d/%m/%Y %H:%M"
        )

        current_time = datetime.now()

        if current_time < publish_datetime:
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

            if not media_url:
                continue

            print("Creating Media:", media_url)

            response = requests.post(
                f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media",
                data={
                    "image_url": media_url,
                    "access_token": ACCESS_TOKEN
                }
            )

            result = response.json()

            print(result)

            if "id" in result:
                media_ids.append(result["id"])

        if len(media_ids) == 0:
            worksheet.update_cell(
                index + 2,
                9,
                "Failed"
            )
            continue

        if len(media_ids) == 1:

            publish_response = requests.post(
                f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media_publish",
                data={
                    "creation_id": media_ids[0],
                    "access_token": ACCESS_TOKEN
                }
            )

            publish_result = publish_response.json()

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
                continue

            publish_response = requests.post(
                f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media_publish",
                data={
                    "creation_id": carousel_result["id"],
                    "access_token": ACCESS_TOKEN
                }
            )

            publish_result = publish_response.json()

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

        print("ERROR:", e)

print("=================================")
print("SCHEDULER FINISHED")
print("=================================")
