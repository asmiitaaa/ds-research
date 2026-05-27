import json
import time
import bbhash
import tracemalloc
import psutil
import os

# ---------------- Utilities ----------------

def str_to_uint64(s):
    return int.from_bytes(s.encode("utf-8"), "little") & 0xFFFFFFFFFFFFFFFF

def get_rss_mb():
    return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)

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

# ---------------- Prefix Tables ----------------

class PrefixTable:
    def __init__(self, prefix_map, bucket_cls, threshold=None):
        self.buckets = {}
        start = time.time()

        for p, s in prefix_map.items():
            if threshold is None:
                self.buckets[p] = bucket_cls(s)
            else:
                self.buckets[p] = bucket_cls(s, threshold)

        self.build_time = time.time() - start

    def lookup(self, word):
        if len(word) < 3:
            return None
        prefix = word[:3]
        suffix = word[3:]
        bucket = self.buckets.get(prefix)
        if not bucket:
            return None
        return bucket.lookup(suffix)

# ---------------- Main ----------------

if __name__ == "__main__":
    json_path = input("Enter path to JSON wordlist: ").strip()

    with open(json_path, "r") as f:
        prefix_map = json.load(f)

    all_words = [p + s for p, lst in prefix_map.items() for s in lst]

    print(f"\nPrefixes   : {len(prefix_map)}")
    print(f"Total words: {len(all_words)}")

    tracemalloc.start()

    results = []

    def build_and_test(name, table):
        rss_before = get_rss_mb()
        t0 = time.time()
        table_obj = table()
        build_time = time.time() - t0
        rss_after = get_rss_mb()
        _, peak_py = tracemalloc.get_traced_memory()

        # Full lookup
        t0 = time.time()
        for w in all_words:
            table_obj.lookup(w)
        lookup_time = time.time() - t0

        results.append((
            name,
            build_time,
            lookup_time,
            peak_py / 1024 / 1024,
            rss_after - rss_before
        ))

        tracemalloc.reset_peak()

    # ---- Run comparisons ----

    build_and_test(
        "Normal MPHF",
        lambda: PrefixTable(prefix_map, MPHFBucket)
    )

    build_and_test(
        "Hybrid ≤3",
        lambda: PrefixTable(prefix_map, SelectiveHybridBucket, 3)
    )

    build_and_test(
        "Hybrid ≤8",
        lambda: PrefixTable(prefix_map, SelectiveHybridBucket, 8)
    )

    print("\n================ FINAL COMPARISON ================")
    print(f"{'Structure':<15} {'Build(s)':>8} {'Lookup(s)':>10} {'PyPeak(MB)':>12} {'RSS(MB)':>10}")
    print("-" * 60)

    for r in results:
        print(f"{r[0]:<15} {r[1]:>8.3f} {r[2]:>10.3f} {r[3]:>12.2f} {r[4]:>10.2f}")
