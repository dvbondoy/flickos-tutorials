#!/usr/bin/python3
"""A pretend phone, to test phone-spike.py without a real one.

It plays the part the Android app plays, in the same order:

 1. connect to the spike's TCP port and send a plain identity
 2. start TLS as the *server* (the TCP connector is the TLS server)
 3. swap full identities inside TLS
 4. share a page before pairing (the spike must drop it)
 5. ask to pair, and wait for the spike to accept
 6. share a page, then a file with a hostile name (the spike must clean it)

Run it through test-loopback.sh, which starts the spike in --local mode and
types "y" for it. Or by hand:

    python3 phone-spike.py --local --dir /tmp/x      # terminal 1
    python3 fake-phone.py --port $(cat /tmp/x/port) --target $(cat /tmp/x/phone-state/device_id)
"""

import argparse
import json
import os
import socket
import ssl
import subprocess
import tempfile
import time
import uuid


def packet(ptype, body, **extra):
    d = {"id": int(time.time() * 1000), "type": ptype, "body": body}
    d.update(extra)
    return (json.dumps(d) + "\n").encode()


def say(msg):
    print(f"fake phone: {msg}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True, help="the spike's TCP port")
    ap.add_argument("--target", required=True, help="the spike's device id")
    args = ap.parse_args()

    tmp = tempfile.mkdtemp()
    my_id = uuid.uuid4().hex
    key, cert = os.path.join(tmp, "key.pem"), os.path.join(tmp, "cert.pem")
    subprocess.run(["openssl", "req", "-x509", "-newkey", "ec",
                    "-pkeyopt", "ec_paramgen_curve:prime256v1", "-noenc",
                    "-keyout", key, "-out", cert, "-days", "10",
                    "-subj", f"/O=KDE/OU=KDE Connect/CN={my_id}"],
                   check=True, capture_output=True)

    # 1. plain identity, like the app's first line
    s = socket.create_connection(("127.0.0.1", args.port))
    s.sendall(packet("kdeconnect.identity", {
        "deviceId": my_id, "deviceName": "Fake phone", "protocolVersion": 8,
        "deviceType": "phone", "targetDeviceId": args.target,
        "targetProtocolVersion": 8}))

    # 2. TLS as server. The real app asks for the client's certificate
    # (Qt's QueryPeer); Python's ssl can't "ask but accept anything", so the
    # fake doesn't ask. That's the stdlib limit ADR-003 is about.
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    ctx.verify_mode = ssl.CERT_NONE
    tls = ctx.wrap_socket(s, server_side=True)
    say(f"TLS up ({tls.version()})")

    # 3. identities inside TLS
    tls.sendall(packet("kdeconnect.identity", {
        "deviceId": my_id, "deviceName": "Fake phone", "deviceType": "phone",
        "protocolVersion": 8, "incomingCapabilities": [],
        "outgoingCapabilities": ["kdeconnect.share.request"]}))
    lines = tls.makefile("rb")
    their = json.loads(lines.readline())["body"]
    say(f"the spike says it is {their['deviceName']!r} ({their['deviceId']})")

    # 4. before pairing: must be dropped
    tls.sendall(packet("kdeconnect.share.request", {"url": "https://example.org/before-pairing"}))
    say("shared a page before pairing (should be dropped)")

    # 5. pair
    tls.sendall(packet("kdeconnect.pair", {"pair": True, "timestamp": int(time.time())}))
    say("asked to pair, waiting for the answer")
    answer = json.loads(lines.readline())
    say(f"answer: {answer['body']}")
    if not answer["body"].get("pair"):
        say("refused, stopping")
        return

    # 6. after pairing
    tls.sendall(packet("kdeconnect.share.request", {"url": "https://example.org/after-pairing"}))
    say("shared a page after pairing")

    data = b"hello from the fake phone\n" * 500
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    tls.sendall(packet("kdeconnect.share.request",
                       {"filename": "../.evil.txt", "numberOfFiles": 1,
                        "totalPayloadSize": len(data)},
                       payloadSize=len(data), payloadTransferInfo={"port": port}))
    say(f"offered a file called '../.evil.txt' ({len(data)} bytes) on port {port}")
    conn, _ = srv.accept()
    ftls = ctx.wrap_socket(conn, server_side=True)
    ftls.sendall(data)
    ftls.close()
    say("file sent")
    time.sleep(1)
    tls.close()
    say("done")


if __name__ == "__main__":
    main()
