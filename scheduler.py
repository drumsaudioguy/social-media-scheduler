import os
import pandas as pd
import requests
from datetime import datetime

GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTxlq2ZA3rHKKWWu188u3uXYndlBlCs0wmQChH-Tz-Hg-BNxdyjTbWOCkJI2b5HfT3vC2WAnjqgnBta/pub?output=csv"

PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
IG_ACCOUNT_ID = os.getenv("IG_ACCOUNT_ID")

print("Loading Google Sheet...")

df = pd.read_csv(GOOGLE_SHEET_URL)

print(df)

for index, row in df.iterrows():

    status = str(row["Status"]).strip()

    if status != "Approved":
        continue

    publish_dt = datetime.strptime(
        f"{row['PublishDate']} {row['PublishTime']}",
        "%Y-%m-%d %H:%M"
    )

    if datetime.now() < publish_dt:
        continue

    media_urls = str(row["MediaURLs"]).split("|")

    media_ids = []

    for media_url in media_urls:

        media_url = media_url.strip()

        print("Creating media:", media_url)

        response = requests.post(
            f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media",
            data={
                "image_url": media_url,
                "access_token": PAGE_ACCESS_TOKEN
            }
        )

        result = response.json()

        print(result)

        if "id" not in result:
            continue

        media_ids.append(result["id"])

    if len(media_ids) == 0:
        continue

    # SINGLE IMAGE

    if len(media_ids) == 1:

        publish_response = requests.post(
            f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media_publish",
            data={
                "creation_id": media_ids[0],
                "access_token": PAGE_ACCESS_TOKEN
            }
        )

        print(publish_response.text)

    # CAROUSEL

    else:

        carousel_response = requests.post(
            f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media",
            data={
                "media_type": "CAROUSEL",
                "children": ",".join(media_ids),
                "caption": row["Caption"],
                "access_token": PAGE_ACCESS_TOKEN
            }
        )

        carousel = carousel_response.json()

        print(carousel)

        if "id" not in carousel:
            continue

        publish_response = requests.post(
            f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media_publish",
            data={
                "creation_id": carousel["id"],
                "access_token": PAGE_ACCESS_TOKEN
            }
        )

        print(publish_response.text)

print("Finished")
