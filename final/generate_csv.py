import json
import time
import csv
import bbhash
import tracemalloc
import psutil
import os

# ---------------- Utilities ----------------

def str_to_uint64(s):
    return int.from_bytes(s.encode("utf-8"), "little") & 0xFFFFFFFFFFFFFFFF

def rss_mb():
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

class NormalPrefixTable:
    def __init__(self, prefix_map):
        self.buckets = {p: MPHFBucket(s) for p, s in prefix_map.items()}

    def lookup(self, word):
        return self.buckets.get(word[:3], None) and \
               self.buckets[word[:3]].lookup(word[3:])


class HybridPrefixTable:
    def __init__(self, prefix_map, threshold):
        self.buckets = {
            p: SelectiveHybridBucket(s, threshold)
            for p, s in prefix_map.items()
        }

    def lookup(self, word):
        return self.buckets.get(word[:3], None) and \
               self.buckets[word[:3]].lookup(word[3:])

# ---------------- Benchmark Runner ----------------

def benchmark(wordlist_name, json_path, writer):
    with open(json_path) as f:
        prefix_map = json.load(f)

    # expand all words once (for lookup benchmark)
    words = [p + s for p, suffs in prefix_map.items() for s in suffs]

    print(f"\n▶ {wordlist_name}: {len(words)} words")

    def run(label, build_fn):
        tracemalloc.start()
        rss_before = rss_mb()

        t0 = time.time()
        table = build_fn()
        build_time = time.time() - t0

        rss_after = rss_mb()
        _, py_peak = tracemalloc.get_traced_memory()

        # lookup benchmark
        t0 = time.time()
        for w in words:
            table.lookup(w)
        lookup_time = time.time() - t0

        tracemalloc.stop()

        writer.writerow([
            wordlist_name,
            label,
            round(build_time, 3),
            round(lookup_time, 3),
            round(py_peak / 1024 / 1024, 2),
            round(rss_after - rss_before, 2)
        ])

    run("Normal MPHF", lambda: NormalPrefixTable(prefix_map))
    run("Hybrid ≤3",    lambda: HybridPrefixTable(prefix_map, 3))
    run("Hybrid ≤8",    lambda: HybridPrefixTable(prefix_map, 8))

# ---------------- Main ----------------

if __name__ == "__main__":
    wordlists = {
        "TWL06":   "/home/asmita/Desktop/DS WORK/twl06.json",
        "German":  "/home/asmita/Desktop/DS WORK/wordlist_german.json",
        "SOWPODS": "/home/asmita/Desktop/DS WORK/sowpods.json",
        "French":  "/home/asmita/Desktop/DS WORK/ODS_french.json",
        "Italian": "/home/asmita/Desktop/DS WORK/italian.json"
    }

    output_csv = "mphf_final_comparison.csv"

    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Wordlist",
            "Structure",
            "BuildTime_s",
            "LookupTime_s",
            "PythonPeak_MB",
            "RSSIncrease_MB"
        ])

        for name, path in wordlists.items():
            benchmark(name, path, writer)

    print(f"\n✅ DONE — results written to: {output_csv}")
