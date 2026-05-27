import sys
import json
import time


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


# ---------- MAIN ----------
json_path = input("Enter path to JSON wordlist: ").strip()

with open(json_path) as f:
    prefix_map = json.load(f)

trie = Trie()

for p, suffixes in prefix_map.items():
    for s in suffixes:
        trie.insert(p + s)

print("READY TRIE", flush=True)

while True:
    line = sys.stdin.readline()
    if not line:
        break

    word = line.strip()
    if word == "exit":
        break

    t0 = time.perf_counter()
    found = trie.search(word)
    dt = (time.perf_counter() - t0) * 1e6

    print(f"TRIE {1 if found else 0} {dt:.2f}", flush=True)
