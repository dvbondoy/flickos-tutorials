#!/usr/bin/env python3
"""check-disk.py: check one installed test disk (vm/NAME.qcow2) without a
window, in two parts:

  layout  boot the live ISO with the disk attached, log in on the serial
          console and run check-layout.sh on it as root
  boot    start the installed disk itself, type the passphrase if there is
          one, and save screenshots until the login screen should be up

    ./check-disk.py NAME                      both parts
    ./check-disk.py NAME --passphrase spikepass
    ./check-disk.py NAME --only layout        or --only boot

The disk is attached with snapshot=on: QEMU writes every change into a
temporary file, so checking never changes the install. The UEFI variables are
copied for the same reason. Results go to results/NAME-layout.txt and
results/NAME-boot-*.png.

It borrows the boot and login code from the FlickOS repo's tools/boot-test.py
(FLICKOS_REPO or FLICKOS, otherwise ~/Documents/Projects/FlickOS), like the
ship tutorial's vm-run.py.
"""
import argparse
import functools
import http.server
import importlib.machinery
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
VM = os.path.join(HERE, "vm")
RESULTS = os.path.join(HERE, "results")
REPO = (os.environ.get("FLICKOS_REPO") or os.environ.get("FLICKOS")
        or os.path.expanduser("~/Documents/Projects/FlickOS"))
OVMF_CODE = "/usr/share/OVMF/OVMF_CODE_4M.fd"

sys.dont_write_bytecode = True  # no __pycache__ in the repo's tools/
_loader = importlib.machinery.SourceFileLoader("boot_test", os.path.join(REPO, "tools/boot-test.py"))
bt = importlib.util.module_from_spec(importlib.util.spec_from_loader(_loader.name, _loader))
_loader.exec_module(bt)


def newest_iso():
    isos = sorted((os.path.join(REPO, f) for f in os.listdir(REPO)
                   if f.startswith("FlickOS-64bit-v") and f.endswith(".iso")), key=os.path.getmtime)
    return isos[-1] if isos else None


def kvm():
    return ["-enable-kvm", "-cpu", "host"] if os.access("/dev/kvm", os.R_OK | os.W_OK) else []


class Qmp:
    """A minimal QMP client: screenshots and key presses."""

    def __init__(self, path, timeout=30):
        deadline = time.monotonic() + timeout
        while True:
            try:
                self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.sock.connect(path)
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.2)
        self.stream = self.sock.makefile("rwb")
        self.stream.readline()  # greeting
        self.call("qmp_capabilities")

    def call(self, command, **arguments):
        message = {"execute": command}
        if arguments:
            message["arguments"] = arguments
        self.stream.write(json.dumps(message).encode() + b"\n")
        self.stream.flush()
        while True:
            reply = json.loads(self.stream.readline())
            if "return" in reply or "error" in reply:
                return reply

    def shot(self, path):
        return "return" in self.call("screendump", filename=path, format="png")

    def type(self, text):
        names = {"-": "minus", " ": "spc", ".": "dot", "\n": "ret"}
        for char in text:
            if char.isalnum() and char.isascii():
                keys = [{"type": "qcode", "data": char.lower()}]
                if char.isupper():
                    keys.insert(0, {"type": "qcode", "data": "shift"})
            elif char in names:
                keys = [{"type": "qcode", "data": names[char]}]
            else:
                raise ValueError(f"can't type {char!r}: use letters, digits, - . and space")
            self.call("send-key", keys=keys)
            time.sleep(0.05)


def serve(directory):
    """This folder over HTTP on 127.0.0.1, a free port. The VM sees it as 10.0.2.2."""
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(Quiet, directory=directory)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def log_in(console):
    """The boot test's login: user/live, then a quiet shell (from vm-run.py)."""
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


def stop(proc):
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def check_layout(name, disk, passphrase, workdir):
    iso = newest_iso()
    if not iso:
        sys.exit(f"no ISO in {REPO}")
    kernel, initrd, cmdline = bt.extract_boot_files(iso, workdir)
    server = serve(HERE)
    port = server.server_address[1]
    command = ["qemu-system-x86_64", "-m", "3G", "-smp", "2",
               "-kernel", kernel, "-initrd", initrd, "-append", cmdline, "-cdrom", iso,
               "-drive", f"file={disk},if=virtio,snapshot=on",
               "-device", "virtio-vga", "-display", "none",
               "-nic", "user,model=virtio-net-pci",
               "-chardev", "stdio,id=ser0,signal=off", "-serial", "chardev:ser0",
               "-monitor", "none"] + kvm()
    print(f"layout: booting the live ISO with {name} attached (read-only) …", flush=True)
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    try:
        console = bt.Console(proc, os.path.join(RESULTS, f"{name}-layout.log"), False)
        log_in(console)
        rc, output = console.run(
            f"curl -fsS http://10.0.2.2:{port}/check-layout.sh -o /tmp/check-layout.sh"
            f" && sudo sh /tmp/check-layout.sh '{passphrase}' </dev/null 2>&1", timeout=600)
    finally:
        stop(proc)
        server.shutdown()
    path = os.path.join(RESULTS, f"{name}-layout.txt")
    with open(path, "w") as out:
        out.write(output + "\n")
    print(output)
    print(f"\nlayout: saved {os.path.relpath(path, HERE)}\n")
    return rc


def check_boot(name, disk, passphrase, seconds, workdir):
    firmware = open(os.path.join(VM, f"{name}.firmware")).read().strip()
    qmp_path = os.path.join(workdir, "qmp.sock")
    command = ["qemu-system-x86_64", "-m", "3G", "-smp", "2",
               "-drive", f"file={disk},if=virtio,snapshot=on",
               "-device", "virtio-vga", "-display", "none",
               "-nic", "user,model=virtio-net-pci", "-monitor", "none",
               "-qmp", f"unix:{qmp_path},server=on,wait=off"] + kvm()
    if firmware == "uefi":
        vars_copy = os.path.join(workdir, "vars.fd")
        shutil.copy(os.path.join(VM, f"{name}.vars"), vars_copy)
        command += ["-drive", f"if=pflash,format=raw,readonly=on,file={OVMF_CODE}",
                    "-drive", f"if=pflash,format=raw,file={vars_copy}"]
    print(f"boot: starting {name} ({firmware}) without a window …", flush=True)
    proc = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    shots = []
    try:
        qmp = Qmp(qmp_path)
        started = time.monotonic()
        typed = not passphrase
        while time.monotonic() - started < seconds:
            time.sleep(5)
            elapsed = int(time.monotonic() - started)
            # GRUB asks for the passphrase a few seconds in. Typing it early
            # is harmless: keys wait in the keyboard buffer until GRUB reads.
            if not typed and elapsed >= 10:
                qmp.type(passphrase + "\n")
                typed = True
                print(f"boot: typed the passphrase at {elapsed} s", flush=True)
            if elapsed % 15 < 5 or time.monotonic() - started >= seconds:
                path = os.path.join(RESULTS, f"{name}-boot-{elapsed:03d}s.png")
                if qmp.shot(path):
                    shots.append(path)
            if proc.poll() is not None:
                print("boot: QEMU exited early")
                break
    finally:
        stop(proc)
    for path in shots:
        print(f"boot: saved {os.path.relpath(path, HERE)}")
    print()
    return 0 if shots else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("name", help="the disk: vm/NAME.qcow2")
    parser.add_argument("--passphrase", default="", help="the disk's passphrase, if encrypted")
    parser.add_argument("--only", choices=["layout", "boot"])
    parser.add_argument("--seconds", type=int, default=90, help="how long the boot part runs (default 90)")
    opts = parser.parse_args()
    disk = os.path.join(VM, f"{opts.name}.qcow2")
    if not os.path.exists(disk):
        sys.exit(f"no disk {disk}")
    os.makedirs(RESULTS, exist_ok=True)
    workdir = tempfile.mkdtemp(prefix="check-disk-")
    failed = 0
    try:
        if opts.only in (None, "layout"):
            failed += check_layout(opts.name, disk, opts.passphrase, workdir) != 0
        if opts.only in (None, "boot"):
            failed += check_boot(opts.name, disk, opts.passphrase, opts.seconds, workdir) != 0
    except bt.Timeout as error:
        print(f"the VM stopped answering: {error}", file=sys.stderr)
        return 3
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
