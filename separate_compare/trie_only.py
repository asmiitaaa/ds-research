import json
import time
import psutil
import os

# ---------- Utilities ----------
def rss_mb():
    return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)

# ---------- Trie ----------
class TrieNode:
    __slots__ = ("children", "end")
    def __init__(self):
        self.children = {}
        self.end = False

class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word):
        node = self.root
        for c in word:
            node = node.children.setdefault(c, TrieNode())
        node.end = True

    def search(self, word):
        node = self.root
        for c in word:
            if c not in node.children:
                return False
            node = node.children[c]
        return node.end

# ---------- Main ----------
json_path = input("Enter path to JSON wordlist: ").strip()

rss_before = rss_mb()
t0 = time.time()

with open(json_path) as f:
    prefix_map = json.load(f)

trie = Trie()
total = 0

for p, suffixes in prefix_map.items():
    for s in suffixes:
        trie.insert(p + s)
        total += 1

build_time = time.time() - t0
rss_after = rss_mb()

print("\n=== TRIE BUILD ===")
print(f"Words      : {total}")
print(f"Build time : {build_time:.3f} sec")
print(f"RSS usage  : {rss_after - rss_before:.2f} MB")

print("\n--------------------------------------------------")
print("Enter words to look up (type 'exit' to stop)")
print("--------------------------------------------------")

while True:
    word = input(">> ").strip()
    if word == "exit":
        break

    t0 = time.perf_counter()
    found = trie.search(word)
    dt = (time.perf_counter() - t0) * 1e6

    print(f"Trie : {'FOUND' if found else 'NOT FOUND'} | {dt:.2f} µs")
