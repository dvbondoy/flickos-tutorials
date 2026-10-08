#!/usr/bin/python3
"""Print which test window has the focus: ./headless.sh run ./focused.py"""
import importlib.machinery, sys
sys.argv = ["focused.py", "none", "none"]
exec(open(__file__.replace("focused.py", "activate.py")).read().split("handles = ")[0])
print("focused:", [w.app_id for w in daemon.tiler.windows.values() if w.activated])
