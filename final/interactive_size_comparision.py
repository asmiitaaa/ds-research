import json
import time
import bbhash

# ---------------- Utilities ----------------

def str_to_uint64(s):
    return int.from_bytes(s.encode("utf-8"), "little") & 0xFFFFFFFFFFFFFFFF

# ---------------- Buckets ----------------

class SelectiveHybridBucket:
    def __init__(self, suffixes, threshold):
        if len(suffixes) <= threshold:
            self.mode = "tuple"
            self.tuple_suffixes = tuple(suffixes)
        else:
            self.mode = "mphf"
            self.suffixes = suffixes
            self.keys = [str_to_uint64(s) for s in suffixes]
            self.mphf = bbhash.PyMPHF(self.keys, len(self.keys), 1.0, 1)

    def lookup(self, suffix):
        if self.mode == "tuple":
            return suffix if suffix in self.tuple_suffixes else None

        idx = self.mphf.lookup(str_to_uint64(suffix))
        if idx is None or idx == -1:
            return None
        return self.suffixes[idx]

# ---------------- Table ----------------

class HybridPrefixTable:
    def __init__(self, prefix_map, threshold):
        self.buckets = {
            p: SelectiveHybridBucket(s, threshold)
            for p, s in prefix_map.items()
        }

    def lookup(self, word):
        b = self.buckets.get(word[:3])
        return None if not b else b.lookup(word[3:])

# ---------------- Main ----------------

if __name__ == "__main__":
    json_path = input("Enter path to JSON wordlist: ").strip()
    with open(json_path) as f:
        prefix_map = json.load(f)

    thresholds = [1, 3, 8, 15, 21]
    tables = {}

    print("\nBuilding hybrid tables...")
    for t in thresholds:
        t0 = time.time()
        tables[t] = HybridPrefixTable(prefix_map, t)
        print(f"  Threshold ≤{t} built in {time.time() - t0:.3f} sec")

    print("\n--------------------------------------------------")
    print("Enter words to look up (type 'exit' to stop)")
    print("--------------------------------------------------")

    while True:
        word = input(">> ").strip()
        if word == "exit":
            break

        print(f"\nWord: {word}")
        for t in thresholds:
            table = tables[t]
            t0 = time.perf_counter()
            found = table.lookup(word) is not None
            dt = (time.perf_counter() - t0) * 1e6
            print(f"  Hybrid ≤{t:<2} : {'FOUND' if found else 'NOT FOUND'} | {dt:.2f} µs")
