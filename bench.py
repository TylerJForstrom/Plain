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

RUNS = 5

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


def time_runs(fn):
    times = []
    for _ in range(RUNS):
        gc_out, sys.stdout = sys.stdout, io.StringIO()
        t0 = time.perf_counter()
        try:
            fn()
        finally:
            captured = sys.stdout.getvalue()
            sys.stdout = gc_out
        times.append(time.perf_counter() - t0)
    times.sort()
    return times[0], times[len(times) // 2], captured


def main():
    print(f"{'workload':<26} {'ast':>9} {'vm':>9} {'speedup':>8}   (best of {RUNS})")
    print("-" * 60)
    for name, src in WORKLOADS.items():
        ast = plain.parse(plain.tokenize(src))
        t0 = time.perf_counter()
        code = plain.compile_program(ast)
        compile_ms = (time.perf_counter() - t0) * 1000

        best_a, _, out_a = time_runs(lambda: plain.run(ast, {}))
        best_v, _, out_v = time_runs(
            lambda: plain._vm_exec([plain._Frame(code)], {}))
        assert out_a == out_v, f"engines disagree on {name}!"

        print(f"{name:<26} {best_a * 1000:>7.1f}ms {best_v * 1000:>7.1f}ms "
              f"{best_a / best_v:>7.2f}x   (compile {compile_ms:.1f}ms)")


if __name__ == "__main__":
    main()
