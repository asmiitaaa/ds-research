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
    """Return total process memory (RSS) in MB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)


# ---------------- Buckets ----------------

class MPHFBucket:
    """Always MPHF + verification (NO false positives)"""
    def __init__(self, suffixes):
        self.suffixes = suffixes
        self.keys = [str_to_uint64(s) for s in suffixes]
        self.mphf = bbhash.PyMPHF(self.keys, len(self.keys), 1.0, 1)

    def lookup(self, suffix):
        idx = self.mphf.lookup(str_to_uint64(suffix))

        if idx is None or idx == -1:
            return None

        if self.suffixes[idx] == suffix:
            return suffix
        return None


class SelectiveHybridBucket:
    """Tuple for size ≤3, MPHF + verification otherwise"""
    def __init__(self, suffixes, threshold=3):
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
        else:
            idx = self.mphf.lookup(str_to_uint64(suffix))

            if idx is None or idx == -1:
                return None

            if self.suffixes[idx] == suffix:
                return suffix
            return None


# ---------------- Prefix Tables ----------------

class NormalPrefixTable:
    def __init__(self, prefix_map):
        self.buckets = {}
        start = time.time()
        for p, s in prefix_map.items():
            self.buckets[p] = MPHFBucket(s)
        self.build_time = time.time() - start

    def lookup(self, word):
        prefix = word[:3]
        suffix = word[3:]
        bucket = self.buckets.get(prefix)
        if not bucket:
            return None
        return bucket.lookup(suffix)


class HybridPrefixTable:
    def __init__(self, prefix_map, threshold=3):
        self.buckets = {}
        start = time.time()
        for p, s in prefix_map.items():
            self.buckets[p] = SelectiveHybridBucket(s, threshold)
        self.build_time = time.time() - start

    def lookup(self, word):
        prefix = word[:3]
        suffix = word[3:]
        bucket = self.buckets.get(prefix)
        if not bucket:
            return None
        return bucket.lookup(suffix)


# ---------------- Main ----------------

if __name__ == "__main__":
    json_path = input("Enter path to JSON wordlist: ")
    with open(json_path, "r") as f:
        prefix_map = json.load(f)

    print(f"\nPrefixes   : {len(prefix_map)}")

    # -------- Build phase --------
    tracemalloc.start()

    rss_before = get_rss_mb()
    print("\nBuilding NORMAL suffix-level MPHF...")
    normal_table = NormalPrefixTable(prefix_map)
    rss_after = get_rss_mb()

    _, peak_py_normal = tracemalloc.get_traced_memory()
    normal_rss = rss_after - rss_before

    tracemalloc.reset_peak()

    rss_before = get_rss_mb()
    print("Building SELECTIVE HYBRID (≤3 tuple, else MPHF)...")
    hybrid_table = HybridPrefixTable(prefix_map, threshold=3)
    rss_after = get_rss_mb()

    _, peak_py_hybrid = tracemalloc.get_traced_memory()
    hybrid_rss = rss_after - rss_before

    print("\n=== Build Summary ===")
    print(f"Normal build time : {normal_table.build_time:.3f} sec")
    print(f"Hybrid build time : {hybrid_table.build_time:.3f} sec")
    print(f"Normal peak Python memory : {peak_py_normal / 1024 / 1024:.2f} MB")
    print(f"Hybrid peak Python memory : {peak_py_hybrid / 1024 / 1024:.2f} MB")
    print(f"Normal RSS increase       : {normal_rss:.2f} MB")
    print(f"Hybrid RSS increase       : {hybrid_rss:.2f} MB")

    print("\n--------------------------------------------------")
    print("Enter words to look up (type 'exit' to stop)")
    print("--------------------------------------------------")

    # -------- Interactive lookup --------
    while True:
        word = input(">> ").strip()
        if word.lower() == "exit":
            break

        # Normal lookup
        t0 = time.perf_counter()
        r1 = normal_table.lookup(word)
        t1 = (time.perf_counter() - t0) * 1e6

        # Hybrid lookup
        t0 = time.perf_counter()
        r2 = hybrid_table.lookup(word)
        t2 = (time.perf_counter() - t0) * 1e6

        print("\nResult:")
        print(f"  Normal MPHF : {'FOUND' if r1 else 'NOT FOUND'} | {t1:.2f} µs")
        print(f"  Hybrid MPHF : {'FOUND' if r2 else 'NOT FOUND'} | {t2:.2f} µs")

    tracemalloc.stop()
