import json
import psutil
import os
import marisa_trie

process = psutil.Process(os.getpid())

json_path = input("Enter path to JSON wordlist: ").strip()
with open(json_path) as f:
    prefix_map = json.load(f)

# Flatten prefix map → full words
words = []
for p, suffixes in prefix_map.items():
    for s in suffixes:
        words.append(p + s)

rss_before = process.memory_info().rss / (1024 * 1024)

trie = marisa_trie.Trie(words)

rss_after = process.memory_info().rss / (1024 * 1024)

print(f"DAWG RSS increase: {rss_after - rss_before:.2f} MB")
