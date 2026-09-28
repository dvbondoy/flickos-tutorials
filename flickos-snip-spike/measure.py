#!/usr/bin/env python3
"""measure.py: CPU and memory of one process until it exits.

    ./measure.py PID              a line every 5 s, a summary at the end
    ./measure.py PID --every 1

CPU is a percentage of one CPU (200% = two CPUs busy). Memory is PSS:
shared libraries count only by this process's share, so it is the fair
number (RSS counts them in full). Both come from /proc, nothing else.
"""
import os
import sys
import time

TICK = os.sysconf("SC_CLK_TCK")


def cpu_seconds(pid):
    with open(f"/proc/{pid}/stat") as f:
        # The name is in parentheses and may contain spaces: split after it.
        fields = f.read().rsplit(")", 1)[1].split()
    return (int(fields[11]) + int(fields[12])) / TICK  # utime + stime


def pss_mb(pid):
    with open(f"/proc/{pid}/smaps_rollup") as f:
        for line in f:
            if line.startswith("Pss:"):
                return int(line.split()[1]) / 1024
    return 0.0


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    pid = int(sys.argv[1])
    every = float(sys.argv[3]) if sys.argv[2:3] == ["--every"] else 5.0
    samples = []
    start = last_t = time.monotonic()
    try:
        last_cpu = cpu_seconds(pid)
        while True:
            time.sleep(every)
            now, cpu, pss = time.monotonic(), cpu_seconds(pid), pss_mb(pid)
            percent = 100 * (cpu - last_cpu) / (now - last_t)
            samples.append((percent, pss))
            print(f"[measure] {now - start:6.0f} s  CPU {percent:5.1f} %  PSS {pss:6.1f} MB",
                  flush=True)
            last_t, last_cpu = now, cpu
    except (FileNotFoundError, ProcessLookupError, IndexError):
        pass  # the process is gone
    except KeyboardInterrupt:
        pass
    if samples:
        cpus = [c for c, _ in samples]
        print(f"[measure] {len(samples)} samples: CPU average {sum(cpus) / len(cpus):.1f} %, "
              f"highest {max(cpus):.1f} %; PSS highest {max(p for _, p in samples):.1f} MB")
    else:
        print("[measure] the process ended before the first sample")


if __name__ == "__main__":
    main()
