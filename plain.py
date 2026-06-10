"""
Plain - an English-like programming language.

Run:  python plain.py program.plain
"""

import difflib
import math
import random
import re
import sys
import time


# ============================================================
# 1. TOKENIZER
# ============================================================

KEYWORDS = {
    # statements
    "set", "to", "add", "subtract", "from",
    "print", "ask",
    "if", "then", "otherwise", "end",
    "repeat", "times", "while", "forever",
    "for", "each", "every", "other", "in", "going", "backwards",
    "stop", "skip",
    "remove", "sort", "reverse",
    "give", "back", "call", "with",
    "wait", "seconds",
    "read", "lines", "into", "save",
    # conditions
    "is", "not", "equal", "greater", "less", "than", "one", "between",
    "divisible",
    # arithmetic
    "plus", "minus", "multiplied", "divided", "by",
    # values & list ops
    "list", "of", "and", "or", "empty",
    "true", "false",
    # built-ins
    "count", "length", "sum", "average", "biggest", "smallest",
    "random", "first", "last", "uppercase", "lowercase",
    "only", "the", "ones", "where", "it",
    "square", "root", "absolute", "value", "round",
    "split", "join",
}

TOKEN_RE = re.compile(
    r'"([^"]*)"'
    r'|(\d+(?:\.\d+)?)'
    r'|([A-Za-z_]\w*)'
    r'|(\n)'
    r'|([ \t]+|\#[^\n]*)'
)


def tokenize(src):
    toks = []
    for m in TOKEN_RE.finditer(src):
        s, num, word, nl, skip = m.groups()
        if skip is not None:
            continue
        if nl is not None:
            if toks and toks[-1][0] != "NL":
                toks.append(("NL", None))
            continue
        if s is not None:
            toks.append(("STR", s))
        elif num is not None:
            toks.append(("NUM", float(num) if "." in num else int(num)))
        elif word is not None:
            lw = word.lower()
            if lw in KEYWORDS:
                toks.append(("KW", lw))
            else:
                toks.append(("ID", word))
    toks.append(("EOF", None))
    return toks


# ============================================================
# 2. PARSER
# ============================================================

class Parser:
    def __init__(self, toks):
        self.t = toks
        self.i = 0

    def peek(self):
        return self.t[self.i]

    def eat(self):
        tok = self.t[self.i]
        self.i += 1
        return tok

    def accept(self, kind, val=None):
        tok = self.peek()
        if tok[0] == kind and (val is None or tok[1] == val):
            self.i += 1
            return tok
        return None

    def expect(self, kind, val=None):
        tok = self.accept(kind, val)
        if not tok:
            got = self.peek()[1] if self.peek()[1] is not None else self.peek()[0]
            raise SyntaxError(suggest(
                f"Expected '{val or kind}', got '{got}'", self.peek()))
        return tok

    def skip_nls(self):
        while self.accept("NL"):
            pass


def suggest(msg, tok):
    """Append a 'did you mean ...?' hint when the offending word is near a keyword."""
    if tok[0] == "ID":
        m = difflib.get_close_matches(tok[1].lower(), KEYWORDS, n=1, cutoff=0.7)
        if m:
            return f"{msg}. Did you mean '{m[0]}'?"
    return msg


def parse(tokens):
    p = Parser(tokens)
    p.skip_nls()
    stmts = []
    while p.peek()[0] != "EOF":
        stmts.append(parse_stmt(p))
        p.skip_nls()
    return ("block", stmts)


def parse_block(p, enders):
    body = []
    p.skip_nls()
    while p.peek() not in [("KW", e) for e in enders]:
        if p.peek()[0] == "EOF":
            raise SyntaxError(f"Reached end of file looking for {' or '.join(enders)}")
        body.append(parse_stmt(p))
        p.skip_nls()
    return body


def parse_stmt(p):
    tok = p.peek()

    if tok == ("KW", "set"):
        p.eat()
        name = p.expect("ID")[1]
        p.expect("KW", "to")
        return ("set", name, parse_expr(p))

    if tok == ("KW", "add"):
        p.eat()
        e = parse_expr(p)
        p.expect("KW", "to")
        return ("add", p.expect("ID")[1], e)

    if tok == ("KW", "subtract"):
        p.eat()
        e = parse_expr(p)
        p.expect("KW", "from")
        return ("sub", p.expect("ID")[1], e)

    if tok == ("KW", "remove"):
        p.eat()
        e = parse_expr(p)
        p.expect("KW", "from")
        return ("remove", p.expect("ID")[1], e)

    if tok == ("KW", "sort"):
        p.eat()
        return ("sort", p.expect("ID")[1])

    if tok == ("KW", "reverse"):
        p.eat()
        return ("reverse", p.expect("ID")[1])

    if tok == ("KW", "print"):
        p.eat()
        return ("print", parse_expr(p))

    if tok == ("KW", "ask"):
        p.eat()
        return ("ask", p.expect("ID")[1])

    if tok == ("KW", "wait"):
        p.eat()
        n = parse_expr(p)
        p.expect("KW", "seconds")
        return ("wait", n)

    if tok == ("KW", "stop"):
        p.eat()
        return ("stop",)

    if tok == ("KW", "skip"):
        p.eat()
        return ("skip",)

    if tok == ("KW", "give"):
        p.eat()
        p.expect("KW", "back")
        return ("return", parse_expr(p))

    if tok == ("KW", "call"):
        # Function call as a standalone statement: just evaluate and discard.
        return ("exprstmt", parse_expr(p))

    if tok == ("KW", "to"):
        p.eat()
        name = p.expect("ID")[1]
        params = []
        if p.accept("KW", "with"):
            params.append(p.expect("ID")[1])
            while p.accept("KW", "and"):
                params.append(p.expect("ID")[1])
        body = parse_block(p, ["end"])
        p.expect("KW", "end")
        return ("def", name, params, body)

    if tok == ("KW", "if"):
        p.eat()
        cond = parse_cond(p)
        p.expect("KW", "then")
        body = parse_block(p, ["end", "otherwise"])
        else_body = []
        if p.accept("KW", "otherwise"):
            else_body = parse_block(p, ["end"])
        p.expect("KW", "end")
        return ("if", cond, body, else_body)

    if tok == ("KW", "repeat"):
        p.eat()
        n = parse_expr(p)
        p.expect("KW", "times")
        body = parse_block(p, ["end"])
        p.expect("KW", "end")
        return ("repeat", n, body)

    if tok == ("KW", "while"):
        p.eat()
        cond = parse_cond(p)
        body = parse_block(p, ["end"])
        p.expect("KW", "end")
        return ("while", cond, body)

    if tok == ("KW", "forever"):
        p.eat()
        body = parse_block(p, ["end"])
        p.expect("KW", "end")
        return ("forever", body)

    if tok == ("KW", "for"):
        p.eat()
        if p.accept("KW", "each"):
            step = 1
        elif p.accept("KW", "every"):
            p.expect("KW", "other")
            step = 2
        else:
            raise SyntaxError("Expected 'each' or 'every other' after 'for'")
        name = p.expect("ID")[1]
        if p.accept("KW", "from"):
            start = parse_expr(p)
            p.expect("KW", "to")
            stop = parse_expr(p)
            step_expr = ("num", 1)
            if p.accept("KW", "by"):
                step_expr = parse_expr(p)
            body = parse_block(p, ["end"])
            p.expect("KW", "end")
            return ("rangefor", name, start, stop, step_expr, body)
        p.expect("KW", "in")
        seq = parse_expr(p)
        backwards = bool(p.accept("KW", "going"))
        if backwards:
            p.expect("KW", "backwards")
        body = parse_block(p, ["end"])
        p.expect("KW", "end")
        return ("for", name, seq, step, backwards, body)

    if tok == ("KW", "read"):
        p.eat()
        p.expect("KW", "lines")
        p.expect("KW", "from")
        path = parse_expr(p)
        p.expect("KW", "into")
        return ("readlines", p.expect("ID")[1], path)

    if tok == ("KW", "save"):
        p.eat()
        val = parse_expr(p)
        p.expect("KW", "to")
        path = parse_expr(p)
        return ("save", val, path)

    raise SyntaxError(suggest(f"I don't understand '{tok[1] or tok[0]}'", tok))


# ---------- Conditions ----------

def parse_cond(p):
    left = parse_cmp(p)
    while True:
        if p.accept("KW", "and"):
            left = ("logic", "and", left, parse_cmp(p))
        elif p.accept("KW", "or"):
            left = ("logic", "or", left, parse_cmp(p))
        else:
            return left


def parse_cmp(p):
    left = parse_expr(p)
    p.expect("KW", "is")
    negate = bool(p.accept("KW", "not"))
    if p.accept("KW", "equal"):
        p.expect("KW", "to")
        node = ("cmp", "eq", left, parse_expr(p))
    elif p.accept("KW", "greater"):
        p.expect("KW", "than")
        node = ("cmp", "gt", left, parse_expr(p))
    elif p.accept("KW", "less"):
        p.expect("KW", "than")
        node = ("cmp", "lt", left, parse_expr(p))
    elif p.accept("KW", "one"):
        p.expect("KW", "of")
        node = ("member", left, parse_atom(p))
    elif p.accept("KW", "between"):
        lo = parse_atom(p)
        p.expect("KW", "and")
        hi = parse_atom(p)
        node = ("between", left, lo, hi)
    elif p.accept("KW", "divisible"):
        p.expect("KW", "by")
        node = ("divisible", left, parse_atom(p))
    else:
        raise SyntaxError(
            "Expected 'equal to', 'greater/less than', 'one of', or 'between'"
        )
    return ("logic", "not", node, None) if negate else node


# ---------- Expressions ----------

def parse_expr(p):
    left = parse_term(p)
    while True:
        if p.accept("KW", "plus"):
            left = ("bin", "+", left, parse_term(p))
        elif p.accept("KW", "minus"):
            left = ("bin", "-", left, parse_term(p))
        else:
            return left


def parse_term(p):
    left = parse_atom(p)
    while True:
        if p.accept("KW", "multiplied"):
            p.expect("KW", "by")
            left = ("bin", "*", left, parse_atom(p))
        elif p.accept("KW", "divided"):
            p.expect("KW", "by")
            left = ("bin", "/", left, parse_atom(p))
        else:
            return left


# One-argument built-in expressions: (keyword, internal-name, separator-keyword)
UNARY_BUILTINS = [
    ("count",     "count",     "of"),
    ("length",    "count",     "of"),
    ("sum",       "sum",       "of"),
    ("average",   "average",   "of"),
    ("biggest",   "max",       "in"),
    ("smallest",  "min",       "in"),
    ("first",     "first",     "of"),
    ("last",      "last",      "of"),
    ("uppercase", "uppercase", "of"),
    ("lowercase", "lowercase", "of"),
]


def parse_atom(p):
    # list literals
    if p.accept("KW", "list"):
        p.expect("KW", "of")
        items = [parse_atom(p)]
        while p.accept("KW", "and"):
            items.append(parse_atom(p))
        return ("list", items)
    if p.accept("KW", "empty"):
        p.expect("KW", "list")
        return ("list", [])

    # one-argument built-ins
    for kw, fn, sep in UNARY_BUILTINS:
        if p.accept("KW", kw):
            p.expect("KW", sep)
            return ("call", fn, [parse_atom(p)])

    # random
    if p.accept("KW", "random"):
        if p.accept("KW", "from"):
            a = parse_atom(p)
            p.expect("KW", "to")
            b = parse_atom(p)
            return ("call", "randnum", [a, b])
        p.expect("KW", "in")
        return ("call", "randitem", [parse_atom(p)])

    # math
    if p.accept("KW", "square"):
        p.expect("KW", "root")
        p.expect("KW", "of")
        return ("call", "sqrt", [parse_atom(p)])
    if p.accept("KW", "absolute"):
        p.expect("KW", "value")
        p.expect("KW", "of")
        return ("call", "abs", [parse_atom(p)])
    if p.accept("KW", "round"):
        p.accept("KW", "of")  # optional 'of'
        return ("call", "round", [parse_atom(p)])

    # string split / join
    if p.accept("KW", "split"):
        s = parse_atom(p)
        p.expect("KW", "by")
        sep = parse_atom(p)
        return ("call", "split", [s, sep])
    if p.accept("KW", "join"):
        lst = parse_atom(p)
        p.expect("KW", "with")
        sep = parse_atom(p)
        return ("call", "join", [lst, sep])

    # filter: "only the ones in LIST where COND"
    if p.accept("KW", "only"):
        p.expect("KW", "the")
        p.expect("KW", "ones")
        p.expect("KW", "in")
        src = parse_atom(p)
        p.expect("KW", "where")
        cond = parse_cond(p)
        return ("filter", src, cond)

    # function call as an expression: "call NAME with X and Y"
    if p.accept("KW", "call"):
        name = p.expect("ID")[1]
        args = []
        if p.accept("KW", "with"):
            args.append(parse_atom(p))
            while p.accept("KW", "and"):
                args.append(parse_atom(p))
        return ("userfn", name, args)

    # 'it' is the implicit element inside a filter
    if p.accept("KW", "it"):
        return ("var", "it")

    tok = p.eat()
    if tok[0] == "NUM": return ("num", tok[1])
    if tok[0] == "STR": return ("str", tok[1])
    if tok[0] == "ID":  return ("var", tok[1])
    if tok == ("KW", "true"):  return ("num", 1)
    if tok == ("KW", "false"): return ("num", 0)
    raise SyntaxError(suggest(f"Expected a value, got '{tok[1] or tok[0]}'", tok))


# ============================================================
# 3. INTERPRETER
# ============================================================

INTERP_RE = re.compile(r'\[(\w+)\]')


class StopLoop(Exception):
    pass


class SkipLoop(Exception):
    pass


class ReturnValue(Exception):
    def __init__(self, value):
        self.value = value


def to_str(v):
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def add_vals(a, b):
    if isinstance(a, str) or isinstance(b, str):
        return to_str(a) + to_str(b)
    return a + b


def evaluate(node, env):
    t = node[0]
    if t == "num":
        return node[1]
    if t == "str":
        return INTERP_RE.sub(
            lambda m: to_str(env[m.group(1)]) if m.group(1) in env else m.group(0),
            node[1],
        )
    if t == "var":
        if node[1] not in env:
            raise NameError(f"You haven't set '{node[1]}' yet.")
        return env[node[1]]
    if t == "bin":
        _, op, a, b = node
        av, bv = evaluate(a, env), evaluate(b, env)
        if op == "+": return add_vals(av, bv)
        if op == "-": return av - bv
        if op == "*": return av * bv
        if op == "/": return av / bv
    if t == "cmp":
        _, op, a, b = node
        av, bv = evaluate(a, env), evaluate(b, env)
        return {"eq": av == bv, "gt": av > bv, "lt": av < bv}[op]
    if t == "member":
        return evaluate(node[1], env) in evaluate(node[2], env)
    if t == "between":
        v = evaluate(node[1], env)
        lo = evaluate(node[2], env)
        hi = evaluate(node[3], env)
        return lo <= v <= hi
    if t == "divisible":
        return evaluate(node[1], env) % evaluate(node[2], env) == 0
    if t == "logic":
        _, op, a, b = node
        if op == "not": return not evaluate(a, env)
        if op == "and": return bool(evaluate(a, env)) and bool(evaluate(b, env))
        if op == "or":  return bool(evaluate(a, env)) or  bool(evaluate(b, env))
    if t == "list":
        return [evaluate(x, env) for x in node[1]]
    if t == "filter":
        src = evaluate(node[1], env)
        cond = node[2]
        result = []
        had = "it" in env
        saved = env.get("it")
        try:
            for x in src:
                env["it"] = x
                if evaluate(cond, env):
                    result.append(x)
        finally:
            if had:
                env["it"] = saved
            else:
                env.pop("it", None)
        return result
    if t == "call":
        _, name, args = node
        vals = [evaluate(a, env) for a in args]
        x = vals[0] if vals else None
        if name == "count":     return len(x)
        if name == "sum":       return sum(x)
        if name == "average":   return sum(x) / len(x)
        if name == "max":       return max(x)
        if name == "min":       return min(x)
        if name == "first":     return x[0]
        if name == "last":      return x[-1]
        if name == "uppercase": return str(x).upper()
        if name == "lowercase": return str(x).lower()
        if name == "randnum":   return random.randint(int(vals[0]), int(vals[1]))
        if name == "randitem":  return random.choice(x)
        if name == "sqrt":      return math.sqrt(x)
        if name == "abs":       return abs(x)
        if name == "round":     return round(x)
        if name == "split":     return str(vals[0]).split(vals[1])
        if name == "join":      return str(vals[1]).join(to_str(v) for v in vals[0])
    if t == "userfn":
        return call_user_fn(node[1], [evaluate(a, env) for a in node[2]], env)
    raise RuntimeError(f"Cannot evaluate {node}")


def call_user_fn(name, args, env):
    fns = env.setdefault("__fns__", {})
    if name not in fns:
        raise NameError(f"No function named '{name}'.")
    params, body = fns[name]
    if len(args) != len(params):
        raise RuntimeError(
            f"'{name}' wants {len(params)} value(s), got {len(args)}."
        )
    saved = {k: env[k] for k in params if k in env}
    for k, v in zip(params, args):
        env[k] = v
    try:
        for s in body:
            run(s, env)
        return None
    except ReturnValue as r:
        return r.value
    finally:
        for k in params:
            if k in saved:
                env[k] = saved[k]
            else:
                env.pop(k, None)


def run(node, env):
    t = node[0]
    if t == "block":
        for s in node[1]:
            run(s, env)
    elif t == "set":
        env[node[1]] = evaluate(node[2], env)
    elif t == "add":
        cur = env.get(node[1], 0)
        v = evaluate(node[2], env)
        if isinstance(cur, list):
            cur.append(v)
        else:
            env[node[1]] = add_vals(cur, v)
    elif t == "sub":
        env[node[1]] = env.get(node[1], 0) - evaluate(node[2], env)
    elif t == "remove":
        v = evaluate(node[2], env)
        lst = env.get(node[1])
        if isinstance(lst, list) and v in lst:
            lst.remove(v)
    elif t == "sort":
        env[node[1]].sort()
    elif t == "reverse":
        env[node[1]].reverse()
    elif t == "print":
        print(to_str(evaluate(node[1], env)))
    elif t == "ask":
        env[node[1]] = coerce(input("> "))
    elif t == "wait":
        time.sleep(float(evaluate(node[1], env)))
    elif t == "if":
        _, cond, body, else_body = node
        for s in (body if evaluate(cond, env) else else_body):
            run(s, env)
    elif t == "repeat":
        for _ in range(int(evaluate(node[1], env))):
            try:
                for s in node[2]:
                    run(s, env)
            except SkipLoop:
                continue
            except StopLoop:
                break
    elif t == "while":
        while evaluate(node[1], env):
            try:
                for s in node[2]:
                    run(s, env)
            except SkipLoop:
                continue
            except StopLoop:
                break
    elif t == "forever":
        while True:
            try:
                for s in node[1]:
                    run(s, env)
            except SkipLoop:
                continue
            except StopLoop:
                break
    elif t == "for":
        _, name, seq_node, step, backwards, body = node
        seq = list(evaluate(seq_node, env))
        if backwards:
            seq = seq[::-1]
        for item in seq[::step]:
            env[name] = item
            try:
                for s in body:
                    run(s, env)
            except SkipLoop:
                continue
            except StopLoop:
                break
    elif t == "rangefor":
        _, name, start_n, stop_n, step_n, body = node
        start = int(evaluate(start_n, env))
        stop = int(evaluate(stop_n, env))
        step = int(evaluate(step_n, env))
        direction = 1 if stop >= start else -1
        v = start
        while (direction > 0 and v <= stop) or (direction < 0 and v >= stop):
            env[name] = v
            try:
                for s in body:
                    run(s, env)
            except SkipLoop:
                pass
            except StopLoop:
                break
            v += direction * step
    elif t == "readlines":
        path = evaluate(node[2], env)
        with open(path, "r", encoding="utf-8") as f:
            env[node[1]] = [line.rstrip("\n") for line in f]
    elif t == "save":
        val = evaluate(node[1], env)
        path = evaluate(node[2], env)
        with open(path, "w", encoding="utf-8") as f:
            if isinstance(val, list):
                f.write("\n".join(to_str(x) for x in val))
            else:
                f.write(to_str(val))
    elif t == "def":
        _, name, params, body = node
        env.setdefault("__fns__", {})[name] = (params, body)
    elif t == "exprstmt":
        evaluate(node[1], env)
    elif t == "stop":
        raise StopLoop()
    elif t == "skip":
        raise SkipLoop()
    elif t == "return":
        raise ReturnValue(evaluate(node[1], env))


def coerce(s):
    s = s.strip()
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


# ============================================================
# 4. ENTRY POINT
# ============================================================

def repl():
    print("Plain REPL. Ctrl+C or Ctrl+Z then Enter to quit.")
    env = {}
    buf = ""
    prompt = ">>> "
    while True:
        try:
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            return
        buf += line + "\n"
        if not buf.strip():
            buf = ""
            continue
        try:
            ast = parse(tokenize(buf))
        except SyntaxError as e:
            msg = str(e)
            if "Reached end of file" in msg or "'EOF'" in msg:
                prompt = "... "
                continue
            print(f"Oops: {e}")
            buf = ""
            prompt = ">>> "
            continue
        prompt = ">>> "
        try:
            run(ast, env)
        except (NameError, RuntimeError, ZeroDivisionError) as e:
            print(f"Oops: {e}")
        buf = ""


def main():
    if len(sys.argv) < 2:
        repl()
        return
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        src = f.read()
    try:
        run(parse(tokenize(src)), {})
    except (SyntaxError, NameError, RuntimeError) as e:
        print(f"Oops: {e}")


if __name__ == "__main__":
    main()
