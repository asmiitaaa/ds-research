import json
import time
import bbhash

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

# ---------------- Collect inputs FIRST ----------------

json_path = input("Enter path to JSON wordlist: ").strip()

print("Enter words to look up (one per line, empty line to start):")
test_words = []
while True:
    w = input().strip()
    if w == "":
        break
    test_words.append(w)

# ---------------- Now build and warm — no input() after this ----------------

with open(json_path) as f:
    prefix_map = json.load(f)

print("\nBuilding Hybrid...")
hybrid = HybridPrefixTable(prefix_map)

print("Warming Hybrid (full wordlist)...")
all_words = [p + s for p, suffixes in prefix_map.items() for s in suffixes]
for w in all_words:
    hybrid.lookup(w)

print("Ready.\n")

# ---------------- Timed lookups ----------------

print(f"{'Word':<15} {'Result':>10} {'Time':>10}")
print("-" * 38)

for word in test_words:
    if len(word) < 3:
        print(f"{word:<15} {'TOO SHORT':>10}")
        continue
    t0 = time.perf_counter()
    found = hybrid.lookup(word) is not None
    dt = (time.perf_counter() - t0) * 1e6
    print(f"{word:<15} {'FOUND' if found else 'NOT FOUND':>10} {dt:>8.2f} µs")