import json

with open("/home/asmita/Desktop/DS WORK/twl06.json") as f:
    pm = json.load(f)

print("blu in keys:", "blu" in pm)
if "blu" in pm:
    print("suffixes for blu:", pm["blu"][:20])
    print("contains 'e':", "e" in pm["blu"])


