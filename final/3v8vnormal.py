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
    """Get current RSS (Resident Set Size) memory in MB"""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)

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

# ---------------- Prefix Table ----------------

class PrefixTable:
    def __init__(self, prefix_map, bucket_cls, threshold=None, name="Table"):
        self.name = name
        
        # Track build time
        build_start = time.time()
        
        # Track memory before build
        rss_before = get_rss_mb()
        tracemalloc_before = tracemalloc.get_traced_memory()[0]
        
        # Build the table
        self.buckets = {
            p: (bucket_cls(s) if threshold is None else bucket_cls(s, threshold))
            for p, s in prefix_map.items()
        }
        
        # Calculate metrics
        self.build_time = time.time() - build_start
        self.rss_memory = get_rss_mb() - rss_before
        tracemalloc_after = tracemalloc.get_traced_memory()[0]
        self.python_memory = (tracemalloc_after - tracemalloc_before) / (1024 * 1024)
        
        # Calculate bucket statistics
        self.total_buckets = len(self.buckets)
        if threshold is not None:
            self.tuple_buckets = sum(1 for b in self.buckets.values() if b.mode == "tuple")
            self.mphf_buckets = self.total_buckets - self.tuple_buckets
        else:
            self.tuple_buckets = 0
            self.mphf_buckets = self.total_buckets

    def lookup(self, word):
        if len(word) < 3:
            return None
        prefix = word[:3]
        suffix = word[3:]
        bucket = self.buckets.get(prefix)
        if not bucket:
            return None
        return bucket.lookup(suffix)
    
    def print_stats(self):
        """Print detailed statistics about this table"""
        print(f"\n{'='*60}")
        print(f"  {self.name}")
        print(f"{'='*60}")
        print(f"  Build Time        : {self.build_time:.3f} seconds")
        print(f"  RSS Memory        : {self.rss_memory:.2f} MB")
        print(f"  Python Memory     : {self.python_memory:.2f} MB")
        print(f"  Total Buckets     : {self.total_buckets:,}")
        print(f"  Tuple Buckets     : {self.tuple_buckets:,}")
        print(f"  MPHF Buckets      : {self.mphf_buckets:,}")
        if self.total_buckets > 0:
            print(f"  Tuple Percentage  : {(self.tuple_buckets/self.total_buckets)*100:.1f}%")
        print(f"{'='*60}")

# ---------------- Main ----------------

if __name__ == "__main__":
    json_path = input("Enter path to JSON wordlist: ").strip()

    with open(json_path, "r") as f:
        prefix_map = json.load(f)

    print(f"\n📊 Dataset: {len(prefix_map):,} prefixes loaded")
    
    # Start memory tracking
    tracemalloc.start()
    
    print("\n🔨 Building data structures...")
    print("  (This may take a moment...)\n")
    
    # Build all three tables
    normal = PrefixTable(prefix_map, MPHFBucket, name="Normal MPHF (All Buckets)")
    hybrid3 = PrefixTable(prefix_map, SelectiveHybridBucket, 3, name="Hybrid Threshold ≤3")
    hybrid8 = PrefixTable(prefix_map, SelectiveHybridBucket, 8, name="Hybrid Threshold ≤8")
    
    # Print statistics for each
    normal.print_stats()
    hybrid3.print_stats()
    hybrid8.print_stats()
    
    # Comparison summary
    print(f"\n{'🔍 COMPARATIVE ANALYSIS':^60}")
    print(f"{'='*60}")
    print(f"\n{'Metric':<25} {'Normal':<12} {'Hybrid ≤3':<12} {'Hybrid ≤8':<12}")
    print(f"{'-'*60}")
    print(f"{'Build Time (sec)':<25} {normal.build_time:<12.3f} {hybrid3.build_time:<12.3f} {hybrid8.build_time:<12.3f}")
    print(f"{'RSS Memory (MB)':<25} {normal.rss_memory:<12.2f} {hybrid3.rss_memory:<12.2f} {hybrid8.rss_memory:<12.2f}")
    print(f"{'Python Memory (MB)':<25} {normal.python_memory:<12.2f} {hybrid3.python_memory:<12.2f} {hybrid8.python_memory:<12.2f}")
    print(f"{'MPHF Buckets':<25} {normal.mphf_buckets:<12,} {hybrid3.mphf_buckets:<12,} {hybrid8.mphf_buckets:<12,}")
    print(f"{'Tuple Buckets':<25} {normal.tuple_buckets:<12,} {hybrid3.tuple_buckets:<12,} {hybrid8.tuple_buckets:<12,}")
    print(f"{'-'*60}")
    
    # Calculate improvements
    print(f"\n{'💡 IMPROVEMENTS vs Normal MPHF':^60}")
    print(f"{'-'*60}")
    
    build_time_saved_3 = ((normal.build_time - hybrid3.build_time) / normal.build_time) * 100
    build_time_saved_8 = ((normal.build_time - hybrid8.build_time) / normal.build_time) * 100
    
    rss_saved_3 = ((normal.rss_memory - hybrid3.rss_memory) / normal.rss_memory) * 100
    rss_saved_8 = ((normal.rss_memory - hybrid8.rss_memory) / normal.rss_memory) * 100
    
    py_saved_3 = ((normal.python_memory - hybrid3.python_memory) / normal.python_memory) * 100
    py_saved_8 = ((normal.python_memory - hybrid8.python_memory) / normal.python_memory) * 100
    
    print(f"  Hybrid ≤3:")
    print(f"    Build Time Reduction  : {build_time_saved_3:+.1f}%")
    print(f"    RSS Memory Reduction  : {rss_saved_3:+.1f}%")
    print(f"    Python Memory Reduction: {py_saved_3:+.1f}%")
    print(f"\n  Hybrid ≤8:")
    print(f"    Build Time Reduction  : {build_time_saved_8:+.1f}%")
    print(f"    RSS Memory Reduction  : {rss_saved_8:+.1f}%")
    print(f"    Python Memory Reduction: {py_saved_8:+.1f}%")
    print(f"{'-'*60}")
    
    print("\n\n--------------------------------------------------")
    print("🔎 Enter words to look up (type 'exit' to stop)")
    print("--------------------------------------------------")

    while True:
        word = input(">> ").strip()
        if word.lower() == "exit":
            break

        def test(name, table):
            t0 = time.perf_counter()
            found = table.lookup(word) is not None
            t = (time.perf_counter() - t0) * 1e6
            print(f"  {name:<12}: {'FOUND' if found else 'NOT FOUND'} | {t:6.2f} µs")

        print(f"\nWord: {word}")
        test("Normal MPHF", normal)
        test("Hybrid ≤3", hybrid3)
        test("Hybrid ≤8", hybrid8)
    
    tracemalloc.stop()
    print("\n✨ Thank you for using the word lookup system!")