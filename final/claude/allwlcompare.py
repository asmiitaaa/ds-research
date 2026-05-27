import json
import time
import bbhash
import csv
import os

def str_to_uint64(s):
    encoded = s.encode("utf-8")
    if len(encoded) > 8:\
        encoded = encoded[:8]
    return int.from_bytes(encoded, "little") & 0xFFFFFFFFFFFFFFFF

class SelectiveHybridBucket:
    def __init__(self, suffixes, threshold):
        if len(suffixes) <= threshold:
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
        if not b:
            return None
        return b.lookup(word[3:])


def benchmark(prefix_map, all_words, threshold):
    # Build
    t0 = time.perf_counter()
    table = HybridPrefixTable(prefix_map, threshold)
    build_time = time.perf_counter() - t0

    # Full wordlist warm-up
    for w in all_words:
        table.lookup(w)

    # Timed lookup over full wordlist
    t0 = time.perf_counter()
    for w in all_words:
        table.lookup(w)
    total_time = time.perf_counter() - t0
    mean_us = (total_time / len(all_words)) * 1e6

    # Bucket distribution
    set_buckets  = sum(1 for b in table.buckets.values() if b.mode == "set")
    mphf_buckets = sum(1 for b in table.buckets.values() if b.mode == "mphf")

    return {
        "build_time_s"  : round(build_time, 3),
        "total_lookup_s": round(total_time, 3),
        "mean_lookup_us": round(mean_us, 4),
        "set_buckets"   : set_buckets,
        "mphf_buckets"  : mphf_buckets,
    }


if __name__ == "__main__":
    # Add as many wordlist paths as you want
    wordlist_paths = []
    print("Enter wordlist paths one by one (empty line to stop):")
    while True:
        p = input("Path: ").strip()
        if p == "":
            break
        wordlist_paths.append(p)

    thresholds  = [3, 8, 21]
    output_csv  = "hybrid_comparison.csv"
    rows        = []

    for path in wordlist_paths:
        wordlist_name = os.path.basename(path)
        print(f"\nProcessing {wordlist_name}...")

        with open(path) as f:
            prefix_map = json.load(f)

        all_words = [p + s for p, lst in prefix_map.items() for s in lst]
        total_words    = len(all_words)
        total_prefixes = len(prefix_map)

        for th in thresholds:
            print(f"  Benchmarking Hybrid ≤{th}...")
            result = benchmark(prefix_map, all_words, th)
            rows.append({
                "wordlist"      : wordlist_name,
                "total_words"   : total_words,
                "total_prefixes": total_prefixes,
                "threshold"     : th,
                "build_time_s"  : result["build_time_s"],
                "total_lookup_s": result["total_lookup_s"],
                "mean_lookup_us": result["mean_lookup_us"],
                "set_buckets"   : result["set_buckets"],
                "mphf_buckets"  : result["mphf_buckets"],
            })

    # Write CSV
    fieldnames = [
        "wordlist", "total_words", "total_prefixes", "threshold",
        "build_time_s", "total_lookup_s", "mean_lookup_us",
        "set_buckets", "mphf_buckets"
    ]

    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nResults saved to {output_csv}")

    # Print table
    print(f"\n{'Wordlist':<20} {'Threshold':>10} {'Words':>8} {'Build(s)':>10} {'Mean(µs)':>10} {'Set':>6} {'MPHF':>6}")
    print("-" * 76)
    for row in rows:
        print(f"{row['wordlist']:<20} {row['threshold']:>10} {row['total_words']:>8} "
              f"{row['build_time_s']:>10.3f} {row['mean_lookup_us']:>10.4f} "
              f"{row['set_buckets']:>6} {row['mphf_buckets']:>6}")