import sys
import json
import time
import bbhash

def str_to_uint64(s):
    return int.from_bytes(s.encode("utf-8"), "little") & 0xFFFFFFFFFFFFFFFF

# ---------------- Hybrid Bucket ----------------

class SelectiveHybridBucket:
    def __init__(self, suffixes, threshold=8):
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

# ---------------- Prefix Table ----------------

class HybridPrefixTable:
    def __init__(self, prefix_map, threshold=8):
        self.buckets = {
            p: SelectiveHybridBucket(s, threshold)
            for p, s in prefix_map.items()
        }

    def lookup(self, word):
        if len(word) < 3:
            return None
        bucket = self.buckets.get(word[:3])
        return None if not bucket else bucket.lookup(word[3:])

# ---------------- Main ----------------

if __name__ == "__main__":
    json_path = sys.argv[1]

    with open(json_path, "r") as f:
        prefix_map = json.load(f)

    t0 = time.time()
    table = HybridPrefixTable(prefix_map, threshold=8)
    build_time = time.time() - t0

    # 🔴 REQUIRED READY LINE
    print(f"READY HYBRID {build_time:.3f}", flush=True)

    while True:
        line = sys.stdin.readline()
        if not line:
            break

        word = line.strip()
        if word == "exit":
            break

        t0 = time.perf_counter()
        found = table.lookup(word) is not None
        dt = (time.perf_counter() - t0) * 1e6

        print(f"HYBRID {1 if found else 0} {dt:.2f}", flush=True)
