import json
import time
import bbhash

# ---------------- Utilities ----------------

def str_to_uint64(s):
    return int.from_bytes(s.encode("utf-8"), "little") & 0xFFFFFFFFFFFFFFFF

# ---------------- Buckets ----------------

class MPHFBucket:
    def __init__(self, suffixes):
        self.suffixes = suffixes
        self.keys = [str_to_uint64(s) for s in suffixes]
        self.mphf = bbhash.PyMPHF(self.keys, len(self.keys), 1.0, 1)

    def lookup(self, suffix):
        idx = self.mphf.lookup(str_to_uint64(suffix))
        if idx is None or idx == -1:
            return None
        return self.suffixes[idx]


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

# ---------------- Tables ----------------

class NormalPrefixTable:
    def __init__(self, prefix_map):
        self.buckets = {p: MPHFBucket(s) for p, s in prefix_map.items()}

    def lookup(self, word):
        b = self.buckets.get(word[:3])
        return None if not b else b.lookup(word[3:])


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

    all_words = [p + s for p, lst in prefix_map.items() for s in lst]
    print(f"\nPrefixes   : {len(prefix_map)}")
    print(f"Total words: {len(all_words)}\n")

    # Normal MPHF
    normal = NormalPrefixTable(prefix_map)
    t0 = time.perf_counter()
    for w in all_words:
        normal.lookup(w)
    normal_time = time.perf_counter() - t0

    print(f"Normal MPHF lookup time : {normal_time:.3f} sec")

    # Hybrid thresholds
    for th in [1, 3, 8, 15, 21]:
        hybrid = HybridPrefixTable(prefix_map, th)
        t0 = time.perf_counter()
        for w in all_words:
            hybrid.lookup(w)
        t = time.perf_counter() - t0
        print(f"Hybrid ≤{th} lookup time : {t:.3f} sec")
