import os

token = os.getenv("PAGE_ACCESS_TOKEN")

print("TOKEN LENGTH:", len(token))
print("FIRST 10 CHARS:", token[:10])
print("LAST 10 CHARS:", token[-10:])
