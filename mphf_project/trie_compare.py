import json
import time
import bbhash
import tracemalloc
import psutil
import os

# ---------------- Utilities ----------------

def str_to_uint64(s):
    return int.from_bytes(s.encode("utf-8"), "little") & 0xFFFFFFFFFFFFFFFF

def get_rss_mb():
    """Return total process memory (RSS) in MB."""
    return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)

# ---------------- Hybrid Buckets (UNCHANGED) ----------------

class SelectiveHybridBucket:
    """Tuple for size ≤3, MPHF otherwise"""
    def __init__(self, suffixes, threshold=3):
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
        else:
            idx = self.mphf.lookup(str_to_uint64(suffix))
            if idx == -1:
                return None
            return self.suffixes[idx]

# ---------------- Hybrid Prefix Table (UNCHANGED) ----------------

class HybridPrefixTable:
    def __init__(self, prefix_map, threshold=3):
        self.buckets = {}
        start = time.time()
        for p, s in prefix_map.items():
            self.buckets[p] = SelectiveHybridBucket(s, threshold)
        self.build_time = time.time() - start

    def lookup(self, word):
        prefix = word[:3]
        suffix = word[3:]
        bucket = self.buckets.get(prefix)
        if not bucket:
            return None
        return bucket.lookup(suffix)

# ---------------- Trie Implementation ----------------

class TrieNode:
    __slots__ = ("children", "end")

    def __init__(self):
        self.children = {}
        self.end = False

class Trie:
    def __init__(self):
        self.root = TrieNode()
        self.build_time = 0.0

    def insert(self, word):
        node = self.root
        for ch in word:
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
        node.end = True

    def build(self, words):
        start = time.time()
        for w in words:
            self.insert(w)
        self.build_time = time.time() - start

    def lookup(self, word):
        node = self.root
        for ch in word:
            if ch not in node.children:
                return None
            node = node.children[ch]
        return word if node.end else None

# ---------------- Main ----------------

if __name__ == "__main__":
    json_path = input("Enter path to JSON wordlist: ")

    with open(json_path, "r") as f:
        prefix_map = json.load(f)

    # Build full word list for Trie
    words = []
    for p, suffixes in prefix_map.items():
        for s in suffixes:
            words.append(p + s)

    print(f"\nPrefixes   : {len(prefix_map)}")
    print(f"Total words: {len(words)}")

    # -------- Build phase --------
    tracemalloc.start()

    # Hybrid
    rss_before = get_rss_mb()
    print("\nBuilding SELECTIVE HYBRID (≤3 tuple, else MPHF)...")
    hybrid_table = HybridPrefixTable(prefix_map, threshold=3)
    rss_after = get_rss_mb()
    _, peak_py_hybrid = tracemalloc.get_traced_memory()
    hybrid_rss = rss_after - rss_before

    tracemalloc.reset_peak()

    # Trie
    rss_before = get_rss_mb()
    print("Building TRIE...")
    trie = Trie()
    trie.build(words)
    rss_after = get_rss_mb()
    _, peak_py_trie = tracemalloc.get_traced_memory()
    trie_rss = rss_after - rss_before

    tracemalloc.stop()

    # -------- Summary --------
    print("\n=== Build Summary ===")
    print(f"Hybrid build time : {hybrid_table.build_time:.3f} sec")
    print(f"Trie build time   : {trie.build_time:.3f} sec")
    print(f"Hybrid peak Python memory : {peak_py_hybrid / 1024 / 1024:.2f} MB")
    print(f"Trie peak Python memory   : {peak_py_trie / 1024 / 1024:.2f} MB")
    print(f"Hybrid RSS increase       : {hybrid_rss:.2f} MB")
    print(f"Trie RSS increase         : {trie_rss:.2f} MB")

    # -------- Interactive lookup --------
    print("\n--------------------------------------------------")
    print("Enter words to look up (type 'exit' to stop)")
    print("--------------------------------------------------")

    while True:
        word = input(">> ").strip()
        if word.lower() == "exit":
            break

        # Hybrid lookup
        t0 = time.perf_counter()
        r1 = hybrid_table.lookup(word)
        t1 = (time.perf_counter() - t0) * 1e6

        # Trie lookup
        t0 = time.perf_counter()
        r2 = trie.lookup(word)
        t2 = (time.perf_counter() - t0) * 1e6

        print("\nResult:")
        print(f"  Hybrid MPHF : {'FOUND' if r1 else 'NOT FOUND'} | {t1:.2f} µs")
        print(f"  Trie       : {'FOUND' if r2 else 'NOT FOUND'} | {t2:.2f} µs")
