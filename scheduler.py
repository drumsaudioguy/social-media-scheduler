import os
import pandas as pd
import requests

PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
IG_ACCOUNT_ID = os.getenv("IG_ACCOUNT_ID")

print("STARTING INSTAGRAM PUBLISH TEST")

df = pd.read_csv("posts.csv")

row = df.iloc[0]

image_url = row["ImageURLs"]
caption = row["Caption"]

create_response = requests.post(
f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media",
data={
"image_url": image_url,
"caption": caption,
"access_token": PAGE_ACCESS_TOKEN
}
)

print("CREATE RESPONSE")
print(create_response.text)

creation_id = create_response.json()["id"]

publish_response = requests.post(
f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media_publish",
data={
"creation_id": creation_id,
"access_token": PAGE_ACCESS_TOKEN
}
)

print("PUBLISH RESPONSE")
print(publish_response.text)

print("DONE")
