import json
import time
import bbhash

# ---------------- Utilities ----------------

def str_to_uint64(s):
    return int.from_bytes(s.encode("utf-8"), "little") & 0xFFFFFFFFFFFFFFFF


# ---------------- Hybrid Bucket (≤8) ----------------

class SelectiveHybridBucket:
    def __init__(self, suffixes):
        # THRESHOLD = 8 (fixed, same as before)
        if len(suffixes) <= 8:
            self.mode = "tuple"
            self.suffixes = tuple(suffixes)
        else:
            self.mode = "mphf"
            self.suffixes = suffixes
            self.keys = [str_to_uint64(s) for s in suffixes]
            self.mphf = bbhash.PyMPHF(self.keys, len(self.keys), 1.0, 1)

    def lookup(self, suffix):
        if self.mode == "tuple":
            return suffix if suffix in self.suffixes else None

        idx = self.mphf.lookup(str_to_uint64(suffix))
        if idx is None or idx == -1:
            return None
        return self.suffixes[idx]


# ---------------- Prefix Table ----------------

class HybridPrefixTable:
    def __init__(self, prefix_map):
        self.buckets = {
            p: SelectiveHybridBucket(s)
            for p, s in prefix_map.items()
        }

    def lookup(self, word):
        b = self.buckets.get(word[:3])
        if not b:
            return None
        return b.lookup(word[3:])


# ---------------- Main ----------------

if __name__ == "__main__":
    json_path = input("Enter path to JSON wordlist: ").strip()

    with open(json_path, "r") as f:
        prefix_map = json.load(f)

    print("\nBuilding Hybrid ≤8...")
    table = HybridPrefixTable(prefix_map)

    print("\n--------------------------------------------------")
    print("HOT-PATH lookup timing (Hybrid ≤8, warmed)")
    print("Type 'exit' to stop")
    print("--------------------------------------------------")

    while True:
        word = input(">> ").strip()
        if word == "exit":
            break

        # ---------------- WARM-UP (DO NOT TIME) ----------------
        table.lookup(word)
        table.lookup(word)

        # ---------------- TIMED HOT PATH ----------------
        t0 = time.perf_counter()
        found = table.lookup(word) is not None
        dt = (time.perf_counter() - t0) * 1e6

        print(f"Hybrid ≤8 : {'FOUND' if found else 'NOT FOUND'} | {dt:.2f} µs")
