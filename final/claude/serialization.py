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
            return {"mode": "mphf", "original": self.original}

    @classmethod
    def from_dict(cls, data):
        obj = cls.__new__(cls)
        if data["mode"] == "set":
            obj.mode = "set"
            obj.suffixes = frozenset(data["suffixes"])
        else:
            obj.mode = "mphf"
            obj.original = data["original"]
            keys = [str_to_uint64(s) for s in data["original"]]
            n = len(data["original"])
            obj.mphf = bbhash.PyMPHF(keys, n, 1.0, 1)
            obj.suffix_array = [None] * n
            for s in data["original"]:
                idx = obj.mphf.lookup(str_to_uint64(s))
                obj.suffix_array[idx] = s
        return obj


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

    @classmethod
    def load_pickle(cls, path):
        with open(path, "rb") as f:
            data = pickle.load(f)
        obj = cls.__new__(cls)
        obj.buckets = {p: SelectiveHybridBucket.from_dict(d) for p, d in data.items()}
        return obj


if __name__ == "__main__":
    json_path  = input("Enter path to JSON wordlist: ").strip()
    out_pickle = "hybrid_saved.pkl"

    with open(json_path) as f:
        prefix_map = json.load(f)

    original_size_mb = os.path.getsize(json_path) / 1024 / 1024

    # Build
    print("\nBuilding Hybrid...")
    t0 = time.perf_counter()
    hybrid = HybridPrefixTable(prefix_map)
    build_time = time.perf_counter() - t0

    # Save
    print("Saving pickle...")
    t0 = time.perf_counter()
    hybrid.save_pickle(out_pickle)
    save_time = time.perf_counter() - t0
    pickle_size_mb = os.path.getsize(out_pickle) / 1024 / 1024

    # Load
    print("Loading pickle...")
    t0 = time.perf_counter()
    hybrid_loaded = HybridPrefixTable.load_pickle(out_pickle)
    load_time = time.perf_counter() - t0

    # Verify correctness
    test_words = ["adieu", "blue", "clams", "prune", "insidious", "asdada", "glen", "prude", "violin"]
    print("\nVerifying correctness...")
    all_ok = True
    for word in test_words:
        orig = hybrid.lookup(word) is not None
        loaded = hybrid_loaded.lookup(word) is not None
        status = "OK" if orig == loaded else "MISMATCH"
        if status == "MISMATCH":
            all_ok = False
        print(f"  {word:<15} original={orig} loaded={loaded} [{status}]")

    print(f"\nAll correct: {all_ok}")

    # Report
    print("\n" + "=" * 60)
    print(f"{'Metric':<35} {'Value':>20}")
    print("-" * 60)
    print(f"{'Original JSON size':<35} {original_size_mb:>18.2f} MB")
    print(f"{'Pickle file size':<35} {pickle_size_mb:>18.2f} MB")
    print(f"{'Size reduction':<35} {((original_size_mb - pickle_size_mb)/original_size_mb)*100:>17.1f} %")
    print("-" * 60)
    print(f"{'Build time':<35} {build_time:>18.3f} s")
    print(f"{'Save time':<35} {save_time:>18.3f} s")
    print(f"{'Load time':<35} {load_time:>18.3f} s")
    print(f"{'Load speedup vs Build':<35} {build_time/load_time:>17.2f}x")
    print("=" * 60)