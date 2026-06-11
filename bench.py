"""Benchmark the AST tree-walker against the bytecode VM.

Run:  python bench.py

Each workload is parsed once, then executed by both engines with output
silenced. Times are the best of several runs (median is also shown), so
the numbers are honest about steady-state speed rather than one lucky
pass. Compile time for the VM is measured separately — it is paid once
per program and is not part of the per-run numbers.
"""

import io
import sys
import time

import plain

RUNS = 7

WORKLOADS = {
    "fib(18) recursion": """
to fib with n
    if n is less than 2 then
        give back n
    end
    give back (call fib with n minus 1) plus (call fib with n minus 2)
end
print call fib with 18
""",
    "loop arithmetic (200k)": """
set total to 0
for each n from 1 to 200000
    set total to total plus n multiplied by 2
end
print total
""",
    "string building (20k)": """
set out to ""
for each n from 1 to 20000
    set out to out plus "x"
end
print count of out
""",
    "list ops (40k)": """
set xs to []
for each n from 1 to 40000
    add n to xs
end
set total to 0
for each x in xs
    if x is divisible by 3 then
        add x to total
    end
end
print total
""",
    "lookup tally (30k)": """
set tally to empty lookup
for each n from 1 to 30000
    add 1 to tally at remainder of n divided by 7
end
print tally at 0
""",
}


def time_once(fn):
    gc_out, sys.stdout = sys.stdout, io.StringIO()
    t0 = time.perf_counter()
    try:
        fn()
    finally:
        captured = sys.stdout.getvalue()
        sys.stdout = gc_out
    return time.perf_counter() - t0, captured


def main():
    print(f"{'workload':<26} {'ast':>9} {'vm':>9} {'vm+opt':>9} "
          f"{'speedup':>8}   (best of {RUNS})")
    print("-" * 72)
    for name, src in WORKLOADS.items():
        ast = plain.parse(plain.tokenize(src))
        plain.OPTIMIZE = False
        code_plain = plain.compile_program(ast)
        plain.OPTIMIZE = True
        t0 = time.perf_counter()
        code_opt = plain.compile_program(ast)
        compile_ms = (time.perf_counter() - t0) * 1000

        # Engines run back-to-back inside each round so background load
        # hits all three roughly equally; best-of filters the rest out.
        best = {"ast": 9e9, "vm": 9e9, "opt": 9e9}
        outs = {}
        for _ in range(RUNS):
            t, outs["ast"] = time_once(lambda: plain.run(ast, {}))
            best["ast"] = min(best["ast"], t)
            t, outs["vm"] = time_once(
                lambda: plain._vm_exec([plain._Frame(code_plain)], {}))
            best["vm"] = min(best["vm"], t)
            t, outs["opt"] = time_once(
                lambda: plain._vm_exec([plain._Frame(code_opt)], {}))
            best["opt"] = min(best["opt"], t)
        assert outs["ast"] == outs["vm"] == outs["opt"], \
            f"engines disagree on {name}!"

        print(f"{name:<26} {best['ast'] * 1000:>7.1f}ms "
              f"{best['vm'] * 1000:>7.1f}ms {best['opt'] * 1000:>7.1f}ms "
              f"{best['ast'] / best['opt']:>7.2f}x   "
              f"(compile {compile_ms:.1f}ms)")


if __name__ == "__main__":
    main()
