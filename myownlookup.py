import json
import time
import bbhash

# ---------- Utility ----------

def str_to_uint64(s):
    """Convert a string into a consistent 64-bit integer for bbhash."""
    return int.from_bytes(s.encode("utf-8"), "little") & 0xFFFFFFFFFFFFFFFF


# ---------- Suffix Bucket ----------

class GenericMPHFBucket:
    """
    One bucket corresponding to a prefix.
    Uses a Minimal Perfect Hash Function (MPHF) on suffixes.
    """
    def __init__(self, suffixes):
        self.suffixes = suffixes
        self.keys = [str_to_uint64(s) for s in suffixes]

        # Build MPHF (one-time)
        self.mphf = bbhash.PyMPHF(
            self.keys,
            len(self.keys),
            1.0,
            1
        )

    def lookup(self, suffix):
        key = str_to_uint64(suffix)
        idx = self.mphf.lookup(key)
        if idx == -1:
            return None
        return self.suffixes[idx]


# ---------- Prefix Table ----------

class PrefixTable:
    """
    Prefix → MPHF bucket mapping
    """
    def __init__(self, prefix_map, prefix_len):
        self.prefix_len = prefix_len
        self.buckets = {}

        # Build phase
        for prefix, suffixes in prefix_map.items():
            self.buckets[prefix] = GenericMPHFBucket(suffixes)

    def lookup(self, word):
        prefix = word[:self.prefix_len]
        suffix = word[self.prefix_len:]

        bucket = self.buckets.get(prefix)
        if not bucket:
            return None

        return bucket.lookup(suffix)


# ---------- Main ----------

if __name__ == "__main__":
    # ---- Input wordlist ----
    json_path = input("Enter path to JSON wordlist: ")
    with open(json_path, "r") as f:
        prefix_map = json.load(f)

    prefix_len = int(input("Enter prefix length: "))

    print("\nBuilding MPHF structure...")
    build_start = time.time()
    table = PrefixTable(prefix_map, prefix_len)
    build_time = time.time() - build_start

    print(f"Build completed in {build_time:.3f} seconds")
    print("--------------------------------------------------")

    # ---- Interactive lookup phase ----
    print("Enter words to look up (type 'exit' to stop):")

    while True:
        word = input(">> ").strip()
        if word.lower() == "exit":
            break

        lookup_start = time.perf_counter()
        result = table.lookup(word)
        lookup_time = (time.perf_counter() - lookup_start) * 1e6  # microseconds

        if result is not None:
            print(f"FOUND | Lookup time: {lookup_time:.2f} µs")
        else:
            print(f"NOT FOUND | Lookup time: {lookup_time:.2f} µs")
