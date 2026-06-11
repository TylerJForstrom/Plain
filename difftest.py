"""Differential test harness: every Plain program must produce identical
output and exit status under both engines (--engine=ast and --engine=vm).

Run:  python difftest.py

Covers tests.plain, demo.plain, every program in examples/, and a set of
inline corner cases aimed at error messages, line numbers, and control
flow that crosses function calls. Exits 1 on any mismatch.
"""

import io
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import plain  # noqa: E402


def run_one(path, engine, args=()):
    """Run a program through the real CLI path; return (stdout, exit_code)."""
    random.seed(12345)   # identical randomness for both engines
    old_argv = sys.argv
    old_stdout, old_stdin = sys.stdout, sys.stdin
    sys.argv = ["plain.py", path, f"--engine={engine}", *args]
    sys.stdout = io.StringIO()
    sys.stdin = io.StringIO("")
    code = 0
    try:
        plain.main()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
    except BaseException as e:   # uncaught = both engines must crash alike
        print(f"<uncaught {type(e).__name__}: {e}>")
        code = "crash"
    finally:
        out = sys.stdout.getvalue()
        sys.argv = old_argv
        sys.stdout, sys.stdin = old_stdout, old_stdin
        plain.TRACE["on"] = False
    return out, code


# Corner cases the example programs don't reach: exact error text and
# line numbers, try/otherwise, stop/skip across function calls, etc.
EXTRA_CASES = {
    "error_line_numbers": 'set a to 5\nprint a + "x" + 1\n',
    "divide_by_zero": 'set a to 1\nprint a / 0\n',
    "unset_variable": 'print total\n',
    "index_out_of_range": 'set xs to [1, 2, 3]\nprint item 9 of xs\n',
    "missing_lookup_key": 'set d to {"a": 1}\nprint d at "b"\n',
    "try_otherwise": (
        'try\n    print 1 / 0\notherwise\n    print "caught: [error]"\nend\n'
        'print "after"\n'
    ),
    "try_error_in_function": (
        'to boom\n    print 1 / 0\nend\n'
        'try\n    call boom\notherwise\n    print "caught: [error]"\nend\n'
    ),
    "try_nested_loop_error": (
        'try\n    for each i from 1 to 5\n        if i is 3 then\n'
        '            print missing\n        end\n        print i\n    end\n'
        'otherwise\n    print "caught: [error]"\nend\n'
    ),
    "stop_skip_basic": (
        'for each i from 1 to 10\n    if i is 3 then\n        skip\n    end\n'
        '    if i is 6 then\n        stop\n    end\n    print i\nend\n'
    ),
    "stop_inside_while": (
        'set i to 0\nwhile i is less than 10\n    add 1 to i\n'
        '    if i is 4 then\n        stop\n    end\nend\nprint i\n'
    ),
    "stop_crosses_function": (
        'to maybe_stop with n\n    if n is 3 then\n        stop\n    end\nend\n'
        'for each i from 1 to 6\n    call maybe_stop with i\n    print i\nend\n'
        'print "done"\n'
    ),
    "skip_crosses_function": (
        'to maybe_skip with n\n    if n is divisible by 2 then\n        skip\n    end\nend\n'
        'for each i from 1 to 6\n    call maybe_skip with i\n    print i\nend\n'
    ),
    "stop_through_try": (
        'for each i from 1 to 5\n    try\n        if i is 3 then\n'
        '            stop\n        end\n        print i\n    otherwise\n'
        '        print "never"\n    end\nend\nprint "out"\n'
    ),
    "multifor_skip_stop": (
        'for each r from 1 to 3 and c from 1 to 3\n'
        '    if c is 2 then\n        skip\n    end\n'
        '    if r is 3 then\n        stop\n    end\n    print "[r],[c]"\nend\n'
        'print "after"\n'
    ),
    "give_back_top_level": 'print "before"\ngive back 5\n',
    "give_back_multi": (
        'to bounds with xs\n    give back smallest in xs and biggest in xs\nend\n'
        'set lo and hi to call bounds with [4, 1, 9]\nprint "[lo] to [hi]"\n'
    ),
    "recursion_fib": (
        'to fib with n\n    if n is less than 2 then\n        give back n\n    end\n'
        '    give back (call fib with n minus 1) plus (call fib with n minus 2)\nend\n'
        'print call fib with 15\n'
    ),
    "function_param_restore": (
        'set x to "outer"\nto shadow with x\n    print x\nend\n'
        'call shadow with "inner"\nprint x\n'
    ),
    "wrong_arg_count": 'to f with a and b\n    give back a\nend\nprint call f with 1\n',
    "missing_function": 'call nothing with 1\n',
    "filter_map_sort": (
        'set nums to [5, 3, 8, 1, 9, 2]\n'
        'set big to only the ones in nums where it is greater than 3\n'
        'print big\nprint each n in nums as n multiplied by 10\n'
        'set pairs to [[1, "b"], [2, "a"]]\nsort pairs by it[2]\nprint pairs\n'
        'sort nums backwards\nprint nums\n'
    ),
    "filter_restores_it": (
        'set it to "mine"\nset evens to only the ones in [1,2,3,4] where it is even\n'
        'print evens\nprint it\n'
    ),
    "string_interp_loop": (
        'for each w in ["a", "b"]\n    print "got [w] and [missing]"\nend\n'
    ),
    "paths_and_grids": (
        'set g to grid of 2 by 2 filled with 0\ng[1][2] = 7\n'
        'set item 1 of item 2 of g to 9\nadd 1 to g[1][2]\n'
        'subtract 2 from g[2][1]\nprint g\n'
        'set d to empty lookup\nadd 1 to d at "k"\nadd 1 to d at "k"\nprint d at "k"\n'
    ),
    "swap_insert_remove": (
        'set xs to [1, 2, 3, 4]\nswap xs[1] and xs[4]\nprint xs\n'
        'insert 99 into xs at 2\nprint xs\nremove item 3 from xs into gone\n'
        'print gone\nremove the first from xs\nremove the last from xs into last\n'
        'print xs\nprint last\n'
    ),
    "sort_not_a_list": 'set x to 5\nsort x\n',
    "reverse_unset": 'reverse ghost\n',
    "setmulti_errors": 'set a and b to [1, 2, 3]\n',
    "expect_fail_exit": 'expect 1 plus 1 to equal 3\n',
    "exit_early": 'print "one"\nexit\nprint "never"\n',
    "repeat_forever": (
        'set n to 0\nforever\n    add 1 to n\n    if n is 3 then\n        stop\n    end\nend\n'
        'print n\nrepeat 2 times\n    print "hi"\nend\n'
    ),
    "while_cond_error_line": 'set s to "x"\nwhile s is less than 3\n    print s\nend\n',
    "deep_recursion": (
        'to down with n\n    if n is 0 then\n        give back 0\n    end\n'
        '    give back call down with n minus 1\nend\nprint call down with 200\n'
    ),
    "bools_and_logic": (
        'set t to true\nset f to false\nprint t\nprint t and f\nprint t or f\n'
        'print not t\nif (1 is less than 2) and ("ab" contains "a") then\n'
        '    print "yes"\nend\n'
    ),
    "conditions_grab_bag": (
        'set n to 7\nif n is between 1 and 10 then\n    print "in range"\nend\n'
        'if n is odd then\n    print "odd"\nend\n'
        'if n is one of [3, 5, 7] then\n    print "listed"\nend\n'
        'if "hello" starts with "he" then\n    print "starts"\nend\n'
        'if "hello" does not contain "z" then\n    print "no z"\nend\n'
        'if [] is empty then\n    print "empty"\nend\n'
        'if n is a number then\n    print "number"\nend\n'
    ),
    "string_builtins": (
        'set s to "  The Quick Fox  "\nprint trim of s\nprint uppercase of s\n'
        'print split "a,b,c" by ","\nprint join [1, 2, 3] with "-"\n'
        'print the first 2 of [9, 8, 7]\nprint items 2 to 3 of "abcd"\n'
        'print replace "a" with "o" in "banana"\nprint count of "n" in "banana"\n'
        'print position of "k" in "akc"\n'
    ),
    "for_variants": (
        'for each x in [10, 20, 30] going backwards\n    print x\nend\n'
        'for every other x in [1, 2, 3, 4, 5]\n    print x\nend\n'
        'for each ch at position i in "abc"\n    print "[i]: [ch]"\nend\n'
        'for each pair of a and b in [1, 4, 9]\n    print a plus b\nend\n'
        'for each n from 10 to 4 by 2\n    print n\nend\n'
    ),
}


def main():
    programs = [
        os.path.join(HERE, "tests.plain"),
        os.path.join(HERE, "demo.plain"),
    ]
    exdir = os.path.join(HERE, "examples")
    programs += [os.path.join(exdir, f) for f in sorted(os.listdir(exdir))
                 if f.endswith(".plain")]

    tmpdir = tempfile.mkdtemp(prefix="plain_difftest_")
    for name, src in EXTRA_CASES.items():
        p = os.path.join(tmpdir, name + ".plain")
        with open(p, "w", encoding="utf-8") as f:
            f.write(src)
        programs.append(p)

    failures = 0
    cwd = os.getcwd()
    os.chdir(HERE)   # demo.plain writes _demo_out.txt next to itself
    try:
        for path in programs:
            label = os.path.relpath(path, HERE) if path.startswith(HERE) \
                else os.path.basename(path)
            out_a, code_a = run_one(path, "ast")
            out_v, code_v = run_one(path, "vm")
            if out_a == out_v and code_a == code_v:
                print(f"  ok   {label}")
            else:
                failures += 1
                print(f"  DIFF {label}")
                if code_a != code_v:
                    print(f"       exit codes: ast={code_a} vm={code_v}")
                la, lv = out_a.splitlines(), out_v.splitlines()
                for i in range(max(len(la), len(lv))):
                    a = la[i] if i < len(la) else "<missing>"
                    v = lv[i] if i < len(lv) else "<missing>"
                    if a != v:
                        print(f"       line {i + 1}: ast={a!r}")
                        print(f"       line {i + 1}:  vm={v!r}")
    finally:
        os.chdir(cwd)

    total = len(programs)
    print(f"\n{total - failures}/{total} programs identical under both engines.")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
