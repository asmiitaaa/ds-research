import json
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

        # Convert suffix strings to integers
        self.keys = [str_to_uint64(s) for s in suffixes]

        # Build MPHF for suffixes
        self.mphf = bbhash.PyMPHF(
            self.keys,
            len(self.keys),
            1.0,
            1
        )

    def lookup(self, suffix):
        """Look up a suffix using MPHF."""
        key = str_to_uint64(suffix)
        idx = self.mphf.lookup(key)

        if idx == -1:
            return None

        return self.suffixes[idx]


# ---------- Prefix Table ----------

class PrefixTable:
    """
    Maps prefixes to suffix buckets.
    """
    def __init__(self, prefix_map, prefix_len=3):
        self.prefix_len = prefix_len
        self.buckets = {}

        for prefix, suffixes in prefix_map.items():
            self.buckets[prefix] = GenericMPHFBucket(suffixes)

    def lookup(self, word):
        """Look up a full word."""
        prefix = word[:self.prefix_len]
        suffix = word[self.prefix_len:]

        bucket = self.buckets.get(prefix)
        if not bucket:
            return None

        return bucket.lookup(suffix)


# ---------- Main ----------

if __name__ == "__main__":
    # Load JSON file: { "pre": ["fix", "view"], ... }
    path = input("Enter path to JSON file: ")
    with open(path, "r") as f:
        prefix_map = json.load(f)

    table = PrefixTable(prefix_map)

    # Test lookup
    while True:
        word = input("Enter word to search (or 'exit'): ")
        if word == "exit":
            break

        result = table.lookup(word)
        if result is not None:
            print("Word FOUND")
        else:
            print("Word NOT FOUND")
