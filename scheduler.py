import os
import pandas as pd
import requests

PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
IG_ACCOUNT_ID = os.getenv("IG_ACCOUNT_ID")

print("STARTING INSTAGRAM TEST")

df = pd.read_csv("posts.csv")

row = df.iloc[0]

image_url = row["ImageURLs"]
caption = row["Caption"]

print("Image URL:", image_url)
print("Caption:", caption)

response = requests.post(
    f"https://graph.facebook.com/v23.0/{IG_ACCOUNT_ID}/media",
    data={
        "image_url": image_url,
        "caption": caption,
        "access_token": PAGE_ACCESS_TOKEN
    }
)

print("MEDIA RESPONSE")
print(response.text)

print("FINISHED")
