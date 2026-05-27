import subprocess
import os
import sys

json_path = input("Enter path to JSON wordlist: ").strip()

BASE = os.path.dirname(__file__)
HYBRID = os.path.join(BASE, "hybrid_only.py")
TRIE   = os.path.join(BASE, "trie_only.py")

hybrid = subprocess.Popen(
    [sys.executable, HYBRID, json_path],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
    bufsize=1
)

trie = subprocess.Popen(
    [sys.executable, TRIE, json_path],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
    bufsize=1
)

# wait for READY
print(hybrid.stdout.readline().strip())
print(trie.stdout.readline().strip())

print("--------------------------------------------------")
print("Hybrid MPHF (≤8) vs Trie")
print("Type 'exit' to stop")
print("--------------------------------------------------")


def read_tagged(proc, tag):
    while True:
        line = proc.stdout.readline()
        if not line:
            return None
        line = line.strip()
        if line.startswith(tag):
            return line


while True:
    try:
        word = input(">> ").strip()
        if word == "exit":
            break

        hybrid.stdin.write(word + "\n")
        hybrid.stdin.flush()

        trie.stdin.write(word + "\n")
        trie.stdin.flush()

        h = read_tagged(hybrid, "HYBRID")
        t = read_tagged(trie, "TRIE")

        if h is None or t is None:
            print("ERROR: subprocess terminated")
            break

        _, hf, ht = h.split()
        _, tf, tt = t.split()

        print("\nResult:")
        print(f"  Hybrid MPHF : {'FOUND' if hf=='1' else 'NOT FOUND'} | {ht} µs")
        print(f"  Trie       : {'FOUND' if tf=='1' else 'NOT FOUND'} | {tt} µs")

    except KeyboardInterrupt:
        break

hybrid.stdin.write("exit\n")
trie.stdin.write("exit\n")
hybrid.stdin.flush()
trie.stdin.flush()

hybrid.terminate()
trie.terminate()

