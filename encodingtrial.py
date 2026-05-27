import json
import time
import bbhash
import tracemalloc

# ---------- Encoding Methods ----------

def utf8_to_uint64(s):
    """Original encoding: UTF-8 string → 64-bit integer"""
    return int.from_bytes(s.encode("utf-8"), "little") & 0xFFFFFFFFFFFFFFFF


def base26_to_int(s):
    """Smaller encoding: base-26 for lowercase wordlists"""
    x = 0
    for ch in s:
        x = x * 26 + (ord(ch) - ord('a'))
    return x


# ---------- Generic MPHF Bucket ----------

class GenericMPHFBucket:
    """
    One bucket corresponding to a prefix.
    Uses a Minimal Perfect Hash Function (MPHF) on suffixes.
    """
    def __init__(self, suffixes, encode_fn):
        self.suffixes = suffixes
        self.encode_fn = encode_fn

        # Convert suffix strings to integers
        self.keys = [encode_fn(s) for s in suffixes]

        # Build MPHF
        self.mphf = bbhash.PyMPHF(
            self.keys,
            len(self.keys),
            1.0,
            1
        )

    def lookup(self, suffix):
        key = self.encode_fn(suffix)
        idx = self.mphf.lookup(key)
        if idx == -1:
            return None
        return self.suffixes[idx]


# ---------- Prefix Table ----------

class PrefixTable:
    """
    Maps prefixes to suffix buckets.
    """
    def __init__(self, prefix_map, encode_fn, prefix_len=3):
        self.prefix_len = prefix_len
        self.buckets = {}

        for prefix, suffixes in prefix_map.items():
            self.buckets[prefix] = GenericMPHFBucket(suffixes, encode_fn)

    def lookup(self, word):
        prefix = word[:self.prefix_len]
        suffix = word[self.prefix_len:]

        bucket = self.buckets.get(prefix)
        if not bucket:
            return None

        return bucket.lookup(suffix)


# ---------- Benchmark Helper ----------

def benchmark(prefix_map, word_list, encode_fn, label):
    print(f"\n=== {label} ===")

    tracemalloc.start()

    start_build = time.time()
    table = PrefixTable(prefix_map, encode_fn)
    build_time = time.time() - start_build

    start_lookup = time.time()
    verified = sum(1 for w in word_list if table.lookup(w) is not None)
    lookup_time = time.time() - start_lookup

    _, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"Build time      : {build_time:.3f} sec")
    print(f"Lookup time     : {lookup_time:.3f} sec")
    print(f"Verified        : {verified}/{len(word_list)}")
    print(f"Peak memory     : {peak_mem / 1024 / 1024:.2f} MB")


# ---------- Main ----------

if __name__ == "__main__":
    path = input("Enter path to JSON file (prefix → suffixes): ")
    with open(path, "r") as f:
        prefix_map = json.load(f)

    # Flatten full word list
    word_list = [
        prefix + suffix
        for prefix, suffixes in prefix_map.items()
        for suffix in suffixes
    ]

    print(f"\nPrefixes   : {len(prefix_map)}")
    print(f"Total words: {len(word_list)}")

    # --- Case 1: UTF-8 → 64-bit ---
    benchmark(
        prefix_map,
        word_list,
        utf8_to_uint64,
        "UTF-8 → 64-bit Integer Encoding"
    )

    # --- Case 2: Base-26 Small Keys ---
    benchmark(
        prefix_map,
        word_list,
        base26_to_int,
        "Base-26 Small Integer Encoding"
    )
