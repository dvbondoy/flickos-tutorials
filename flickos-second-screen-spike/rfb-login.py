#!/usr/bin/python3
"""Log in to wayvnc the way AVNC does with VeNCrypt X509Plain, stdlib only.

  rfb-login.py HOST PORT USER PASSWORD [--pin SHA256]

RFB 3.8 handshake -> security type 19 (VeNCrypt) -> subtype 262
(X509Plain) -> TLS -> username and password -> ServerInit (screen size).
The certificate isn't checked against a CA: like AVNC's "trust this
certificate?" prompt, it prints the fingerprint, and --pin makes a
different one fail (what a phone that trusted it once would do).
"""
import argparse, hashlib, socket, ssl, struct

p = argparse.ArgumentParser()
p.add_argument("host"); p.add_argument("port", type=int)
p.add_argument("user"); p.add_argument("password"); p.add_argument("--pin")
a = p.parse_args()

def read(s, n):
    data = b""
    while len(data) < n:
        chunk = s.recv(n - len(data))
        if not chunk:
            raise SystemExit(f"server closed the connection (wanted {n} bytes, got {data!r})")
        data += chunk
    return data

s = socket.create_connection((a.host, a.port), timeout=10)
version = read(s, 12); print("server:", version.decode().strip())
s.sendall(b"RFB 003.008\n")
n = read(s, 1)[0]
types = list(read(s, n)); print("security types:", types)
if 19 not in types:
    raise SystemExit("no VeNCrypt (19)")
s.sendall(bytes([19]))
print("VeNCrypt version:", tuple(read(s, 2))); s.sendall(bytes([0, 2]))
if read(s, 1)[0] != 0:
    raise SystemExit("server refused VeNCrypt 0.2")
n = read(s, 1)[0]
subtypes = struct.unpack(f">{n}I", read(s, 4 * n)); print("subtypes:", subtypes)
if 262 not in subtypes:
    raise SystemExit("no X509Plain (262)")
s.sendall(struct.pack(">I", 262))
if read(s, 1)[0] != 1:
    raise SystemExit("server refused X509Plain")
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE          # checked below by fingerprint
t = ctx.wrap_socket(s, server_hostname=a.host)
pin = hashlib.sha256(t.getpeercert(binary_form=True)).hexdigest()
print(f"TLS {t.version()} {t.cipher()[0]}; certificate sha256 {pin}")
if a.pin and a.pin.lower() != pin:
    raise SystemExit("certificate changed: refusing (pinned one differs)")
u, w = a.user.encode(), a.password.encode()
t.sendall(struct.pack(">II", len(u), len(w)) + u + w)
result = struct.unpack(">I", read(t, 4))[0]
if result != 0:
    reason = read(t, struct.unpack(">I", read(t, 4))[0]).decode(errors="replace")
    raise SystemExit(f"login failed: {reason!r}")
t.sendall(b"\x01")                        # ClientInit: shared
width, height = struct.unpack(">HH", read(t, 4)); read(t, 16)
name = read(t, struct.unpack(">I", read(t, 4))[0]).decode()
print(f"logged in: screen {width}x{height} {name!r}")
