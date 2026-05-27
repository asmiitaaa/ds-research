import subprocess
import os
import sys

json_path = input("Enter path to JSON wordlist: ").strip()

BASE = os.path.dirname(__file__)
HYBRID = os.path.join(BASE, "hybrid_only.py")
DAWG   = os.path.join(BASE, "dawg_only.py")

hybrid = subprocess.Popen(
    ["python", HYBRID, json_path],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
    bufsize=1
)

dawg = subprocess.Popen(
    ["python", DAWG, json_path],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
    bufsize=1
)

# ---------- WAIT FOR READY SIGNALS ----------
print(hybrid.stdout.readline().strip())  # READY HYBRID
print(dawg.stdout.readline().strip())    # READY DAWG

print("--------------------------------------------------")
print("Hybrid MPHF (≤8) vs DAWG (DAFSA)")
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

# ---------- INTERACTIVE LOOP ----------
while True:
    try:
        word = input(">> ").strip()
        if word == "exit":
            break

        # send word
        hybrid.stdin.write(word + "\n")
        hybrid.stdin.flush()

        dawg.stdin.write(word + "\n")
        dawg.stdin.flush()

        # read responses
        h = read_tagged(hybrid, "HYBRID")
        d = read_tagged(dawg, "DAWG")

        if h is None or d is None:
            print("ERROR: subprocess died")
            break

        _, hf, ht = h.split()
        _, df, dt = d.split()

        print("\nResult:")
        print(f"  Hybrid MPHF : {'FOUND' if hf=='1' else 'NOT FOUND'} | {ht} µs")
        print(f"  DAWG       : {'FOUND' if df=='1' else 'NOT FOUND'} | {dt} µs")

    except KeyboardInterrupt:
        break

# ---------- CLEAN EXIT ----------
hybrid.stdin.write("exit\n")
hybrid.stdin.flush()
dawg.stdin.write("exit\n")
dawg.stdin.flush()

hybrid.terminate()
dawg.terminate()
