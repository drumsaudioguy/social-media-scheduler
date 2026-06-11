import os
import pandas as pd
import requests
from datetime import datetime

PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
IG_ACCOUNT_ID = os.getenv("IG_ACCOUNT_ID")

print("=== STARTING SCHEDULER ===")

print("IG_ACCOUNT_ID:", IG_ACCOUNT_ID)

df = pd.read_csv("posts.csv")

for index, row in df.iterrows():

    print(f"\nProcessing row {index}")

    status = str(row["Status"]).strip()

    print("Status:", status)

    if status != "Approved":
        print("Skipped - Not Approved")
        continue

    publish_dt = datetime.strptime(
        f"{row['PublishDate']} {row['PublishTime']}",
        "%Y-%m-%d %H:%M"
    )

    print("Publish Date:", publish_dt)
    print("Current Date:", datetime.now())

    if datetime.now() < publish_dt:
        print("Skipped - Publish time not reached")
        continue

    image_urls = str(row["ImageURLs"]).split("|")

    print("Images:", image_urls)

    media_ids = []

    for image_url in image_urls:

        image_url = image_url.strip()

        print("Creating media:", image_url)

        response = requests.post(
            f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media",
            data={
                "image_url": image_url,
                "access_token": PAGE_ACCESS_TOKEN
            }
        )

        print("Instagram Response:")
        print(response.text)

        result = response.json()

        if "id" not in result:
            print("FAILED TO CREATE MEDIA")
            continue

        media_ids.append(result["id"])

    print("Media IDs:", media_ids)

    if len(media_ids) == 0:
        print("No valid media found")
        continue

    if len(media_ids) == 1:

        print("Publishing single image")

        publish_response = requests.post(
            f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media_publish",
            data={
                "creation_id": media_ids[0],
                "access_token": PAGE_ACCESS_TOKEN
            }
        )

        print(publish_response.text)

    else:

        print("Publishing carousel")

        carousel_response = requests.post(
            f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media",
            data={
                "media_type": "CAROUSEL",
                "children": ",".join(media_ids),
                "caption": row["Caption"],
                "access_token": PAGE_ACCESS_TOKEN
            }
        )

        print("Carousel Response:")
        print(carousel_response.text)

        carousel = carousel_response.json()

        if "id" not in carousel:
            print("Carousel creation failed")
            continue

        publish_response = requests.post(
            f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media_publish",
            data={
                "creation_id": carousel["id"],
                "access_token": PAGE_ACCESS_TOKEN
            }
        )

        print("Publish Response:")
        print(publish_response.text)

    print("Marking as Posted")

    df.loc[index, "Status"] = "Posted"

df.to_csv("posts.csv", index=False)

print("=== FINISHED ===")
