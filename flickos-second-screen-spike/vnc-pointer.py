#!/usr/bin/python3
"""Log in like rfb-login.py, then put the pointer at X Y of the VNC screen
(what a tap on the phone does). Usage: vnc-pointer.py HOST PORT USER PASSWORD X Y [--click]"""
import runpy, struct, sys, time
host, port, user, password, x, y = sys.argv[1:7]
click = "--click" in sys.argv
sys.argv = ["rfb-login.py", host, port, user, password]
login = runpy.run_path(__file__.replace("vnc-pointer.py", "rfb-login.py"))
t = login["t"]
for mask in ([1, 0] if click else [0]):
    t.sendall(struct.pack(">BBHH", 5, mask, int(x), int(y)))
    time.sleep(0.05)
time.sleep(0.3)
print(f"pointer at {x},{y}{' + click' if click else ''}")
