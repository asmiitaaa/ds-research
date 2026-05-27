import json
import time
import bbhash
import tracemalloc

# ---------------- Utilities ----------------

def str_to_uint64(s):
    """Convert a string to a consistent 64-bit integer for bbhash."""
    return int.from_bytes(s.encode("utf-8"), "little") & 0xFFFFFFFFFFFFFFFF

# ---------------- Bucket Classes ----------------

class GenericMPHFBucket:
    """Each bucket uses a generic MPHF for suffixes."""
    def __init__(self, suffixes, error_log):
        self.suffixes = suffixes
        try:
            self.keys = [str_to_uint64(s) for s in suffixes]
            self.mphf = bbhash.PyMPHF(self.keys, len(self.keys), 1.0, 1)
        except Exception as e:
            error_log.append(f"GenericMPHFBucket error: {e}")
            self.mphf = None

    def lookup(self, suffix):
        if not self.mphf:
            return None
        key = str_to_uint64(suffix)
        idx = self.mphf.lookup(key)
        if idx != -1:
            return self.suffixes[idx]
        return None

class Algorithm3Bucket:
    """Each bucket uses Algorithm 3 variant (still bbhash) for suffixes."""
    def __init__(self, suffixes, error_log):
        self.suffixes = suffixes
        try:
            self.keys = [str_to_uint64(s) for s in suffixes]
            self.mphf = bbhash.PyMPHF(self.keys, len(self.keys), 1.0, 1)  # Algorithm 3
        except Exception as e:
            error_log.append(f"Algorithm3Bucket error: {e}")
            self.mphf = None

    def lookup(self, suffix):
        if not self.mphf:
            return None
        key = str_to_uint64(suffix)
        idx = self.mphf.lookup(key)
        if idx != -1:
            return self.suffixes[idx]
        return None

# ---------------- Prefix Table ----------------

class PrefixTable:
    """Prefix -> Bucket mapping"""
    def __init__(self, prefix_map, bucket_class, error_log):
        self.buckets = {}
        start_build = time.time()
        for prefix, suffixes in prefix_map.items():
            self.buckets[prefix] = bucket_class(suffixes, error_log)
        self.build_time = time.time() - start_build

    def lookup(self, word, prefix_len=3):
        prefix = word[:prefix_len]
        bucket = self.buckets.get(prefix)
        if bucket:
            suffix = word[prefix_len:]
            return bucket.lookup(suffix)
        return None

# ---------------- Main ----------------

if __name__ == "__main__":
    error_log = []

    # Load JSON
    json_path = input("Enter path to JSON file (prefix -> suffixes): ")
    with open(json_path, "r") as f:
        prefix_map = json.load(f)

    # Flatten word list for testing
    word_list = [prefix + suffix for prefix, suffixes in prefix_map.items() for suffix in suffixes]

    print(f"Loaded {len(prefix_map)} prefixes from {json_path}")
    print(f"Total words: {len(word_list)}")

    # Start tracking memory
    tracemalloc.start()

    # --- Case 1: Generic MPHF at Suffix Level ---
    generic_table = PrefixTable(prefix_map, GenericMPHFBucket, error_log)
    start = time.time()
    verified = sum(1 for word in word_list if generic_table.lookup(word) is not None)
    generic_lookup_time = time.time() - start
    mem_current, mem_peak = tracemalloc.get_traced_memory()
    print("\n=== Generic MPHF at Suffix Level ===")
    print(f"Build time: {generic_table.build_time:.3f} sec")
    print(f"Total lookup time: {generic_lookup_time:.3f} sec")
    print(f"Verified: {verified}/{len(word_list)}")
    print(f"Memory usage: {mem_peak/1024/1024:.2f} MB (peak)")

    # --- Case 2: Algorithm 3 at Suffix Level ---
    algo3_table = PrefixTable(prefix_map, Algorithm3Bucket, error_log)
    start = time.time()
    verified = sum(1 for word in word_list if algo3_table.lookup(word) is not None)
    algo3_lookup_time = time.time() - start
    mem_current2, mem_peak2 = tracemalloc.get_traced_memory()
    print("\n=== Algorithm 3 at Suffix Level ===")
    print(f"Build time: {algo3_table.build_time:.3f} sec")
    print(f"Total lookup time: {algo3_lookup_time:.3f} sec")
    print(f"Verified: {verified}/{len(word_list)}")
    print(f"Memory usage: {mem_peak2/1024/1024:.2f} MB (peak)")

    # --- Case 3: Algorithm 3 at Prefix Level + MPHF Suffix ---
    class Algo3PrefixTable:
        """Algorithm 3 at prefix level"""
        def __init__(self, prefix_map, suffix_bucket_class, error_log):
            self.prefixes = list(prefix_map.keys())
            self.prefix_keys = [str_to_uint64(p) for p in self.prefixes]
            try:
                self.prefix_mphf = bbhash.PyMPHF(self.prefix_keys, len(self.prefix_keys), 1.0, 1)
            except Exception as e:
                error_log.append(f"Algo3PrefixTable error: {e}")
                self.prefix_mphf = None
            self.buckets = {}
            for p in self.prefixes:
                self.buckets[p] = suffix_bucket_class(prefix_map[p], error_log)

        def lookup(self, word, prefix_len=3):
            prefix = word[:prefix_len]
            if not self.prefix_mphf:
                return None
            prefix_key = str_to_uint64(prefix)
            idx = self.prefix_mphf.lookup(prefix_key)
            if idx == -1:
                return None
            suffix = word[prefix_len:]
            return self.buckets[prefix].lookup(suffix)

    algo3_prefix_table = Algo3PrefixTable(prefix_map, GenericMPHFBucket, error_log)
    start = time.time()
    verified = sum(1 for word in word_list if algo3_prefix_table.lookup(word) is not None)
    algo3_prefix_lookup_time = time.time() - start
    mem_current3, mem_peak3 = tracemalloc.get_traced_memory()
    print("\n=== Algorithm 3 at Prefix Level + MPHF Suffix ===")
    print(f"Total lookup time: {algo3_prefix_lookup_time:.3f} sec")
    print(f"Verified: {verified}/{len(word_list)}")
    print(f"Memory usage: {mem_peak3/1024/1024:.2f} MB (peak)")

    # --- Comparison ---
    print("\n=== Total Lookup Time Comparison ===")
    print(f"Generic MPHF Suffix: {generic_lookup_time:.3f} sec")
    print(f"Algorithm 3 Suffix: {algo3_lookup_time:.3f} sec")
    print(f"Algorithm 3 Prefix + MPHF Suffix: {algo3_prefix_lookup_time:.3f} sec")

    print("\n=== Memory Comparison (MB) ===")
    print(f"Generic MPHF Suffix: {mem_peak/1024/1024:.2f}")
    print(f"Algorithm 3 Suffix: {mem_peak2/1024/1024:.2f}")
    print(f"Algorithm 3 Prefix + MPHF Suffix: {mem_peak3/1024/1024:.2f}")

    # --- Log Errors ---
    if error_log:
        print("\n=== Errors Encountered During Execution ===")
        for e in error_log:
            print("-", e)

    tracemalloc.stop()
