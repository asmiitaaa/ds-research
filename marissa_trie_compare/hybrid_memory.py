import json
import psutil
import os
from hybrid_only import HybridPrefixTable   # or paste class directly

process = psutil.Process(os.getpid())

json_path = input("Enter path to JSON wordlist: ").strip()
with open(json_path) as f:
    prefix_map = json.load(f)

rss_before = process.memory_info().rss / (1024 * 1024)

table = HybridPrefixTable(prefix_map, threshold=8)

rss_after = process.memory_info().rss / (1024 * 1024)

print(f"Hybrid MPHF (≤8) RSS increase: {rss_after - rss_before:.2f} MB")
