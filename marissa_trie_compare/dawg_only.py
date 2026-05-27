import sys
import json
import time
import marisa_trie

if __name__ == "__main__":
    json_path = sys.argv[1]

    with open(json_path, "r") as f:
        prefix_map = json.load(f)

    words = []
    for p, suffixes in prefix_map.items():
        for s in suffixes:
            words.append(p + s)

    t0 = time.time()
    trie = marisa_trie.Trie(words)
    build_time = time.time() - t0

    # 🔴 REQUIRED READY LINE
    print(f"READY DAWG {build_time:.3f}", flush=True)

    while True:
        line = sys.stdin.readline()
        if not line:
            break

        word = line.strip()
        if word == "exit":
            break

        t0 = time.perf_counter()
        found = word in trie
        dt = (time.perf_counter() - t0) * 1e6

        print(f"DAWG {1 if found else 0} {dt:.2f}", flush=True)
