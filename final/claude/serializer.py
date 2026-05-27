import json
import time
import bbhash
import pickle
import os

def str_to_uint64(s):
    encoded = s.encode("utf-8")
    if len(encoded) > 8:
        encoded = encoded[:8]
    return int.from_bytes(encoded, "little") & 0xFFFFFFFFFFFFFFFF

class SelectiveHybridBucket:
    THRESHOLD = 8

    def __init__(self, suffixes):
        if len(suffixes) <= self.THRESHOLD:
            self.mode = "set"
            self.suffixes = frozenset(suffixes)
        else:
            self.mode = "mphf"
            n = len(suffixes)
            self.original = list(suffixes)
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

    def to_dict(self):
        if self.mode == "set":
            return {"mode": "set", "suffixes": list(self.suffixes)}
        else:
            # Store only original — suffix_array reconstructed on load
            return {"mode": "mphf", "original": self.original}


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

    def save_pickle(self, path):
        data = {p: b.to_dict() for p, b in self.buckets.items()}
        with open(path, "wb") as f:
            pickle.dump(data, f)


if __name__ == "__main__":
    json_path  = input("Enter path to JSON wordlist: ").strip()
    output_dir = input("Enter output directory to save pickle: ").strip()
    out_pickle = os.path.join(output_dir, "hybrid_saved.pkl")

    with open(json_path) as f:
        prefix_map = json.load(f)

    original_size_mb = os.path.getsize(json_path) / 1024 / 1024

    print("\nBuilding Hybrid...")
    t0 = time.perf_counter()
    hybrid = HybridPrefixTable(prefix_map)
    build_time = time.perf_counter() - t0
    print(f"Build time        : {build_time:.3f} s")

    print("Saving pickle...")
    t0 = time.perf_counter()
    hybrid.save_pickle(out_pickle)
    save_time = time.perf_counter() - t0

    pickle_size_mb = os.path.getsize(out_pickle) / 1024 / 1024

    print(f"Saved to          : {out_pickle}")
    print(f"Save time         : {save_time:.3f} s")
    print(f"Original JSON size: {original_size_mb:.2f} MB")
    print(f"Pickle file size  : {pickle_size_mb:.2f} MB")