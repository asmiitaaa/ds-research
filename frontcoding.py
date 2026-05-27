import json
import time
import bbhash
import tracemalloc

# ---------------- Utilities ----------------

def str_to_uint64(s):
    """Convert a string to a consistent 64-bit integer for bbhash."""
    return int.from_bytes(s.encode("utf-8"), "little") & 0xFFFFFFFFFFFFFFFF

# ---------------- Front-Coding Utilities ----------------

def front_code_suffixes(suffixes):
    """
    Encode suffixes using simple front-coding:
    - Store common prefix length + remaining string for each suffix.
    Returns (prefix, encoded_suffixes)
    """
    if not suffixes:
        return "", []

    # Find common prefix
    common_prefix = suffixes[0]
    for s in suffixes[1:]:
        i = 0
        while i < len(common_prefix) and i < len(s) and common_prefix[i] == s[i]:
            i += 1
        common_prefix = common_prefix[:i]

    # Encode each suffix as remaining part after common prefix
    encoded = [s[len(common_prefix):] for s in suffixes]
    return common_prefix, encoded

def reconstruct_suffix(common_prefix, encoded_suffix):
    """Reconstruct original suffix from front-coded form"""
    return common_prefix + encoded_suffix

# ---------------- Bucket Classes ----------------

class GenericMPHFBucket:
    """Each bucket uses a generic MPHF for suffixes, optional front-coding."""
    def __init__(self, suffixes, error_log, front_coding=False):
        self.front_coding = front_coding
        self.error_log = error_log

        try:
            if front_coding:
                # Apply front coding
                self.common_prefix, self.encoded_suffixes = front_code_suffixes(suffixes)
                keys = [str_to_uint64(suffix) for suffix in self.encoded_suffixes]
                self.suffixes = self.encoded_suffixes
            else:
                self.suffixes = suffixes
                keys = [str_to_uint64(s) for s in suffixes]

            self.mphf = bbhash.PyMPHF(keys, len(keys), 1.0, 1)
        except Exception as e:
            error_log.append(f"GenericMPHFBucket error: {e}")
            self.mphf = None

    def lookup(self, suffix):
        if not self.mphf:
            return None
        if self.front_coding:
            # Only store remaining part, need to remove common prefix
            if not suffix.startswith(self.common_prefix):
                return None
            encoded_suffix = suffix[len(self.common_prefix):]
            key = str_to_uint64(encoded_suffix)
        else:
            key = str_to_uint64(suffix)
        idx = self.mphf.lookup(key)
        if idx != -1:
            if self.front_coding:
                return reconstruct_suffix(self.common_prefix, self.suffixes[idx])
            else:
                return self.suffixes[idx]
        return None

# ---------------- Prefix Table ----------------

class PrefixTable:
    """Prefix -> Bucket mapping"""
    def __init__(self, prefix_map, bucket_class, error_log, front_coding=False):
        self.buckets = {}
        start_build = time.time()
        for prefix, suffixes in prefix_map.items():
            self.buckets[prefix] = bucket_class(suffixes, error_log, front_coding)
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

    tracemalloc.start()

    # --- Case 1: DS1 without front-coding ---
    table_no_fc = PrefixTable(prefix_map, GenericMPHFBucket, error_log, front_coding=False)
    start = time.time()
    verified = sum(1 for word in word_list if table_no_fc.lookup(word) is not None)
    lookup_time_no_fc = time.time() - start
    mem_current, mem_peak = tracemalloc.get_traced_memory()
    print("\n=== DS1 without Front-Coding ===")
    print(f"Total lookup time: {lookup_time_no_fc:.3f} sec")
    print(f"Verified: {verified}/{len(word_list)}")
    print(f"Memory usage: {mem_peak/1024/1024:.2f} MB (peak)")

    # --- Case 2: DS1 with front-coding ---
    table_fc = PrefixTable(prefix_map, GenericMPHFBucket, error_log, front_coding=True)
    start = time.time()
    verified = sum(1 for word in word_list if table_fc.lookup(word) is not None)
    lookup_time_fc = time.time() - start
    mem_current2, mem_peak2 = tracemalloc.get_traced_memory()
    print("\n=== DS1 with Front-Coding ===")
    print(f"Total lookup time: {lookup_time_fc:.3f} sec")
    print(f"Verified: {verified}/{len(word_list)}")
    print(f"Memory usage: {mem_peak2/1024/1024:.2f} MB (peak)")

    # --- Comparison ---
    print("\n=== Lookup Time Comparison ===")
    print(f"Without Front-Coding: {lookup_time_no_fc:.3f} sec")
    print(f"With Front-Coding:    {lookup_time_fc:.3f} sec")

    print("\n=== Memory Comparison (MB) ===")
    print(f"Without Front-Coding: {mem_peak/1024/1024:.2f}")
    print(f"With Front-Coding:    {mem_peak2/1024/1024:.2f}")

    if error_log:
        print("\n=== Errors Encountered ===")
        for e in error_log:
            print("-", e)

    tracemalloc.stop()
