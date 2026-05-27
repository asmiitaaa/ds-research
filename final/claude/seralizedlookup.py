import time
import bbhash
import pickle

def str_to_uint64(s):
    encoded = s.encode("utf-8")
    if len(encoded) > 8:
        encoded = encoded[:8]
    return int.from_bytes(encoded, "little") & 0xFFFFFFFFFFFFFFFF

class SelectiveHybridBucket:
    def lookup(self, suffix):
        if self.mode == "set":
            return suffix if suffix in self.suffixes else None
        idx = self.mphf.lookup(str_to_uint64(suffix))
        if idx is None or idx == -1:
            return None
        if idx >= len(self.suffix_array):
            return None
        return suffix if self.suffix_array[idx] == suffix else None

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
            # Reconstruct suffix_array
            obj.suffix_array = [None] * n
            for s in data["original"]:
                idx = obj.mphf.lookup(str_to_uint64(s))
                obj.suffix_array[idx] = s
        return obj


class HybridPrefixTable:
    def lookup(self, word):
        if len(word) < 3:
            return None
        b = self.buckets.get(word[:3])
        if not b:
            return None
        return b.lookup(word[3:])

    @classmethod
    def load_pickle(cls, path):
        with open(path, "rb") as f:
            data = pickle.load(f)
        obj = cls.__new__(cls)
        obj.buckets = {p: SelectiveHybridBucket.from_dict(d) for p, d in data.items()}
        return obj


if __name__ == "__main__":
    pickle_path = input("Enter path to pickle file: ").strip()

    print("\nLoading Hybrid from pickle...")
    t0 = time.perf_counter()
    hybrid = HybridPrefixTable.load_pickle(pickle_path)
    load_time = time.perf_counter() - t0
    print(f"Load time : {load_time:.3f} s")

    # Full wordlist warm-up from loaded buckets
    print("Warming cache (full wordlist)...")
    for prefix, bucket in hybrid.buckets.items():
        if bucket.mode == "set":
            for s in bucket.suffixes:
                hybrid.lookup(prefix + s)
        else:
            for s in bucket.original:
                hybrid.lookup(prefix + s)

    print("Ready.\n")

    test_words = ["adieu", "blue", "clams", "prune", "insidious", "asdada", "glen", "prude", "violin"]

    print(f"{'Word':<15} {'Result':>10} {'Time':>10}")
    print("-" * 38)

    for word in test_words:
        t0 = time.perf_counter()
        found = hybrid.lookup(word) is not None
        dt = (time.perf_counter() - t0) * 1e6
        print(f"{word:<15} {'FOUND' if found else 'NOT FOUND':>10} {dt:>8.2f} µs")