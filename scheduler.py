import os
import pandas as pd
import requests
from datetime import datetime

PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
IG_ACCOUNT_ID = os.getenv("IG_ACCOUNT_ID")

df = pd.read_csv("posts.csv")

for index, row in df.iterrows():

    if row["Status"] != "Approved":
        continue

    publish_dt = datetime.strptime(
        f"{row['PublishDate']} {row['PublishTime']}",
        "%Y-%m-%d %H:%M"
    )

    if datetime.now() < publish_dt:
        continue

    image_urls = row["ImageURLs"].split("|")

    media_ids = []

    for image_url in image_urls:

        create_url = f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media"

        payload = {
            "image_url": image_url,
            "access_token": PAGE_ACCESS_TOKEN
        }

        response = requests.post(create_url, data=payload)
        media_ids.append(response.json()["id"])

    carousel_url = f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media"

    payload = {
        "media_type": "CAROUSEL",
        "children": ",".join(media_ids),
        "caption": row["Caption"],
        "access_token": PAGE_ACCESS_TOKEN
    }

    carousel = requests.post(carousel_url, data=payload).json()

    publish_url = f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media_publish"

    publish_payload = {
        "creation_id": carousel["id"],
        "access_token": PAGE_ACCESS_TOKEN
    }

    requests.post(publish_url, data=publish_payload)

    df.loc[index, "Status"] = "Posted"

df.to_csv("posts.csv", index=False)
