import json
import time
import bbhash

# ---------------- Utilities ----------------

def str_to_uint64(s):
    encoded = s.encode("utf-8")
    if len(encoded) > 8:
        encoded = encoded[:8]
    return int.from_bytes(encoded, "little") & 0xFFFFFFFFFFFFFFFF


# ---------------- Hybrid Bucket (≤8) ----------------

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

            # Build suffix_array in MPHF-index order
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


# ---------------- Main ----------------

if __name__ == "__main__":
    json_path = input("Enter path to JSON wordlist: ").strip()

    with open(json_path, "r") as f:
        prefix_map = json.load(f)

    print("\nBuilding Hybrid ≤8...")
    table = HybridPrefixTable(prefix_map)

    # Bucket mode distribution
    mode_counts = {"set": 0, "mphf": 0}
    for b in table.buckets.values():
        mode_counts[b.mode] += 1
    print(f"Bucket distribution — set: {mode_counts['set']}, mphf: {mode_counts['mphf']}")

    print("\n--------------------------------------------------")
    print("HOT-PATH lookup timing (Hybrid ≤8, warmed)")
    print("Type 'exit' to stop")
    print("--------------------------------------------------")

    while True:
        word = input(">> ").strip()
        if word == "exit":
            break

        if len(word) < 3:
            print("Word too short (need at least 3 characters for prefix split)")
            continue

        # ---------------- WARM-UP (DO NOT TIME) ----------------
        table.lookup(word)
        table.lookup(word)

        # ---------------- TIMED HOT PATH ----------------
        t0 = time.perf_counter()
        found = table.lookup(word) is not None
        dt = (time.perf_counter() - t0) * 1e6

        print(f"Hybrid ≤8 : {'FOUND' if found else 'NOT FOUND'} | {dt:.2f} µs")