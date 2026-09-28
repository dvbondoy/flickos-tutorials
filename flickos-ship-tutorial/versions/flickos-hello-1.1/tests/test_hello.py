"""Tests for usr/bin/flickos-hello. Run: python3 -m unittest discover -s tests"""

import importlib.machinery
import importlib.util
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = os.path.dirname(HERE)

# The program has no .py ending, so import it by path.
sys.dont_write_bytecode = True
_loader = importlib.machinery.SourceFileLoader("flickos_hello", os.path.join(PACKAGE, "usr/bin/flickos-hello"))
hello = importlib.util.module_from_spec(importlib.util.spec_from_loader(_loader.name, _loader))
_loader.exec_module(hello)


class GreetingTest(unittest.TestCase):
    def write(self, text):
        f = tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False)
        f.write(text)
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_no_files_gives_the_default(self):
        self.assertEqual(hello.greeting(["/nonexistent"]), "Hello")

    def test_the_last_file_wins(self):
        system = self.write("[Hello]\nGreeting=Hi\n")
        user = self.write("[Hello]\nGreeting=Howdy\n")
        self.assertEqual(hello.greeting([system, user]), "Howdy")

    def test_the_shipped_file_says_mabuhay(self):
        self.assertEqual(hello.greeting([os.path.join(PACKAGE, "etc/xdg/flickos/hello.conf")]), "Mabuhay")


if __name__ == "__main__":
    unittest.main()
