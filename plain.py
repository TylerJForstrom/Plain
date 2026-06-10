"""
Plain - a tiny English-like language.

Run:  python plain.py program.plain
"""

import random
import re
import sys


# ============================================================
# 1. TOKENIZER  -  turns source text into a list of tokens
# ============================================================

KEYWORDS = {
    "set", "to", "add", "subtract", "from",
    "print", "ask",
    "if", "then", "otherwise", "end",
    "repeat", "times", "while",
    "for", "each", "every", "other", "in", "going", "backwards",
    "is", "not", "equal", "greater", "less", "than",
    "plus", "minus", "multiplied", "divided", "by",
    "list", "of", "and", "empty",
    "count", "sum", "average", "biggest", "smallest",
    "random",
    "true", "false",
}

TOKEN_RE = re.compile(
    r'"([^"]*)"'          # string
    r'|(\d+(?:\.\d+)?)'   # number
    r'|([A-Za-z_]\w*)'    # word
    r'|(\n)'              # newline
    r'|([ \t]+|\#[^\n]*)' # whitespace / comments
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
# 2. PARSER  -  turns tokens into a tree (AST)
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
            raise SyntaxError(
                f"Expected {val or kind}, got {self.peek()[1] or self.peek()[0]}"
            )
        return tok

    def skip_nls(self):
        while self.accept("NL"):
            pass


def parse(tokens):
    p = Parser(tokens)
    p.skip_nls()
    stmts = []
    while p.peek()[0] != "EOF":
        stmts.append(parse_stmt(p))
        p.skip_nls()
    return ("block", stmts)


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

    if tok == ("KW", "print"):
        p.eat()
        return ("print", parse_expr(p))

    if tok == ("KW", "ask"):
        p.eat()
        return ("ask", p.expect("ID")[1])

    if tok == ("KW", "if"):
        p.eat()
        cond = parse_cond(p)
        p.expect("KW", "then")
        p.skip_nls()
        body = []
        while p.peek() not in (("KW", "end"), ("KW", "otherwise")):
            body.append(parse_stmt(p))
            p.skip_nls()
        else_body = []
        if p.accept("KW", "otherwise"):
            p.skip_nls()
            while p.peek() != ("KW", "end"):
                else_body.append(parse_stmt(p))
                p.skip_nls()
        p.expect("KW", "end")
        return ("if", cond, body, else_body)

    if tok == ("KW", "repeat"):
        p.eat()
        n = parse_expr(p)
        p.expect("KW", "times")
        p.skip_nls()
        body = []
        while p.peek() != ("KW", "end"):
            body.append(parse_stmt(p))
            p.skip_nls()
        p.expect("KW", "end")
        return ("repeat", n, body)

    if tok == ("KW", "while"):
        p.eat()
        cond = parse_cond(p)
        p.skip_nls()
        body = []
        while p.peek() != ("KW", "end"):
            body.append(parse_stmt(p))
            p.skip_nls()
        p.expect("KW", "end")
        return ("while", cond, body)

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
        p.expect("KW", "in")
        seq = parse_expr(p)
        backwards = bool(p.accept("KW", "going"))
        if backwards:
            p.expect("KW", "backwards")
        p.skip_nls()
        body = []
        while p.peek() != ("KW", "end"):
            body.append(parse_stmt(p))
            p.skip_nls()
        p.expect("KW", "end")
        return ("for", name, seq, step, backwards, body)

    raise SyntaxError(f"I don't understand: {tok[1] or tok[0]}")


def parse_cond(p):
    left = parse_expr(p)
    p.expect("KW", "is")
    negate = bool(p.accept("KW", "not"))
    if p.accept("KW", "equal"):
        p.expect("KW", "to")
        op = "ne" if negate else "eq"
    elif p.accept("KW", "greater"):
        p.expect("KW", "than")
        op = "le" if negate else "gt"
    elif p.accept("KW", "less"):
        p.expect("KW", "than")
        op = "ge" if negate else "lt"
    else:
        raise SyntaxError("Expected 'equal to', 'greater than', or 'less than'")
    return ("cmp", op, left, parse_expr(p))


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


def parse_atom(p):
    # high-level "function-like" prefixes
    if p.accept("KW", "list"):
        p.expect("KW", "of")
        items = [parse_atom(p)]
        while p.accept("KW", "and"):
            items.append(parse_atom(p))
        return ("list", items)
    if p.accept("KW", "empty"):
        p.expect("KW", "list")
        return ("list", [])
    if p.accept("KW", "count"):
        p.expect("KW", "of")
        return ("call", "count", [parse_atom(p)])
    if p.accept("KW", "sum"):
        p.expect("KW", "of")
        return ("call", "sum", [parse_atom(p)])
    if p.accept("KW", "average"):
        p.expect("KW", "of")
        return ("call", "average", [parse_atom(p)])
    if p.accept("KW", "biggest"):
        p.expect("KW", "in")
        return ("call", "max", [parse_atom(p)])
    if p.accept("KW", "smallest"):
        p.expect("KW", "in")
        return ("call", "min", [parse_atom(p)])
    if p.accept("KW", "random"):
        if p.accept("KW", "from"):
            a = parse_atom(p)
            p.expect("KW", "to")
            b = parse_atom(p)
            return ("call", "randnum", [a, b])
        p.expect("KW", "in")
        return ("call", "randitem", [parse_atom(p)])

    tok = p.eat()
    if tok[0] == "NUM":
        return ("num", tok[1])
    if tok[0] == "STR":
        return ("str", tok[1])
    if tok[0] == "ID":
        return ("var", tok[1])
    if tok == ("KW", "true"):
        return ("num", 1)
    if tok == ("KW", "false"):
        return ("num", 0)
    raise SyntaxError(f"Expected a value, got {tok[1] or tok[0]}")


# ============================================================
# 3. INTERPRETER  -  walks the tree and runs it
# ============================================================

def evaluate(node, env):
    t = node[0]
    if t in ("num", "str"):
        return node[1]
    if t == "var":
        if node[1] not in env:
            raise NameError(f"You haven't set '{node[1]}' yet.")
        return env[node[1]]
    if t == "bin":
        _, op, a, b = node
        av, bv = evaluate(a, env), evaluate(b, env)
        return {"+": av + bv, "-": av - bv,
                "*": av * bv, "/": av / bv}[op]
    if t == "cmp":
        _, op, a, b = node
        av, bv = evaluate(a, env), evaluate(b, env)
        return {"eq": av == bv, "ne": av != bv,
                "gt": av > bv,  "lt": av < bv,
                "ge": av >= bv, "le": av <= bv}[op]
    if t == "list":
        return [evaluate(x, env) for x in node[1]]
    if t == "call":
        _, name, args = node
        vals = [evaluate(a, env) for a in args]
        if name == "count":    return len(vals[0])
        if name == "sum":      return sum(vals[0])
        if name == "average":  return sum(vals[0]) / len(vals[0])
        if name == "max":      return max(vals[0])
        if name == "min":      return min(vals[0])
        if name == "randnum":  return random.randint(int(vals[0]), int(vals[1]))
        if name == "randitem": return random.choice(vals[0])
    raise RuntimeError(f"Cannot evaluate {node}")


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
            env[node[1]] = cur + v
    elif t == "sub":
        env[node[1]] = env.get(node[1], 0) - evaluate(node[2], env)
    elif t == "print":
        print(evaluate(node[1], env))
    elif t == "ask":
        env[node[1]] = coerce(input("> "))
    elif t == "if":
        _, cond, body, else_body = node
        for s in (body if evaluate(cond, env) else else_body):
            run(s, env)
    elif t == "repeat":
        for _ in range(int(evaluate(node[1], env))):
            for s in node[2]:
                run(s, env)
    elif t == "while":
        while evaluate(node[1], env):
            for s in node[2]:
                run(s, env)
    elif t == "for":
        _, name, seq_node, step, backwards, body = node
        seq = list(evaluate(seq_node, env))
        if backwards:
            seq = seq[::-1]
        for item in seq[::step]:
            env[name] = item
            for s in body:
                run(s, env)


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

def main():
    if len(sys.argv) < 2:
        print("Usage: python plain.py <file.plain>")
        return
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        src = f.read()
    try:
        run(parse(tokenize(src)), {})
    except (SyntaxError, NameError, RuntimeError) as e:
        print(f"Oops: {e}")


if __name__ == "__main__":
    main()
