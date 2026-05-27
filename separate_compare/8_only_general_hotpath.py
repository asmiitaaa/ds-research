import json
import time
import bbhash
import random

# ---------------- Utilities ----------------

def str_to_uint64(s):
    encoded = s.encode("utf-8")
    if len(encoded) > 8:
        encoded = encoded[:8]
    return int.from_bytes(encoded, "little") & 0xFFFFFFFFFFFFFFFF


# ---------------- Hybrid Bucket ----------------

class SelectiveHybridBucket:
    THRESHOLD = 8

    def __init__(self, suffixes):
        if len(suffixes) <= self.THRESHOLD:
            self.mode = "set"
            self.suffixes = frozenset(suffixes)
        else:
            self.mode = "mphf"
            n = len(suffixes)
            keys = [str_to_uint64(s) for s in suffixes]
            self.mphf = bbhash.PyMPHF(keys, n, 1.0, 1)

            self.suffix_array = [None] * n
            for s in suffixes:
                idx = self.mphf.lookup(str_to_uint64(s))
                self.suffix_array[idx] = s

    def lookup(self, suffix):
        if self.mode == "set":
            return suffix if suffix in self.suffixes else None

        idx = self.mphf.lookup(str_to_uint64(suffix))
        if idx is None or idx == -1:
            return None
        if idx >= len(self.suffix_array):
            return None
        return suffix if self.suffix_array[idx] == suffix else None


# ---------------- Prefix Table ----------------

class HybridPrefixTable:
    def __init__(self, prefix_map):
        self.buckets = {
            p: SelectiveHybridBucket(s)
            for p, s in prefix_map.items()
        }

    def lookup(self, word):
        if len(word) < 3:
            return None
        b = self.buckets.get(word[:3])
        if not b:
            return None
        return b.lookup(word[3:])


# ---------------- Trie ----------------

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


# ---------------- Main ----------------

json_path = "/home/asmita/Desktop/DS WORK/twl06.json"

with open(json_path) as f:
    prefix_map = json.load(f)

# Build hybrid
print("Building Hybrid...")
hybrid = HybridPrefixTable(prefix_map)

# Build trie
print("Building Trie...")
trie = Trie()
for p, suffixes in prefix_map.items():
    for s in suffixes:
        trie.insert(p + s)

# One-time general warm-up: touch a random sample of all words
print("Warming cache...")
all_words = [p + s for p, suffixes in prefix_map.items() for s in suffixes]
warm_sample = random.sample(all_words, min(5000, len(all_words)))
for w in warm_sample:
    hybrid.lookup(w)
    trie.search(w)

print("Cache warmed.\n")

# ---------------- Test words ----------------
test_words = ["adieu", "blue", "clams", "prune", "insidious", "asdada", "glen", "prude", "violin"]

print(f"{'Word':<15} {'Hybrid':>12} {'Trie':>12} {'Speedup':>10}")
print("-" * 52)

for word in test_words:
    t0 = time.perf_counter()
    h_found = hybrid.lookup(word) is not None
    h_dt = (time.perf_counter() - t0) * 1e6

    t0 = time.perf_counter()
    t_found = trie.search(word)
    t_dt = (time.perf_counter() - t0) * 1e6

    speedup = t_dt / h_dt if h_dt > 0 else float("inf")
    status = "FOUND" if h_found else "NOT FOUND"
    print(f"{word:<15} {h_dt:>10.2f}µs {t_dt:>10.2f}µs {speedup:>9.2f}x  ({status})")