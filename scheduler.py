import os
import pandas as pd
import requests
from datetime import datetime

print("================================")
print("SCRIPT STARTED")
print("================================")

PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
IG_ACCOUNT_ID = os.getenv("IG_ACCOUNT_ID")

print("IG_ACCOUNT_ID =", IG_ACCOUNT_ID)

try:
    df = pd.read_csv("posts.csv")

    print("CSV LOADED")
    print(df)

except Exception as e:

    print("CSV ERROR:")
    print(str(e))
    raise

for index, row in df.iterrows():

    print("--------------------------------")
    print("ROW:", index)

    try:

        print(row.to_dict())

        status = str(row["Status"]).strip()

        print("STATUS:", status)

        if status != "Approved":
            print("Skipping row")
            continue

        publish_dt = datetime.strptime(
            f"{row['PublishDate']} {row['PublishTime']}",
            "%Y-%m-%d %H:%M"
        )

        print("Publish Time:", publish_dt)
        print("Current Time:", datetime.now())

        if datetime.now() < publish_dt:
            print("Not time yet")
            continue

        print("POST SHOULD BE PUBLISHED NOW")

    except Exception as e:

        print("ROW ERROR:")
        print(str(e))

print("================================")
print("SCRIPT FINISHED")
print("================================")
