#!/usr/bin/python3
"""For each verb of a Python helper: every program it can start and every
file it can change, with the expression that builds the argument.

Reference answer for exercise 3. It reads the syntax tree (ast) only:

  1. finds VERBS = {"verb": cmd_function, ...};
  2. follows calls from each cmd_ function to the module's other functions
     (by name: a call graph);
  3. lists the SINKS in every function it reaches:
       program  subprocess.run/Popen/call/check_output, os.system, os.exec*
       file     open(..., "w"/"a"/"x"), os.replace/rename/unlink/remove/
                chmod/chown/makedirs/mkdir, shutil.*, tempfile.mkstemp
     and for a program, which argv items are constants and which are not;
  4. marks a WRAPPER: a function that passes one of its own parameters to a
     sink (run_tool, gpasswd, ufw). Calls of a wrapper are sinks too, so
     run_tool(["chpasswd"], f"{name}:{password}\\n") is seen with its values.

    python3 sinks.py HELPER [VERB]
"""

import ast
import collections
import sys

PROGRAM_CALLS = {"subprocess.run", "subprocess.Popen", "subprocess.call", "subprocess.check_call",
                 "subprocess.check_output", "os.system", "os.popen", "os.execv", "os.execvp", "os.execve",
                 "os.spawnv", "os.posix_spawn"}
FILE_CALLS = {"os.replace", "os.rename", "os.unlink", "os.remove", "os.chmod", "os.chown", "os.makedirs",
              "os.mkdir", "os.symlink", "os.link", "shutil.copy", "shutil.copyfile", "shutil.move",
              "shutil.rmtree", "tempfile.mkstemp"}


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        inner = dotted(node.value)
        return f"{inner}.{node.attr}" if inner else None
    return None


def opens_for_writing(call):
    if dotted(call.func) not in ("open", "os.fdopen", "io.open", "gzip.open"):
        return False
    mode = call.args[1] if len(call.args) > 1 else next((k.value for k in call.keywords if k.arg == "mode"), None)
    return isinstance(mode, ast.Constant) and isinstance(mode.value, str) and any(c in mode.value for c in "wax+")


def classify_argv(node):
    """[(text, 'const'|'VAR')] for a list/tuple argv, else one VAR item."""
    if isinstance(node, (ast.List, ast.Tuple)):
        items = []
        for elt in node.elts:
            text = ast.unparse(elt)
            items.append((text, "const" if isinstance(elt, ast.Constant) else "VAR"))
        return items
    return [(ast.unparse(node), "VAR")]


class Module:
    def __init__(self, path):
        with open(path, encoding="utf-8") as f:
            self.tree = ast.parse(f.read(), path)
        self.functions = {n.name: n for n in self.tree.body if isinstance(n, ast.FunctionDef)}
        self.verbs = {}
        for node in self.tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "VERBS" for t in node.targets):
                if isinstance(node.value, ast.Dict):
                    for key, value in zip(node.value.keys, node.value.values):
                        if isinstance(key, ast.Constant):
                            self.verbs[key.value] = ast.unparse(value)
        self.wrappers = self.find_wrappers()

    def calls_in(self, function):
        return [n for n in ast.walk(function) if isinstance(n, ast.Call)]

    def find_wrappers(self):
        """Functions whose own parameter reaches a program or file sink."""
        wrappers = {}
        changed = True
        while changed:
            changed = False
            for name, function in self.functions.items():
                if name in wrappers:
                    continue
                params = {a.arg for a in function.args.args + function.args.kwonlyargs}
                if function.args.vararg:
                    params.add(function.args.vararg.arg)
                for call in self.calls_in(function):
                    callee = dotted(call.func)
                    kind = ("program" if callee in PROGRAM_CALLS else
                            "file" if callee in FILE_CALLS or opens_for_writing(call) else
                            wrappers.get(callee))
                    if not kind:
                        continue
                    used = {n.id for arg in call.args for n in ast.walk(arg) if isinstance(n, ast.Name)}
                    if used & params:
                        wrappers[name] = kind
                        changed = True
                        break
        return wrappers

    def reachable(self, start):
        seen, order, todo = set(), [], [start]
        while todo:
            name = todo.pop(0)
            if name in seen or name not in self.functions:
                continue
            seen.add(name)
            order.append(name)
            for call in self.calls_in(self.functions[name]):
                callee = dotted(call.func)
                if callee in self.functions:
                    todo.append(callee)
                # Functions passed as values (simulate=simulate, protected=desktop_dependencies).
                for arg in list(call.args) + [k.value for k in call.keywords]:
                    if isinstance(arg, ast.Name) and arg.id in self.functions:
                        todo.append(arg.id)
            for default in self.functions[name].args.defaults:
                if isinstance(default, ast.Name) and default.id in self.functions:
                    todo.append(default.id)
        return order

    def sinks(self, function_name):
        found = []
        for call in self.calls_in(self.functions[function_name]):
            callee = dotted(call.func)
            if callee in PROGRAM_CALLS or self.wrappers.get(callee) == "program":
                wrapper = self.functions.get(callee)
                if wrapper and wrapper.args.vararg and not wrapper.args.args:
                    # gpasswd(*args), ufw(*args): every argument is one argv item.
                    argv = classify_argv(ast.List(elts=call.args))
                    stdin = None
                else:
                    argv = classify_argv(call.args[0]) if call.args else []
                    stdin = next((ast.unparse(k.value) for k in call.keywords if k.arg == "input"), None)
                    if wrapper and len(call.args) > 1:
                        stdin = ast.unparse(call.args[1])
                found.append((call.lineno, "program", callee, argv, stdin))
            elif callee in FILE_CALLS or opens_for_writing(call) or self.wrappers.get(callee) == "file":
                content = call.args[1] if len(call.args) > 1 else None
                tag = "VAR" if callee in self.wrappers and content is not None and \
                    not isinstance(content, ast.Constant) else ""
                found.append((call.lineno, "file", callee, [(ast.unparse(a), tag) for a in call.args[:2]], None))
        return found


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    module = Module(sys.argv[1])
    only = sys.argv[2] if len(sys.argv) > 2 else None
    print("Wrappers (a parameter reaches a sink): " +
          ", ".join(f"{name} ({kind})" for name, kind in module.wrappers.items()))
    for verb, handler in module.verbs.items():
        if only and verb != only:
            continue
        start = handler
        if handler not in module.functions:
            # countme-helper: VERBS holds data, and main() does the work for every verb.
            start = "main"
            handler = f"{handler[:50]}... (data; following main())"
        print(f"\n### {verb}  ->  {handler}")
        by_function = collections.OrderedDict()
        for name in module.reachable(start):
            sinks = module.sinks(name)
            if sinks:
                by_function[name] = sinks
        if not by_function:
            print("  (no program or file sink reached)")
        for name, sinks in by_function.items():
            for line, kind, callee, argv, stdin in sinks:
                if kind == "program":
                    shown = " ".join(text if tag == "const" else f"<{text}>" for text, tag in argv)
                    extra = f"   stdin: <{stdin}>" if stdin else ""
                    variable = any(tag == "VAR" for _, tag in argv) or stdin
                    print(f"  {'!' if variable else ' '} {line:5} {name}: {callee}  [{shown}]{extra}")
                else:
                    mark = "~" if any(tag == "VAR" for _, tag in argv) else " "
                    print(f"  {mark} {line:5} {name}: {callee}  ({', '.join(t for t, _ in argv)})")
    print("\n! = a program gets an argument or stdin that is not a constant: trace where it comes from.")
    print("~ = a file is written with content built from data: trace what goes into it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
