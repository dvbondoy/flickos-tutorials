#!/usr/bin/env python3
"""vm-run.py: boot the FlickOS live ISO without a window, log in on its
serial console and run commands in it, the way tools/boot-test.py runs its
checks. Nothing is kept: the live session lives in RAM, so every run starts
from the same clean system.

    ./vm-run.py 'cat /etc/os-release' 'apt policy flickos-desktop'
    ./vm-run.py --script upgrade-test.txt
    ./vm-run.py --shot end.png --script upgrade-test.txt

A script has one command per line; empty lines and lines starting with # are
skipped. Each line runs in its own subshell as the live user (sudo works
without a password), with no terminal input, so chain steps that belong
together with && and give apt -y. A line starting with "host:" runs on THIS
computer instead (in this folder), for example to publish a new version to
the local repo half-way through a test.

The VM reaches this computer as 10.0.2.2 (QEMU's user networking), which
QEMU connects to this computer's 127.0.0.1: a server that listens only on
127.0.0.1 is reachable from the VM, and from nowhere else.

It stops at the first command that fails (exit code 1), unless --keep-going.
The whole serial console is saved in vm-run.log.

It borrows the boot and login code from the FlickOS repo's tools/boot-test.py
(`FLICKOS_REPO` or `FLICKOS`, otherwise ~/Documents/Projects/FlickOS), so a change there
reaches this script too.
"""
import argparse
import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = (
    os.environ.get("FLICKOS_REPO")
    or os.environ.get("FLICKOS")
    or os.path.expanduser("~/Documents/Projects/FlickOS")
)

sys.dont_write_bytecode = True  # no __pycache__ in the repo's tools/
_loader = importlib.machinery.SourceFileLoader("boot_test", os.path.join(REPO, "tools/boot-test.py"))
bt = importlib.util.module_from_spec(importlib.util.spec_from_loader(_loader.name, _loader))
_loader.exec_module(bt)


def newest_iso():
    isos = sorted((os.path.join(REPO, f) for f in os.listdir(REPO)
                   if f.startswith("FlickOS-64bit-v") and f.endswith(".iso")), key=os.path.getmtime)
    return isos[-1] if isos else None


def read_steps(opts):
    lines = open(opts.script).read().splitlines() if opts.script else opts.commands
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]


def log_in(console):
    """The boot test's login: user/live, then a quiet shell."""
    console.expect(rb"login: ", 300)
    console.send(f"{bt.LIVE_USER}\n")
    console.expect(rb"Password: ", 60)
    console.send(f"{bt.LIVE_PASSWORD}\n")
    console.expect(rb"\$ $", 60)
    console.buf = b""
    console.send("stty -echo; export PS1= PS2= TERM=dumb SYSTEMD_PAGER=cat PAGER=cat"
                 " PATH=\"$PATH:/usr/sbin:/sbin\"; sudo -n dmesg -n 1 </dev/null 2>/dev/null;"
                 " echo \"@@LOGGED\"\"_IN@@\"\n")
    console.expect(rb"@@LOGGED_IN@@", 60)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("commands", nargs="*", help="commands to run in the VM")
    parser.add_argument("--script", help="file with one command per line")
    parser.add_argument("--iso", help="ISO to boot (default: the newest in $FLICKOS_REPO)")
    parser.add_argument("--mem", default="3G", help="guest RAM (default: 3G)")
    parser.add_argument("--timeout", type=int, default=600, help="seconds one command may take (default: 600)")
    parser.add_argument("--keep-going", action="store_true", help="don't stop at a failed command")
    parser.add_argument("--shot", help="save a PNG of the VM's screen at the end")
    parser.add_argument("--verbose", "-v", action="store_true", help="also print the serial console live")
    opts = parser.parse_args()
    steps = read_steps(opts)
    if not steps:
        parser.error("no commands (give them as arguments or with --script)")
    iso = os.path.abspath(opts.iso or newest_iso() or "")
    if not os.path.isfile(iso):
        sys.exit("no ISO: build one (tools/build-iso.sh) or pass --iso FILE")

    workdir = tempfile.mkdtemp(prefix="vm-run-")
    qmp = os.path.join(workdir, "qmp.sock")
    proc = None
    failed = 0
    try:
        kernel, initrd, cmdline = bt.extract_boot_files(iso, workdir)
        command = ["qemu-system-x86_64", "-m", opts.mem, "-smp", "2",
                   "-kernel", kernel, "-initrd", initrd, "-append", cmdline, "-cdrom", iso,
                   "-device", "virtio-vga", "-display", "none",
                   "-nic", "user,model=virtio-net-pci",
                   "-chardev", "stdio,id=ser0,signal=off", "-serial", "chardev:ser0",
                   "-monitor", "none", "-qmp", f"unix:{qmp},server=on,wait=off"]
        if os.access("/dev/kvm", os.R_OK | os.W_OK):
            command += ["-enable-kvm", "-cpu", "host"]
        print(f"booting {os.path.basename(iso)} …", flush=True)
        started = time.monotonic()
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        console = bt.Console(proc, os.path.join(HERE, "vm-run.log"), opts.verbose)
        log_in(console)
        print(f"logged in after {time.monotonic() - started:.0f} s\n", flush=True)

        for step in steps:
            if step.startswith("host:"):
                print(f"host$ {step[5:].strip()}", flush=True)
                rc = subprocess.run(step[5:], shell=True, cwd=HERE).returncode
                output = ""
            else:
                print(f"vm$ {step}", flush=True)
                rc, output = console.run(f"( {step} ) </dev/null 2>&1", timeout=opts.timeout)
            if output:
                print(output)
            if rc:
                failed += 1
                print(f"(exit {rc})")
            print(flush=True)
            if rc and not opts.keep_going:
                break
        if opts.shot and bt.qmp_screendump(qmp, os.path.abspath(opts.shot)):
            print(f"screenshot: {opts.shot}")
    except bt.Timeout as error:
        print(f"the VM stopped answering: {error}. See vm-run.log", file=sys.stderr)
        return 3
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        shutil.rmtree(workdir, ignore_errors=True)
    print("all commands succeeded" if not failed else f"{failed} command(s) failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
