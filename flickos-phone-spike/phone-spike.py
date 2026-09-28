#!/usr/bin/python3
"""Phase 0 spike for docs/design/flickos-phone.md.

A KDE Connect peer in Python's standard library (plus the openssl command),
to find out what the design has to know. It never connects to the phone's
main port itself: it announces itself and lets the phone connect, so it is
always the TLS client (ADR-003).

Type `help` for the commands. Everything is also logged to spike.log.

    python3 phone-spike.py                  # the real thing: LAN, UDP broadcast
    python3 phone-spike.py --local --dir D  # loopback only, no UDP, state in D
                                            # (test-loopback.sh uses this)
"""

import argparse
import hashlib
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import threading
import time
import uuid

parser = argparse.ArgumentParser(description="KDE Connect peer spike")
parser.add_argument("--dir", help="where phone-state/, received/ and spike.log go "
                    "(default: next to this script)")
parser.add_argument("--local", action="store_true",
                    help="listen on 127.0.0.1 only, no UDP; write the TCP port to DIR/port")
ARGS = parser.parse_args()

HERE = os.path.abspath(ARGS.dir or os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(HERE, "phone-state")
RECEIVED = os.path.join(HERE, "received")
LOG = os.path.join(HERE, "spike.log")

UDP_PORT = 1716
TCP_PORTS = range(1716, 1765)
PAYLOAD_PORTS = range(1739, 1765)
MAX_IDENTITY = 8192
MAX_PACKET = 1 << 20
ANNOUNCE_SECONDS = 5
PAIR_SECONDS = 30
NAME = "FlickOS spike"
CAPS = [
    "kdeconnect.share.request",
    "kdeconnect.clipboard",
    "kdeconnect.clipboard.connect",
    "kdeconnect.ping",
]

log_lock = threading.Lock()
started = time.monotonic()


def log(msg):
    line = f"[{time.monotonic() - started:7.1f}s] {msg}"
    with log_lock:
        print(line, flush=True)
        with open(LOG, "a") as f:
            f.write(line + "\n")


def packet(ptype, body, **extra):
    d = {"id": int(time.time() * 1000), "type": ptype, "body": body}
    d.update(extra)
    return (json.dumps(d) + "\n").encode()


class LineReader:
    def __init__(self, sock, limit):
        self.sock, self.limit, self.buf = sock, limit, b""

    def readline(self):
        while b"\n" not in self.buf:
            if len(self.buf) > self.limit:
                raise ValueError(f"line longer than {self.limit} bytes")
            data = self.sock.recv(65536)
            if not data:
                raise EOFError("connection closed")
            self.buf += data
        line, _, self.buf = self.buf.partition(b"\n")
        return json.loads(line)


# --- identity and certificates -------------------------------------------

def openssl(*args, data=None):
    return subprocess.run(["openssl", *args], input=data, capture_output=True,
                          check=True).stdout


def setup():
    os.makedirs(os.path.join(STATE, "trusted"), mode=0o700, exist_ok=True)
    os.makedirs(RECEIVED, exist_ok=True)
    idfile = os.path.join(STATE, "device_id")
    if not os.path.exists(idfile):
        with open(idfile, "w") as f:
            f.write(uuid.uuid4().hex)
    with open(idfile) as f:
        dev_id = f.read().strip()
    key = os.path.join(STATE, "key.pem")
    cert = os.path.join(STATE, "cert.pem")
    if not os.path.exists(cert):
        t = time.monotonic()
        openssl("req", "-x509", "-newkey", "ec",
                "-pkeyopt", "ec_paramgen_curve:prime256v1", "-noenc",
                "-keyout", key, "-out", cert, "-sha512", "-days", "3650",
                "-subj", f"/O=KDE/OU=KDE Connect/CN={dev_id}")
        os.chmod(key, 0o600)
        log(f"made certificate in {time.monotonic() - t:.2f}s")
    with open(cert) as f:
        der = ssl.PEM_cert_to_DER_cert(f.read())
    return dev_id, key, cert, der


def spki(cert_der):
    pub = openssl("x509", "-pubkey", "-noout",
                  data=ssl.DER_cert_to_PEM_cert(cert_der).encode())
    return openssl("pkey", "-pubin", "-outform", "DER", data=pub)


def cert_cn(cert_der):
    subj = openssl("x509", "-noout", "-subject", "-nameopt", "RFC2253",
                   data=ssl.DER_cert_to_PEM_cert(cert_der).encode()).decode()
    m = re.search(r"CN=([^,\n]+)", subj)
    return m.group(1) if m else None, subj.strip()


def cert_info(cert_der):
    return openssl("x509", "-noout", "-subject", "-dates", "-text",
                   data=ssl.DER_cert_to_PEM_cert(cert_der).encode()).decode()


def verification_key(my_der, their_der, timestamp):
    """pairinghandler.cpp: sha256(bigger key, smaller key, timestamp)[:8]."""
    a, b = spki(my_der), spki(their_der)
    if a < b:
        a, b = b, a
    h = hashlib.sha256(a + b + str(timestamp).encode()).hexdigest()
    return h[:8].upper()


def sha(der):
    return hashlib.sha256(der).hexdigest()


# --- the spike -------------------------------------------------------------

class Link:
    def __init__(self, tls, reader, dev_id, name, der, addr):
        self.tls, self.reader, self.id, self.name = tls, reader, dev_id, name
        self.der, self.addr = der, addr
        self.paired = False
        self.requested = False
        self.pending = None      # timestamp of the phone's pair request
        self.send_lock = threading.Lock()

    def send(self, ptype, body, **extra):
        with self.send_lock:
            self.tls.sendall(packet(ptype, body, **extra))


class Spike:
    def __init__(self):
        self.id, self.key, self.cert, self.der = setup()
        self.links = {}
        self.tcp_port = None
        self.udp = None
        self.announce = True
        self.last_answer = {}

    # contexts
    def client_ctx(self):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.load_cert_chain(self.cert, self.key)
        return ctx

    def trusted_path(self, dev_id):
        return os.path.join(STATE, "trusted", dev_id + ".pem")

    def trusted_der(self, dev_id):
        try:
            with open(self.trusted_path(dev_id)) as f:
                return ssl.PEM_cert_to_DER_cert(f.read())
        except FileNotFoundError:
            return None

    def identity(self):
        return {"deviceId": self.id, "deviceName": NAME, "deviceType": "laptop",
                "protocolVersion": 8, "incomingCapabilities": CAPS,
                "outgoingCapabilities": CAPS}

    def discovery(self):
        return packet("kdeconnect.identity", {
            "deviceId": self.id, "deviceName": NAME, "protocolVersion": 8,
            "tcpPort": self.tcp_port})

    # UDP
    def udp_loop(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.bind(("", UDP_PORT))
        self.udp = s
        log(f"UDP listening on {UDP_PORT}")
        threading.Thread(target=self.announce_loop, daemon=True).start()
        while True:
            data, addr = s.recvfrom(65536)
            try:
                body = json.loads(data)["body"]
            except (ValueError, KeyError):
                log(f"UDP from {addr[0]}: not a packet ({len(data)} bytes)")
                continue
            if body.get("deviceId") == self.id:
                continue
            log(f"UDP identity from {addr[0]}: {json.dumps(body)}")
            now = time.monotonic()
            if now - self.last_answer.get(addr[0], 0) > 2:
                self.last_answer[addr[0]] = now
                s.sendto(self.discovery(), (addr[0], UDP_PORT))
                log(f"  answered {addr[0]} with our identity (UDP unicast)")

    def announce_loop(self):
        n = 0
        while True:
            if self.announce and self.udp and not self.links:
                try:
                    self.udp.sendto(self.discovery(), ("255.255.255.255", UDP_PORT))
                    if n % 12 == 0:
                        log("announced (UDP broadcast)")
                    n += 1
                except OSError as e:
                    log(f"announce failed: {e}")
            time.sleep(ANNOUNCE_SECONDS)

    # TCP
    def tcp_loop(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        for port in TCP_PORTS:
            try:
                srv.bind(("127.0.0.1" if ARGS.local else "", port))
                break
            except OSError:
                continue
        else:
            log("no free TCP port in 1716-1764")
            return
        srv.listen(8)
        self.tcp_port = port
        log(f"TCP listening on {port}")
        while True:
            sock, addr = srv.accept()
            threading.Thread(target=self.handle, args=(sock, addr), daemon=True).start()

    def handle(self, sock, addr):
        ip = addr[0]
        try:
            sock.settimeout(10)
            r = LineReader(sock, MAX_IDENTITY)
            pkt = r.readline()
            body = pkt.get("body", {})
            log(f"TCP from {ip}: plain identity {json.dumps(body)}")
            if r.buf:
                log(f"  WARNING: {len(r.buf)} bytes after the identity before TLS")
            if body.get("targetDeviceId") not in (None, self.id):
                log("  not for us, closing")
                return
            if body.get("protocolVersion", 0) < 8:
                log("  protocol < 8, closing")
                return
            t = time.monotonic()
            tls = self.client_ctx().wrap_socket(sock, server_side=False)
            der = tls.getpeercert(binary_form=True)
            cn, subj = cert_cn(der)
            log(f"  TLS as client ok in {time.monotonic() - t:.2f}s: {tls.version()} "
                f"{tls.cipher()[0]}; phone cert {subj}; sha256 {sha(der)[:16]}")
            if cn != body.get("deviceId"):
                log(f"  certificate CN {cn} != deviceId {body.get('deviceId')}, closing")
                return
            tls.sendall(packet("kdeconnect.identity", self.identity()))
            r = LineReader(tls, MAX_IDENTITY)
            ident = r.readline()["body"]
            log(f"  secure identity: {json.dumps(ident)}")
            if ident.get("deviceId") != body.get("deviceId"):
                log("  deviceId changed inside TLS, closing")
                return
            tls.settimeout(None)
            link = Link(tls, r, ident["deviceId"], ident.get("deviceName"), der, ip)
            known = self.trusted_der(link.id)
            if known is not None:
                link.paired = known == der
                log(f"  known phone, certificate {'matches' if link.paired else 'DIFFERS'}")
            old = self.links.get(link.id)
            self.links[link.id] = link
            if old:
                try:
                    old.tls.close()
                except OSError:
                    pass
            log(f"LINK up: {link.name} ({'paired' if link.paired else 'not paired'})")
            self.packets(link)
        except Exception as e:
            log(f"connection from {ip} ended: {type(e).__name__}: {e}")
        finally:
            sock.close()

    def packets(self, link):
        try:
            while True:
                link.reader.limit = MAX_PACKET if link.paired else MAX_IDENTITY
                pkt = link.reader.readline()
                self.dispatch(link, pkt)
        finally:
            if self.links.get(link.id) is link:
                del self.links[link.id]
            log(f"LINK down: {link.name}")

    def dispatch(self, link, pkt):
        ptype, body = pkt.get("type"), pkt.get("body", {})
        if ptype == "kdeconnect.pair":
            return self.on_pair(link, body)
        if not link.paired:
            log(f"dropped {ptype} from unpaired {link.name}: {json.dumps(body)[:200]}")
            return
        if ptype == "kdeconnect.share.request":
            if "url" in body:
                log(f"PAGE from {link.name}: {body['url']}   (full body: {json.dumps(body)})")
            elif "text" in body:
                log(f"TEXT from {link.name}: {body['text']!r}")
            elif "filename" in body:
                log(f"FILE from {link.name}: {json.dumps(pkt)}")
                threading.Thread(target=self.receive_file, args=(link, pkt),
                                 daemon=True).start()
            else:
                log(f"share.request with unknown body: {json.dumps(body)}")
        elif ptype in ("kdeconnect.clipboard", "kdeconnect.clipboard.connect"):
            log(f"CLIPBOARD ({ptype}) from {link.name}: {json.dumps(body)[:300]}")
        elif ptype == "kdeconnect.ping":
            log(f"PING from {link.name}: {json.dumps(body)}")
        else:
            log(f"other packet {ptype}: {json.dumps(body)[:300]}")

    def on_pair(self, link, body):
        if body.get("pair"):
            if link.requested:
                link.requested = False
                self.trust(link)
                log(f"PAIRED: {link.name} accepted our request")
                return
            ts = body.get("timestamp")
            skew = None if ts is None else ts - int(time.time())
            key = verification_key(self.der, link.der, ts) if ts is not None else "?"
            link.pending = ts
            log(f"PAIR REQUEST from {link.name}: timestamp {ts} (clock skew {skew}s), "
                f"verification key {key}")
            log('  compare it with the phone, then type "y" to pair or "n" to refuse')
            threading.Timer(PAIR_SECONDS, self.pair_timeout, args=(link, ts)).start()
        else:
            was = link.paired
            link.paired = link.requested = False
            link.pending = None
            try:
                os.unlink(self.trusted_path(link.id))
            except FileNotFoundError:
                pass
            log(f"UNPAIR from {link.name} (was paired: {was})")

    def pair_timeout(self, link, ts):
        if link.pending == ts and not link.paired:
            link.pending = None
            log(f"pair request from {link.name} timed out")

    def trust(self, link):
        with open(self.trusted_path(link.id), "w") as f:
            f.write(ssl.DER_cert_to_PEM_cert(link.der))
        link.paired = True

    def receive_file(self, link, pkt):
        body, size = pkt["body"], pkt.get("payloadSize", -1)
        port = pkt.get("payloadTransferInfo", {}).get("port")
        name = os.path.basename(body.get("filename", "file")).lstrip(".") or "file"
        path = os.path.join(RECEIVED, name)
        stem, ext = os.path.splitext(path)
        n = 2
        while os.path.exists(path):
            path, n = f"{stem} ({n}){ext}", n + 1
        try:
            t = time.monotonic()
            raw = socket.create_connection((link.addr, port), timeout=10)
            tls = self.client_ctx().wrap_socket(raw, server_side=False)
            der = tls.getpeercert(binary_form=True)
            log(f"  payload TLS as client ok; same certificate as the link: {der == link.der}")
            got = 0
            with open(path + ".part", "wb") as f:
                while size < 0 or got < size:
                    data = tls.recv(min(65536, size - got) if size > 0 else 65536)
                    if not data:
                        break
                    f.write(data)
                    got += len(data)
            tls.close()
            os.rename(path + ".part", path)
            dt = time.monotonic() - t
            log(f"  saved {path}: {got} of {size} bytes in {dt:.1f}s "
                f"({got / dt / 1e6:.1f} MB/s)")
        except Exception as e:
            log(f"  file receive failed: {type(e).__name__}: {e}")

    def send_file(self, link, path, strict):
        size = os.path.getsize(path)
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        for port in PAYLOAD_PORTS:
            try:
                srv.bind(("", port))
                break
            except OSError:
                continue
        srv.listen(1)
        srv.settimeout(60)

        def serve():
            try:
                conn, addr = srv.accept()
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ctx.load_cert_chain(self.cert, self.key)
                if strict:
                    ctx.verify_mode = ssl.CERT_REQUIRED
                    ctx.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN
                    ctx.load_verify_locations(cadata=ssl.DER_cert_to_PEM_cert(link.der))
                t = time.monotonic()
                tls = ctx.wrap_socket(conn, server_side=True)
                der = tls.getpeercert(binary_form=True)
                log(f"  payload TLS as server ok ({'CERT_REQUIRED' if strict else 'CERT_NONE'}); "
                    f"phone certificate presented: {der is not None}, "
                    f"matches: {der == link.der}")
                with open(path, "rb") as f:
                    while chunk := f.read(65536):
                        tls.sendall(chunk)
                tls.close()
                log(f"  sent {size} bytes in {time.monotonic() - t:.1f}s")
            except Exception as e:
                log(f"  file send failed: {type(e).__name__}: {e}")
            finally:
                srv.close()

        threading.Thread(target=serve, daemon=True).start()
        link.send("kdeconnect.share.request",
                  {"filename": os.path.basename(path), "numberOfFiles": 1,
                   "totalPayloadSize": size},
                  payloadSize=size, payloadTransferInfo={"port": port})
        log(f"offered {path} ({size} bytes) on port {port}")

    # commands
    def link(self):
        if not self.links:
            print("no phone connected")
            return None
        return next(iter(self.links.values()))

    def command(self, line):
        cmd, _, arg = line.strip().partition(" ")
        link = self.link() if cmd not in ("", "help", "quit", "mem", "phones",
                                         "announce", "info") else None
        if cmd in ("y", "n"):
            if not link or link.pending is None:
                print("no pair request waiting")
                return
            link.pending = None
            if cmd == "y":
                link.send("kdeconnect.pair", {"pair": True})
                self.trust(link)
                log(f"PAIRED with {link.name} (we accepted)")
            else:
                link.send("kdeconnect.pair", {"pair": False})
                log(f"refused {link.name}")
        elif cmd == "pair" and link:
            ts = int(time.time())
            link.requested = True
            link.send("kdeconnect.pair", {"pair": True, "timestamp": ts})
            log(f"asked {link.name} to pair, verification key "
                f"{verification_key(self.der, link.der, ts)}")
        elif cmd == "unpair" and link:
            link.send("kdeconnect.pair", {"pair": False})
            self.on_pair(link, {"pair": False})
        elif cmd == "url" and link:
            link.send("kdeconnect.share.request", {"url": arg})
            log(f"sent page {arg}")
        elif cmd == "text" and link:
            link.send("kdeconnect.share.request", {"text": arg})
            log(f"sent text {arg!r}")
        elif cmd == "clip" and link:
            link.send("kdeconnect.clipboard", {"content": arg})
            log(f"sent clipboard {arg!r}")
        elif cmd == "ping" and link:
            link.send("kdeconnect.ping", {})
            log("sent ping")
        elif cmd in ("file", "file-loose") and link:
            self.send_file(link, os.path.expanduser(arg), strict=cmd == "file")
        elif cmd == "phones":
            for l in self.links.values():
                print(f"{l.name}  {l.id}  {l.addr}  paired={l.paired}")
        elif cmd == "info":
            for l in self.links.values():
                print(cert_info(l.der))
        elif cmd == "announce":
            self.announce = arg != "off"
            log(f"announcing {'on' if self.announce else 'off'}")
        elif cmd == "mem":
            with open("/proc/self/smaps_rollup") as f:
                rows = [r.split()[:2] for r in f if r.split()[0] in ("Rss:", "Pss:", "Private_Dirty:")]
            log("memory: " + ", ".join(f"{k} {int(v) / 1024:.1f} MB" for k, v in rows))
        elif cmd == "help":
            print(__doc__.split("Type")[0].strip())
            print("\ny / n            answer the phone's pair request\n"
                  "pair / unpair    ask the phone to pair / forget it\n"
                  "url URL          send a page to the phone\n"
                  "text TEXT        send text\n"
                  "clip TEXT        send clipboard text\n"
                  "file PATH        send a file (payload TLS verifies the phone)\n"
                  "file-loose PATH  send a file without asking for the phone's certificate\n"
                  "ping, phones, info, mem, announce on|off, quit")
        elif cmd == "quit":
            raise SystemExit
        elif cmd:
            print("unknown command or no phone connected; type help")

    def run(self):
        log(f"--- spike started: device id {self.id}, name {NAME!r}, python "
            f"{sys.version.split()[0]}, {ssl.OPENSSL_VERSION}")
        threading.Thread(target=self.tcp_loop, daemon=True).start()
        while self.tcp_port is None:
            time.sleep(0.05)
        if ARGS.local:
            with open(os.path.join(HERE, "port"), "w") as f:
                f.write(str(self.tcp_port))
            log("local mode: no UDP, nothing announced")
        else:
            threading.Thread(target=self.udp_loop, daemon=True).start()
        print('Type "help" for commands.')
        try:
            while True:
                self.command(input())
        except (EOFError, KeyboardInterrupt, SystemExit):
            log("--- spike stopped")


if __name__ == "__main__":
    Spike().run()
