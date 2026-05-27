import json
import time
import bbhash
import psutil
import os
import sys

def str_to_uint64(s):
    encoded = s.encode("utf-8")
    if len(encoded) > 8:
        encoded = encoded[:8]
    return int.from_bytes(encoded, "little") & 0xFFFFFFFFFFFFFFFF

class MPHFBucket:
    def __init__(self, suffixes):
        n = len(suffixes)
        keys = [str_to_uint64(s) for s in suffixes]
        self.mphf = bbhash.PyMPHF(keys, n, 1.0, 1)
        self.suffix_array = [None] * n
        for s in suffixes:
            idx = self.mphf.lookup(str_to_uint64(s))
            self.suffix_array[idx] = s

    def lookup(self, suffix):
        idx = self.mphf.lookup(str_to_uint64(suffix))
        if idx is None or idx == -1:
            return None
        if idx >= len(self.suffix_array):
            return None
        return suffix if self.suffix_array[idx] == suffix else None

class SelectiveHybridBucket:
    def __init__(self, suffixes, threshold):
        if len(suffixes) <= threshold:
            self.mode = "set"
            self.suffixes = frozenset(suffixes)
        else:
            self.mode = "mphf"
            n = len(suffixes)
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

class NormalPrefixTable:
    def __init__(self, prefix_map):
        self.buckets = {p: MPHFBucket(s) for p, s in prefix_map.items()}

    def lookup(self, word):
        if len(word) < 3:
            return None
        b = self.buckets.get(word[:3])
        return None if not b else b.lookup(word[3:])

class HybridPrefixTable:
    def __init__(self, prefix_map, threshold):
        self.buckets = {
            p: SelectiveHybridBucket(s, threshold)
            for p, s in prefix_map.items()
        }

    def lookup(self, word):
        if len(word) < 3:
            return None
        b = self.buckets.get(word[:3])
        return None if not b else b.lookup(word[3:])

# ---------------- Subprocess worker ----------------

if __name__ == "__main__" and len(sys.argv) == 3:
    # Running as subprocess worker
    json_path = sys.argv[1]
    mode = sys.argv[2]  # "normal", "1", "3", "8", "15", "21"

    with open(json_path) as f:
        prefix_map = json.load(f)

    rss_before = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024

    t0 = time.perf_counter()
    if mode == "normal":
        table = NormalPrefixTable(prefix_map)
    else:
        table = HybridPrefixTable(prefix_map, int(mode))
    build_time = time.perf_counter() - t0

    rss_after = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
    rss_delta = rss_after - rss_before

    # Lookup timing
    import random
    all_words = [p + s for p, lst in prefix_map.items() for s in lst]
    warm_sample = random.sample(all_words, min(5000, len(all_words)))
    for w in warm_sample:
        table.lookup(w)
    t0 = time.perf_counter()
    for w in all_words:
        table.lookup(w)
    total_t = time.perf_counter() - t0
    mean_us = (total_t / len(all_words)) * 1e6

    print(f"{build_time:.3f},{rss_delta:.2f},{mean_us:.4f}")
    sys.exit(0)

# ---------------- Main orchestrator ----------------

if __name__ == "__main__":
    import subprocess

    json_path = input("Enter path to JSON wordlist: ").strip()

    configs = [
        ("Normal MPHF", "normal"),
        ("Hybrid ≤1",   "1"),
        ("Hybrid ≤3",   "3"),
        ("Hybrid ≤8",   "8"),
        ("Hybrid ≤15",  "15"),
        ("Hybrid ≤21",  "21"),
    ]

    results = []
    python = sys.executable

    for name, mode in configs:
        print(f"Benchmarking {name}...")
        proc = subprocess.run(
            [python, __file__, json_path, mode],
            capture_output=True, text=True
        )
        build_t, rss_d, mean_us = proc.stdout.strip().split(",")
        results.append((name, float(build_t), float(rss_d), float(mean_us)))

    print("\n" + "=" * 85)
    print(f"{'Structure':<15} {'Build (s)':>10} {'RSS Delta (MB)':>15} {'Mean/word (µs)':>15}")
    print("-" * 85)
    for name, build_t, rss_d, mean_us in results:
        print(f"{name:<15} {build_t:>10.3f} {rss_d:>15.2f} {mean_us:>15.4f}")
    print("=" * 85)