import json
import time
import bbhash
import tracemalloc
import psutil
import os

# ---------------- Utilities ----------------

def str_to_uint64(s):
    """Convert string to stable 64-bit integer"""
    return int.from_bytes(s.encode("utf-8"), "little") & 0xFFFFFFFFFFFFFFFF

def get_rss_mb():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)


# ---------------- Buckets ----------------

class SelectiveHybridBucket:
    """
    Tuple for size ≤3
    MPHF + verification otherwise
    """
    def __init__(self, suffixes, threshold=3):
        self.suffixes = suffixes

        if len(suffixes) <= threshold:
            self.mode = "tuple"
            self.tuple_suffixes = tuple(suffixes)
        else:
            self.mode = "mphf"
            self.keys = [str_to_uint64(s) for s in suffixes]
            self.mphf = bbhash.PyMPHF(self.keys, len(self.keys), 1.0, 1)

    def lookup(self, suffix):
        # tuple case
        if self.mode == "tuple":
            return suffix if suffix in self.tuple_suffixes else None

        # MPHF case
        idx = self.mphf.lookup(str_to_uint64(suffix))

        if idx is None or idx == -1:
            return None

        # 🔒 mandatory verification
        if self.suffixes[idx] == suffix:
            return suffix

        return None


# ---------------- Prefix Table ----------------

class HybridPrefixTable:
    def __init__(self, prefix_map, threshold=3):
        start = time.time()
        self.buckets = {
            p: SelectiveHybridBucket(s, threshold)
            for p, s in prefix_map.items()
        }
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
    json_path = input("Enter path to JSON wordlist: ").strip()

    with open(json_path, "r") as f:
        prefix_map = json.load(f)

    print(f"\nPrefixes   : {len(prefix_map)}")

    tracemalloc.start()
    rss_before = get_rss_mb()

    print("\nBuilding HYBRID MPHF (≤3 tuple, else MPHF)...")
    table = HybridPrefixTable(prefix_map, threshold=3)

    rss_after = get_rss_mb()
    _, peak_py = tracemalloc.get_traced_memory()

    print("\n=== Build Summary ===")
    print(f"Build time           : {table.build_time:.3f} sec")
    print(f"Peak Python memory   : {peak_py / 1024 / 1024:.2f} MB")
    print(f"RSS increase         : {rss_after - rss_before:.2f} MB")

    print("\n--------------------------------------------------")
    print("Enter words to look up (type 'exit' to stop)")
    print("--------------------------------------------------")

    while True:
        word = input(">> ").strip()
        if word.lower() == "exit":
            break

        t0 = time.perf_counter()
        found = table.lookup(word) is not None
        t_us = (time.perf_counter() - t0) * 1e6

        print(
            f"\nResult:\n"
            f"  Hybrid MPHF : {'FOUND' if found else 'NOT FOUND'} | {t_us:.2f} µs"
        )

    tracemalloc.stop()
