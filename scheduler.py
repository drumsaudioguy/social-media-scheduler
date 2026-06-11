import os
import pandas as pd
import requests
from datetime import datetime

PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
IG_ACCOUNT_ID = os.getenv("IG_ACCOUNT_ID")

print("Starting scheduler...")
print("IG Account ID:", IG_ACCOUNT_ID)

df = pd.read_csv("posts.csv")

for index, row in df.iterrows():

```
print("\n--------------------------------")
print("Processing row:", index)
print(row)

if str(row["Status"]).strip() != "Approved":
    print("Skipping: Status is not Approved")
    continue

publish_dt = datetime.strptime(
    f"{row['PublishDate']} {row['PublishTime']}",
    "%Y-%m-%d %H:%M"
)

print("Publish Date:", publish_dt)
print("Current Date:", datetime.now())

if datetime.now() < publish_dt:
    print("Skipping: Publish time not reached")
    continue

image_urls = str(row["ImageURLs"]).split("|")

print("Images found:", len(image_urls))

media_ids = []

for image_url in image_urls:

    print("Creating media container for:", image_url)

    create_url = f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media"

    payload = {
        "image_url": image_url.strip(),
        "access_token": PAGE_ACCESS_TOKEN
    }

    response = requests.post(create_url, data=payload)

    print("Response:", response.text)

    result = response.json()

    if "id" not in result:
        print("ERROR creating media container")
        continue

    media_ids.append(result["id"])

print("Media IDs:", media_ids)

if len(media_ids) == 0:
    print("No media containers created")
    continue

if len(media_ids) == 1:

    print("Publishing SINGLE image")

    publish_url = f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media_publish"

    publish_payload = {
        "creation_id": media_ids[0],
        "access_token": PAGE_ACCESS_TOKEN
    }

    publish_response = requests.post(
        publish_url,
        data=publish_payload
    )

    print("Publish response:", publish_response.text)

else:

    print("Publishing CAROUSEL")

    carousel_url = f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media"

    payload = {
        "media_type": "CAROUSEL",
        "children": ",".join(media_ids),
        "caption": row["Caption"],
        "access_token": PAGE_ACCESS_TOKEN
    }

    carousel_response = requests.post(
        carousel_url,
        data=payload
    )

    print("Carousel response:", carousel_response.text)

    carousel = carousel_response.json()

    if "id" not in carousel:
        print("Carousel creation failed")
        continue

    publish_url = f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media_publish"

    publish_payload = {
        "creation_id": carousel["id"],
        "access_token": PAGE_ACCESS_TOKEN
    }

    publish_response = requests.post(
        publish_url,
        data=publish_payload
    )

    print("Publish response:", publish_response.text)

df.loc[index, "Status"] = "Posted"
```

df.to_csv("posts.csv", index=False)

print("Scheduler finished")
