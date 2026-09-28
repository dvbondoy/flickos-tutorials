"""Tests for usr/bin/flickos-hello. Run: python3 -m unittest discover -s tests"""

import configparser
import importlib.machinery
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = os.path.dirname(HERE)
PROGRAM = os.path.join(PACKAGE, "usr/bin/flickos-hello")
SHIPPED_CONF = os.path.join(PACKAGE, "etc/xdg/flickos/hello.conf")
DESKTOP_FILE = os.path.join(PACKAGE, "usr/share/applications/flickos-hello.desktop")

# The program has no .py ending, so import it by its path.
sys.dont_write_bytecode = True
_loader = importlib.machinery.SourceFileLoader("flickos_hello", PROGRAM)
hello = importlib.util.module_from_spec(importlib.util.spec_from_loader(_loader.name, _loader))
_loader.exec_module(hello)


def quiet():
    """Swallow the program's warnings (stderr) in a test that expects them."""
    return mock.patch.object(hello.sys, "stderr", new_callable=io.StringIO)


def run_main(*argv):
    """main(argv) → (exit code, stdout)."""
    with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
        code = hello.main(list(argv))
    return code, out.getvalue()


class HomeTest(unittest.TestCase):
    """Every test gets its own ~/.config and its own /etc/xdg/flickos/hello.conf,
    never the build host's: the build runs on a real FlickOS desktop."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.home = os.path.join(self.root, "config")
        self.system_conf = os.path.join(self.root, "etc/xdg/flickos/hello.conf")
        for patch in (mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": self.home}),
                      mock.patch.object(hello, "SYSTEM_CONF", self.system_conf)):
            patch.start()
            self.addCleanup(patch.stop)

    def write(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def system_says(self, value):
        self.write(self.system_conf, f"[Hello]\nGreeting={value}\n")

    def user_says(self, value):
        self.write(hello.user_conf(), f"[Hello]\nGreeting={value}\n")


class ReadTest(HomeTest):
    def test_no_files_is_the_default(self):
        self.assertEqual(hello.current_greeting(), hello.DEFAULT_GREETING)

    def test_the_system_file_sets_it(self):
        self.system_says("howdy")
        self.assertEqual(hello.current_greeting(), "howdy")

    def test_the_user_wins(self):
        self.system_says("howdy")
        self.user_says("hi")
        self.assertEqual(hello.current_greeting(), "hi")

    def test_text_and_any_case_are_understood(self):
        """1.x's hello.conf held the text (Greeting=Hello), and an administrator
        who edited it kept theirs on upgrade (a conffile)."""
        self.system_says("MABUHAY")
        self.assertEqual(hello.current_greeting(), "mabuhay")
        self.system_says("Good day")
        self.assertEqual(hello.current_greeting(), "good-day")

    def test_an_unknown_greeting_is_ignored_with_a_warning(self):
        self.system_says("howdy")
        self.user_says("Bonjour")
        with quiet() as err:
            self.assertEqual(hello.current_greeting(), "howdy")
        self.assertIn("unknown greeting 'Bonjour'", err.getvalue())

    def test_a_broken_file_is_ignored_with_a_one_line_warning(self):
        self.write(self.system_conf, "garbage [[\n")
        with quiet() as err:
            self.assertEqual(hello.current_greeting(), hello.DEFAULT_GREETING)
        self.assertEqual(len(err.getvalue().splitlines()), 1, err.getvalue())
        self.assertTrue(err.getvalue().startswith("flickos-hello: "))


class CommandTest(HomeTest):
    def test_say(self):
        self.assertEqual(run_main("say", "Ana"), (0, "Hello, Ana!\n"))

    def test_no_command_says_hello_to_you(self):
        with mock.patch.object(hello.getpass, "getuser", return_value="jon"):
            self.assertEqual(run_main(), (0, "Hello, jon!\n"))

    def test_list_is_id_tab_text(self):
        code, out = run_main("greeting", "list")
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertEqual(len(lines), len(hello.GREETINGS))
        self.assertEqual(lines[0], "hello\tHello")

    def test_set_and_current(self):
        self.assertEqual(run_main("greeting", "set", "mabuhay"), (0, ""), "success is quiet")
        self.assertEqual(run_main("greeting", "current"), (0, "mabuhay\n"))
        self.assertEqual(run_main("say", "Ana"), (0, "Mabuhay, Ana!\n"))

    def test_set_default_goes_back_to_the_machines(self):
        self.system_says("howdy")
        run_main("greeting", "set", "hi")
        self.assertEqual(run_main("greeting", "set", "default"), (0, ""))
        self.assertEqual(run_main("greeting", "current"), (0, "howdy\n"))
        self.assertFalse(os.path.exists(hello.user_conf()), "no choice, no file")
        self.assertEqual(run_main("greeting", "set", "default"), (0, ""), "twice is fine")

    def test_set_writes_one_file_and_nothing_else(self):
        run_main("greeting", "set", "hi")
        self.assertEqual(os.listdir(os.path.dirname(hello.user_conf())), ["hello"],
                         "no temporary file left behind")
        ini = configparser.ConfigParser()
        ini.read(hello.user_conf())
        self.assertEqual(ini["Hello"]["Greeting"], "hi")

    def test_an_unknown_greeting_is_a_usage_error(self):
        with quiet(), self.assertRaises(SystemExit) as exit_:
            hello.main(["greeting", "set", "bonjour"])
        self.assertEqual(exit_.exception.code, 2)

    def test_a_read_only_folder_is_an_error_not_a_crash(self):
        folder = os.path.dirname(hello.user_conf())
        os.makedirs(folder)
        os.chmod(folder, 0o500)
        self.addCleanup(os.chmod, folder, 0o700)
        if os.access(folder, os.W_OK):
            self.skipTest("running as root: every folder is writable")
        with quiet() as err:
            self.assertEqual(run_main("greeting", "set", "hi")[0], 1)
        self.assertIn("can't save the greeting", err.getvalue())
        self.assertEqual(os.listdir(folder), [], "no temporary file left behind")


class SingleInstanceTest(unittest.TestCase):
    def test_second_window_is_refused_while_one_is_open(self):
        with tempfile.TemporaryDirectory() as runtime, \
                mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": runtime}):
            with hello.single_instance() as first:
                self.assertTrue(first)
                with hello.single_instance() as second:
                    self.assertFalse(second)
            with hello.single_instance() as again:
                self.assertTrue(again, "closing the window frees the lock")

    def test_show_opens_no_window_while_one_is_open(self):
        with tempfile.TemporaryDirectory() as runtime, \
                mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": runtime}), \
                mock.patch.object(hello, "load_gtk") as load_gtk:
            with hello.single_instance():
                self.assertEqual(run_main("show"), (0, "Hello is already open.\n"))
            load_gtk.assert_not_called()


class NoGtkTest(unittest.TestCase):
    def test_commands_do_not_load_gtk(self):
        """PERF-3: GTK is imported only for the window, so commands start fast
        and work without a display. Run in a fresh Python, which has nothing
        imported yet."""
        check = ("import runpy, sys\n"
                 "sys.argv = [sys.argv[1], 'greeting', 'list']\n"
                 "try:\n    runpy.run_path(sys.argv[0], run_name='__main__')\n"
                 "except SystemExit:\n    pass\n"
                 "print('gi' in sys.modules)\n")
        with tempfile.TemporaryDirectory() as root:
            env = dict(os.environ, XDG_CONFIG_HOME=root, FLICKOS_HELLO_PREFIX=root)
            out = subprocess.run([sys.executable, "-c", check, PROGRAM], env=env,
                                 capture_output=True, text=True, check=True).stdout
        self.assertEqual(out.splitlines()[-1], "False")


class ShippedFilesTest(unittest.TestCase):
    """What must hold between the files of this package (HIG PKG-8)."""

    def test_shipped_conf_names_the_default_greeting(self):
        ini = configparser.ConfigParser()
        ini.read(SHIPPED_CONF, encoding="utf-8")
        self.assertEqual(ini["Hello"]["Greeting"], hello.DEFAULT_GREETING)

    def test_greeting_ids_are_unique_and_simple(self):
        ids = [greeting for greeting, _text in hello.GREETINGS]
        self.assertEqual(len(ids), len(set(ids)))
        for greeting in ids:
            self.assertRegex(greeting, r"^[a-z][a-z-]*$")

    def test_desktop_file_matches_the_program(self):
        entry = configparser.ConfigParser(interpolation=None)
        entry.optionxform = str
        entry.read(DESKTOP_FILE, encoding="utf-8")
        desktop = entry["Desktop Entry"]
        self.assertEqual(desktop["Name"], hello.TITLE, "WIN-4: the title is the Name")
        self.assertEqual(desktop["Icon"], hello.ICON)
        self.assertEqual(desktop["Exec"], "flickos-hello show")
        self.assertEqual(os.path.basename(DESKTOP_FILE), hello.APP_ID + ".desktop",
                         "INT-2: the file name is the Wayland app id")


if __name__ == "__main__":
    unittest.main()
