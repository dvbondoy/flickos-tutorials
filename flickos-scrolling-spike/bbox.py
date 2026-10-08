#!/usr/bin/python3
"""Where each test window is: ./headless.sh run ./bbox.py red=#ff0000 …

Takes one grim screenshot of the whole headless screen and prints, per color,
the box its pixels cover (x y width height) and how many pixels that is, or
"not on screen". The pointer is drawn into grim's picture, so a few pixels
can be missing; the box is still right."""
import subprocess
import sys

ppm = subprocess.run(["grim", "-t", "ppm", "-"], check=True, capture_output=True).stdout
parts = ppm.split(b"\n", 3)                     # P6, "W H", 255, pixels
width, height = map(int, parts[1].split())
pixels = parts[3]
print(f"screen {width}x{height}")
for arg in sys.argv[1:]:
    name, hexcolor = arg.split("=")
    want = bytes.fromhex(hexcolor.lstrip("#"))
    xs, ys, count = [], [], 0
    start = 0
    while (i := pixels.find(want, start)) != -1:
        if i % 3 == 0:
            pixel = i // 3
            xs.append(pixel % width)
            ys.append(pixel // width)
            count += 1
            start = i + 3
        else:
            start = i + 1
    if count:
        x, y = min(xs), min(ys)
        print(f"{name:8} x={x:5} y={y:5} w={max(xs) - x + 1:5} h={max(ys) - y + 1:5}  ({count} px)")
    else:
        print(f"{name:8} not on screen")
