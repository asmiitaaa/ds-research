import json
import time
import bbhash

# ---------- Suffix Bucket Classes ----------

class GenericMPHFBucket:
    """Each bucket uses a generic MPHF for suffixes"""
    def __init__(self, suffixes):
        self.suffixes = suffixes
        # Convert suffixes to 64-bit ints for bbhash
        self.keys = [hash(s) & 0xFFFFFFFFFFFFFFFF for s in suffixes]
        self.mphf = bbhash.PyMPHF(self.keys, len(self.keys), 1.0, 1)

    def lookup(self, suffix):
        key = hash(suffix) & 0xFFFFFFFFFFFFFFFF
        idx = self.mphf.lookup(key)
        if idx != -1:
            return self.suffixes[idx]  # Return actual suffix
        return None

class Algorithm3Bucket:
    """Each bucket uses Algorithm 3 for suffixes"""
    def __init__(self, suffixes):
        self.suffixes = suffixes
        # Convert suffixes to 64-bit ints for bbhash
        self.keys = [hash(s) & 0xFFFFFFFFFFFFFFFF for s in suffixes]
        self.mphf = bbhash.PyMPHF(self.keys, len(self.keys), 1.0, 1)  # Algorithm 3 variant

    def lookup(self, suffix):
        key = hash(suffix) & 0xFFFFFFFFFFFFFFFF
        idx = self.mphf.lookup(key)
        if idx != -1:
            return self.suffixes[idx]
        return None

# ---------- Prefix Table ----------

class PrefixTable:
    """Prefix -> Bucket mapping"""
    def __init__(self, prefix_map, bucket_class):
        self.buckets = {}
        start_build = time.time()
        for prefix, suffixes in prefix_map.items():
            self.buckets[prefix] = bucket_class(suffixes)
        self.build_time = time.time() - start_build

    def lookup(self, word):
        prefix = word[:-1]  # or adjust based on your prefix definition
        suffix = word[-1:]  # adjust as needed
        bucket = self.buckets.get(prefix)
        if bucket:
            return bucket.lookup(suffix)
        return None

# ---------- Main ----------

if __name__ == "__main__":
    json_path = input("Enter path to JSON file (prefix -> suffixes): ")
    with open(json_path, "r") as f:
        prefix_map = json.load(f)

    # Flatten word list for lookup testing
    word_list = [prefix + suffix for prefix, suffixes in prefix_map.items() for suffix in suffixes]

    print(f"Loaded {len(prefix_map)} prefixes from {json_path}")
    print(f"Total words: {len(word_list)}")

    # --- Data structure 1: Generic MPHF ---
    generic_table = PrefixTable(prefix_map, GenericMPHFBucket)
    start = time.time()
    verified = sum(1 for word in word_list if generic_table.lookup(word) is not None)
    generic_lookup_time = time.time() - start
    print("\n=== Generic MPHF at Suffix Level ===")
    print(f"Build time: {generic_table.build_time:.3f} sec")
    print(f"Total lookup time: {generic_lookup_time:.3f} sec")
    print(f"Verified: {verified}/{len(word_list)}")

    # --- Data structure 2: Algorithm 3 ---
    algo3_table = PrefixTable(prefix_map, Algorithm3Bucket)
    start = time.time()
    verified = sum(1 for word in word_list if algo3_table.lookup(word) is not None)
    algo3_lookup_time = time.time() - start
    print("\n=== Algorithm 3 at Suffix Level ===")
    print(f"Build time: {algo3_table.build_time:.3f} sec")
    print(f"Total lookup time: {algo3_lookup_time:.3f} sec")
    print(f"Verified: {verified}/{len(word_list)}")

    # --- Comparison ---
    print("\n=== Total Lookup Time Comparison ===")
    print(f"Generic MPHF: {generic_lookup_time:.3f} sec")
    print(f"Algorithm 3: {algo3_lookup_time:.3f} sec")
