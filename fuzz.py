"""Differential fuzzer: generate random valid Plain programs and require
the AST interpreter and the bytecode VM to produce identical output.

Run:  python fuzz.py              (400 programs)
      python fuzz.py --n 2000     (more)
      python fuzz.py --seed 7     (different base seed)

Programs are valid by construction and guaranteed to terminate: every
loop is bounded (small constant ranges, while-loops always start with
their own counter increment) and functions only call functions defined
before them, so there is no recursion. Runtime errors are allowed and
useful — the error text and the line number must match across engines
too. Any divergence is saved to fuzz_failures/ for replay.
"""

import argparse
import io
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import plain  # noqa: E402

NUM_BIN = ["plus", "minus", "*", "/", "//"]
WORDS = ["apple", "bear", "cat", "drum", "echo", "fox", "gem", "hat"]
SEPS = [",", "-", " "]


class Gen:
    """Builds one random program. Tracks variables by kind so most code
    is well-typed, while indexes and division still misfire sometimes —
    error paths are part of what we are comparing."""

    def __init__(self, rng):
        self.r = rng
        self.vars = {"num": [], "str": [], "list": [], "dict": []}
        self.fns = []          # (name, arity), defined before use
        self.counter = 0
        self.lines = []

    def name(self, prefix):
        self.counter += 1
        return f"{prefix}{self.counter}"

    def pick(self, kind):
        return self.r.choice(self.vars[kind]) if self.vars[kind] else None

    # ---- expressions ----

    def num_expr(self, d=0):
        r = self.r
        opts = ["lit", "lit"]
        if self.vars["num"]:
            opts += ["var", "var", "var"]
        if self.vars["list"]:
            opts += ["agg", "item"]
        if self.vars["str"]:
            opts.append("strlen")
        if d < 2:
            opts += ["bin", "bin", "unary"]
        if self.fns and d < 2:
            opts.append("call")
        k = r.choice(opts)
        if k == "var":
            return self.pick("num")
        if k == "bin":
            op = r.choice(NUM_BIN)
            if op == "*":
                # Multiply only by small literals. var * var inside a loop
                # squares the value every iteration, and a few dozen
                # squarings of a bignum is effectively a hang.
                return f"({self.num_expr(d + 1)} * {r.randint(0, 4)})"
            return f"({self.num_expr(d + 1)} {op} {self.num_expr(d + 1)})"
        if k == "unary":
            inner = self.num_expr(d + 1)
            return r.choice([
                f"absolute value of ({inner})",
                f"floor of ({inner})",
                f"middle of ({inner}) and ({self.num_expr(d + 1)})",
                f"remainder of ({inner}) divided by {r.randint(1, 7)}",
            ])
        if k == "agg":
            lst = self.pick("list")
            return r.choice([
                f"sum of {lst}", f"count of {lst}",
                f"biggest in {lst}", f"smallest in {lst}",
                f"first of {lst}", f"last of {lst}",
            ])
        if k == "item":
            lst = self.pick("list")
            return f"item {r.randint(1, 5)} of {lst}"   # sometimes out of range
        if k == "strlen":
            return f"count of {self.pick('str')}"
        if k == "call":
            fname, arity = r.choice(self.fns)
            args = " and ".join(self.num_expr(2) for _ in range(arity))
            return f"(call {fname}{' with ' + args if arity else ''})"
        return str(r.choice([0, 1, 2, 3, 4, 5, 7, 10, -2, 2.5]))

    def str_expr(self, d=0):
        r = self.r
        opts = ["lit", "lit", "interp"]
        if self.vars["str"]:
            opts += ["var", "var", "method"]
        if self.vars["list"]:
            opts.append("join")
        k = r.choice(opts)
        if k == "var":
            return self.pick("str")
        if k == "interp":
            names = [v for pool in self.vars.values() for v in pool]
            if names:
                return f'"{r.choice(WORDS)} [{r.choice(names)}]"'
            k = "lit"
        if k == "method":
            s = self.pick("str")
            return r.choice([
                f"uppercase of {s}", f"lowercase of {s}", f"trim of {s}",
                f'replace "{r.choice("aeo"):s}" with "{r.choice("xyz"):s}" in {s}',
            ])
        if k == "join":
            return f'join {self.pick("list")} with "{r.choice(SEPS)}"'
        return f'"{r.choice(WORDS)}"'

    def list_expr(self):
        r = self.r
        k = r.choice(["lit", "lit", "range", "split", "letters", "mapfil"])
        if k == "range":
            a = r.randint(1, 4)
            return f"numbers from {a} to {a + r.randint(0, 5)}"
        if k == "split" and self.vars["str"]:
            return f'split {self.pick("str")} by "{r.choice(SEPS)}"'
        if k == "letters":
            return f'letters of "{r.choice(WORDS)}"'
        if k == "mapfil" and self.vars["list"]:
            src = self.pick("list")
            v = self.name("mv")
            return r.choice([
                f"each {v} in {src} as {v} * {r.randint(2, 4)}",
                f"only the ones in {src} where it is "
                + r.choice(["even", "odd", f"greater than {r.randint(1, 6)}"]),
                f"the first {r.randint(1, 3)} of {src}",
            ])
        items = ", ".join(str(r.randint(-3, 9)) for _ in range(r.randint(1, 5)))
        return f"[{items}]"

    def any_expr(self):
        kind = self.r.choice(["num", "num", "num", "str", "list"])
        return getattr(self, kind + "_expr")() if kind != "list" else self.list_expr()

    def cond(self, d=0):
        r = self.r
        opts = ["cmp", "cmp", "cmp", "word"]
        if self.vars["list"]:
            opts += ["member", "empty"]
        if self.vars["str"]:
            opts.append("strcheck")
        if self.vars["dict"]:
            opts.append("has")
        if d < 1:
            opts += ["logic", "not"]
        k = r.choice(opts)
        if k == "cmp":
            op = r.choice(["is equal to", "is not equal to", "is less than",
                           "is greater than", "is at least", "is at most",
                           "<", ">", "==", "!="])
            return f"{self.num_expr(1)} {op} {self.num_expr(1)}"
        if k == "word":
            n = self.num_expr(1)
            return r.choice([
                f"{n} is even", f"{n} is odd",
                f"{n} is divisible by {r.randint(1, 5)}",
                f"{n} is between {r.randint(0, 3)} and {r.randint(4, 9)}",
                f"{n} is positive", f"{n} is a number",
                f"{n} is one of [1, 2, 3]",
            ])
        if k == "member":
            return f"{self.pick('list')} contains {self.r.randint(0, 6)}"
        if k == "empty":
            return f"{self.pick('list')} is empty"
        if k == "strcheck":
            s = self.pick("str")
            return r.choice([
                f'{s} contains "{r.choice("aeio")}"',
                f'{s} starts with "{r.choice("abc")}"',
                f'{s} does not contain "z"',
            ])
        if k == "has":
            return f'{self.pick("dict")} has "{r.choice(WORDS)}"'
        if k == "logic":
            joiner = r.choice(["and", "or"])
            return f"({self.cond(d + 1)}) {joiner} ({self.cond(d + 1)})"
        return f"not ({self.cond(d + 1)})"

    # ---- statements ----

    def emit(self, indent, text):
        self.lines.append("    " * indent + text)

    def assign(self, indent):
        r = self.r
        kind = r.choice(["num", "num", "str", "list", "dict"])
        if self.vars[kind] and r.random() < 0.5:
            v = self.pick(kind)          # reassign, keeping the kind
        else:
            v = self.name({"num": "n", "str": "s", "list": "xs", "dict": "d"}[kind])
        if kind == "num":
            self.emit(indent, f"set {v} to {self.num_expr()}")
        elif kind == "str":
            self.emit(indent, f"set {v} to {self.str_expr()}")
        elif kind == "list":
            self.emit(indent, f"set {v} to {self.list_expr()}")
        else:
            self.emit(indent, f"set {v} to {{}}")
        if v not in self.vars[kind]:
            self.vars[kind].append(v)

    def stmt(self, indent, depth, in_loop):
        r = self.r
        opts = ["assign", "assign", "print"]
        if self.vars["num"]:
            opts += ["addsub", "addsub"]
        if self.vars["list"]:
            opts += ["listop", "listop", "foreach"]
        if self.vars["dict"]:
            opts += ["dictop", "dictop"]
        if depth < 2:
            opts += ["if", "if", "forrange", "repeat", "while", "try", "multifor"]
        if in_loop:
            opts += ["stopskip"]
        if self.fns:
            opts.append("callstmt")
        k = r.choice(opts)

        if k == "assign":
            self.assign(indent)
        elif k == "print":
            self.emit(indent, f"print {self.any_expr()}")
        elif k == "addsub":
            v = self.pick("num")
            verb = r.choice([f"add {self.num_expr(1)} to {v}",
                             f"subtract {self.num_expr(1)} from {v}"])
            self.emit(indent, verb)
        elif k == "listop":
            v = self.pick("list")
            self.emit(indent, r.choice([
                f"add {r.randint(0, 9)} to {v}",
                f"sort {v}",
                f"sort {v} backwards",
                f"reverse {v}",
                f"insert {r.randint(0, 9)} into {v} at {r.randint(1, 4)}",
                f"remove item {r.randint(1, 4)} from {v}",
                f"remove the first from {v}",
                f"{v}[{r.randint(1, 4)}] = {self.num_expr(1)}",
            ]))
        elif k == "dictop":
            v = self.pick("dict")
            key = r.choice(WORDS)
            self.emit(indent, r.choice([
                f'set {v} at "{key}" to {self.num_expr(1)}',
                f'add 1 to {v} at "{key}"',
                f'print keys of {v}',
            ]))
        elif k == "if":
            self.emit(indent, f"if {self.cond()} then")
            self.block(indent + 1, depth + 1, in_loop, r.randint(1, 2))
            if r.random() < 0.5:
                self.emit(indent, "otherwise")
                self.block(indent + 1, depth + 1, in_loop, r.randint(1, 2))
            self.emit(indent, "end")
        elif k == "forrange":
            v = self.name("i")
            a = r.randint(1, 3)
            spec = f"for each {v} from {a} to {a + r.randint(0, 4)}"
            if r.random() < 0.3:
                spec += f" by {r.randint(1, 2)}"
            self.emit(indent, spec)
            self.vars["num"].append(v)
            self.block(indent + 1, depth + 1, True, r.randint(1, 2))
            self.emit(indent, "end")
        elif k == "foreach":
            src = self.pick("list")
            v = self.name("e")
            extra = r.choice(["", "", " going backwards"])
            pos = ""
            if not extra and r.random() < 0.3:
                pos = f" at position {self.name('p')}"
            self.emit(indent, f"for each {v}{pos} in {src}{extra}")
            self.vars["num"].append(v)   # usually numbers; errors are fair game
            self.block(indent + 1, depth + 1, True, r.randint(1, 2))
            self.emit(indent, "end")
        elif k == "repeat":
            self.emit(indent, f"repeat {r.randint(1, 3)} times")
            self.block(indent + 1, depth + 1, True, r.randint(1, 2))
            self.emit(indent, "end")
        elif k == "while":
            # Bounded by construction: fresh counter, increment first, no
            # skip inside (in_loop=False below), and — crucially — the
            # counter is never added to the variable pool, so nothing in
            # the body can reset it and stall the loop.
            v = self.name("w")
            self.emit(indent, f"set {v} to 0")
            self.emit(indent, f"while {v} is less than {r.randint(1, 4)}")
            self.emit(indent + 1, f"add 1 to {v}")
            self.block(indent + 1, depth + 1, False, 1)
            self.emit(indent, "end")
        elif k == "multifor":
            a, b = self.name("i"), self.name("j")
            self.emit(indent, f"for each {a} from 1 to {r.randint(1, 3)} "
                              f"and {b} from 1 to {r.randint(1, 2)}")
            self.vars["num"] += [a, b]
            self.block(indent + 1, depth + 1, True, 1)
            self.emit(indent, "end")
        elif k == "try":
            self.emit(indent, "try")
            self.block(indent + 1, depth + 1, in_loop, r.randint(1, 2))
            self.emit(indent, "otherwise")
            self.emit(indent + 1, 'print "caught: [error]"')
            self.emit(indent, "end")
        elif k == "stopskip":
            word = r.choice(["stop", "skip"])
            self.emit(indent, f"if {self.cond()} then")
            self.emit(indent + 1, word)
            self.emit(indent, "end")
        elif k == "callstmt":
            fname, arity = r.choice(self.fns)
            args = " and ".join(self.num_expr(2) for _ in range(arity))
            self.emit(indent, f"call {fname}{' with ' + args if arity else ''}")

    def block(self, indent, depth, in_loop, n):
        for _ in range(n):
            self.stmt(indent, depth, in_loop)

    def function(self):
        r = self.r
        fname = self.name("f")
        arity = r.randint(0, 2)
        params = [self.name("a") for _ in range(arity)]
        head = f"to {fname}"
        if params:
            head += " with " + " and ".join(params)
        self.emit(0, head)
        saved_vars = {k: list(v) for k, v in self.vars.items()}
        self.vars["num"] += params
        self.block(1, 1, False, r.randint(1, 3))
        if r.random() < 0.7:
            self.emit(1, f"give back {self.num_expr(1)}")
        self.emit(0, "end")
        self.vars = saved_vars           # params are not visible outside
        self.fns.append((fname, arity))

    def program(self):
        r = self.r
        for _ in range(r.randint(0, 2)):
            self.function()
        # Seed a couple of variables so early statements have material.
        self.assign(0)
        self.assign(0)
        for _ in range(r.randint(4, 10)):
            self.stmt(0, 0, False)
        if r.random() < 0.2:
            self.emit(0, f"expect {self.num_expr(1)} to equal {self.num_expr(1)}")
        return "\n".join(self.lines) + "\n"


def run_engine(path, engine):
    random.seed(99991)   # runtime randomness identical for both engines
    old_argv, old_out, old_in = sys.argv, sys.stdout, sys.stdin
    sys.argv = ["plain.py", path, f"--engine={engine}"]
    sys.stdout = io.StringIO()
    sys.stdin = io.StringIO("")
    code = 0
    try:
        plain.main()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
    except BaseException as e:
        print(f"<uncaught {type(e).__name__}: {e}>")
        code = "crash"
    finally:
        out = sys.stdout.getvalue()
        sys.argv, sys.stdout, sys.stdin = old_argv, old_out, old_in
        plain.TRACE["on"] = False
    return out, code


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    faildir = os.path.join(HERE, "fuzz_failures")
    tmp = os.path.join(HERE, "_fuzz_current.plain")
    failures = 0
    for i in range(args.n):
        seed = args.seed * 1_000_000 + i
        src = Gen(random.Random(seed)).program()
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(src)
        out_a, code_a = run_engine(tmp, "ast")
        out_v, code_v = run_engine(tmp, "vm")
        if out_a != out_v or code_a != code_v:
            failures += 1
            os.makedirs(faildir, exist_ok=True)
            keep = os.path.join(faildir, f"seed_{seed}.plain")
            with open(keep, "w", encoding="utf-8") as f:
                f.write(src)
            print(f"DIVERGENCE at seed {seed} (saved to {keep})")
            if code_a != code_v:
                print(f"  exit codes: ast={code_a} vm={code_v}")
            la, lv = out_a.splitlines(), out_v.splitlines()
            for j in range(max(len(la), len(lv))):
                a = la[j] if j < len(la) else "<missing>"
                v = lv[j] if j < len(lv) else "<missing>"
                if a != v:
                    print(f"  line {j + 1}: ast={a!r}")
                    print(f"  line {j + 1}:  vm={v!r}")
                    break
    if os.path.exists(tmp):
        os.remove(tmp)
    print(f"\n{args.n - failures}/{args.n} random programs identical "
          f"under both engines.")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
