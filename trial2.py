import json, time, tracemalloc
import bbhash

# ----------------- Buckets -----------------
class MPHBucket:
    def __init__(self, suffixes):
        self.suffixes = list(suffixes)
        # assign each suffix a unique integer ID
        self.keys = [i for i in range(len(self.suffixes))]
        # build MPHF over these integers
        self.builder = bbhash.PyMPHF(
            self.keys, len(self.keys), 1.0, 1
        )

    def lookup(self, suffix):
        try:
            idx = self.suffixes.index(suffix)  # linear inside bucket
            return self.suffixes[idx]
        except ValueError:
            return None


# ----------------- Data Structures -----------------
class PrefixDict:
    """Normal dict at prefix level, MPHF at suffix level"""
    def __init__(self, prefix_map):
        self.buckets = {}
        for prefix, suffixes in prefix_map.items():
            self.buckets[prefix] = MPHBucket(suffixes)

    def lookup(self, prefix, suffix):
        if prefix not in self.buckets:
            return None
        return self.buckets[prefix].lookup(suffix)


class PrefixAlgo3:
    """Algo3 MPHF at prefix level, MPHF at suffix level"""
    def __init__(self, prefix_map):
        self.prefixes = list(prefix_map.keys())
        prefix_ids = list(range(len(self.prefixes)))
        self.prefix_to_suffix = prefix_map
        self.builder = bbhash.PyMPHF(
            prefix_ids, len(prefix_ids), 1.0, 1
        )
        # buckets indexed by prefix index
        self.buckets = [None] * len(self.prefixes)
        for idx, prefix in enumerate(self.prefixes):
            self.buckets[idx] = MPHBucket(prefix_map[prefix])

    def lookup(self, prefix, suffix):
        try:
            idx = self.prefixes.index(prefix)
        except ValueError:
            return None
        return self.buckets[idx].lookup(suffix)


# ----------------- Benchmark Helper -----------------
def benchmark_with_memory(table_cls, prefix_map, words, label):
    tracemalloc.start()
    t0 = time.time()
    table = table_cls(prefix_map)
    t1 = time.time()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    correct = 0
    for prefix, suffix in words:
        if table.lookup(prefix, suffix):
            correct += 1
    t2 = time.time()

    print(f"\n=== {label} ===")
    print(f"Build time: {t1 - t0:.3f} sec")
    print(f"Lookup time: {t2 - t1:.3f} sec")
    print(f"Verified: {correct}/{len(words)}")
    print(f"Memory usage: {current / 1024 / 1024:.2f} MB "
          f"(peak {peak / 1024 / 1024:.2f} MB)")


# ----------------- Main -----------------
if __name__ == "__main__":
    path = input("Enter path to JSON file (prefix -> suffixes): ").strip()
    with open(path, "r") as f:
        prefix_map = json.load(f)

    total_words = sum(len(v) for v in prefix_map.values())
    words = [(p, s) for p, suffixes in prefix_map.items() for s in suffixes]

    print(f"Loaded {len(prefix_map)} prefixes from {path}")
    print(f"Total word pairs: {total_words}")

    benchmark_with_memory(PrefixDict, prefix_map, words, "Normal Prefix + MPHF Suffix")
    benchmark_with_memory(PrefixAlgo3, prefix_map, words, "Algo3 Prefix + MPHF Suffix")
