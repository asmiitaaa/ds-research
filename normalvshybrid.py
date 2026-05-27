import json
import time
import bbhash
import tracemalloc

# ---------------- Utilities ----------------

def str_to_uint64(s):
    """Convert a string to a consistent 64-bit integer for bbhash."""
    return int.from_bytes(s.encode("utf-8"), "little") & 0xFFFFFFFFFFFFFFFF


# ---------------- Normal MPHF Bucket ----------------

class MPHFBucket:
    """Always uses MPHF for suffixes."""
    def __init__(self, suffixes):
        self.suffixes = suffixes
        self.keys = [str_to_uint64(s) for s in suffixes]
        self.mphf = bbhash.PyMPHF(self.keys, len(self.keys), 1.0, 1)

    def lookup(self, suffix):
        idx = self.mphf.lookup(str_to_uint64(suffix))
        if idx == -1:
            return None
        return self.suffixes[idx]


# ---------------- Selective Hybrid Bucket ----------------

class SelectiveHybridBucket:
    """
    Uses tuple membership ONLY for very small buckets (≤ 3),
    MPHF for all others.
    """
    def __init__(self, suffixes, small_threshold=3):
        self.size = len(suffixes)

        if self.size <= small_threshold:
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
            if idx == -1:
                return None
            return self.suffixes[idx]


# ---------------- Prefix Tables ----------------

class NormalPrefixTable:
    """Prefix → MPHF bucket"""
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
    """Prefix → Selective hybrid bucket"""
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


# ---------------- Benchmark ----------------

def benchmark(table, word_list):
    start = time.time()
    verified = sum(1 for w in word_list if table.lookup(w) is not None)
    lookup_time = time.time() - start
    return verified, lookup_time


# ---------------- Main ----------------

if __name__ == "__main__":
    json_path = input("Enter path to JSON wordlist: ")
    with open(json_path, "r") as f:
        prefix_map = json.load(f)

    word_list = [
        p + s
        for p, suffixes in prefix_map.items()
        for s in suffixes
    ]

    print(f"\nPrefixes   : {len(prefix_map)}")
    print(f"Total words: {len(word_list)}")

    tracemalloc.start()

    # --- Normal MPHF ---
    normal_table = NormalPrefixTable(prefix_map)
    verified1, lookup1 = benchmark(normal_table, word_list)
    _, mem1 = tracemalloc.get_traced_memory()

    print("\n=== Normal Suffix-Level MPHF ===")
    print(f"Build time : {normal_table.build_time:.3f} sec")
    print(f"Lookup time: {lookup1:.3f} sec")
    print(f"Verified   : {verified1}/{len(word_list)}")
    print(f"Peak memory: {mem1 / 1024 / 1024:.2f} MB")

    # --- Reset peak to avoid cumulative effect ---
    tracemalloc.reset_peak()

    # --- Hybrid MPHF ---
    hybrid_table = HybridPrefixTable(prefix_map, threshold=3)
    verified2, lookup2 = benchmark(hybrid_table, word_list)
    _, mem2 = tracemalloc.get_traced_memory()

    print("\n=== Selective Hybrid (≤3 tuple, else MPHF) ===")
    print(f"Build time : {hybrid_table.build_time:.3f} sec")
    print(f"Lookup time: {lookup2:.3f} sec")
    print(f"Verified   : {verified2}/{len(word_list)}")
    print(f"Peak memory: {mem2 / 1024 / 1024:.2f} MB")

    tracemalloc.stop()
