"""
Plain - an English-like programming language.

Run:  python plain.py program.plain
"""

import bisect
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
    "try", "exit", "put",
    # conditions
    "is", "not", "equal", "greater", "less", "than", "one", "between",
    "divisible", "positive", "negative",
    # aliases / extras
    "say", "as", "now", "expect",
    # arithmetic
    "plus", "minus", "multiplied", "divided", "by",
    # values & list ops
    "list", "of", "and", "or", "empty",
    "lookup", "being", "at",
    "true", "false",
    "contains", "starts", "ends",
    "arguments",
    # built-ins
    "count", "length", "sum", "average", "biggest", "smallest",
    "random", "first", "last", "uppercase", "lowercase",
    "only", "the", "ones", "where", "it",
    "square", "root", "absolute", "value", "round",
    "split", "join",
    # indexing, lookups, and comparisons
    "item", "position", "remainder", "letters", "keys", "values",
    "least", "most", "has", "floor", "middle",
    # list surgery and parity
    "insert", "swap", "odd", "even", "replace",
}

TOKEN_RE = re.compile(
    r'"([^"]*)"'
    r'|(\d+(?:\.\d+)?)'
    r'|([A-Za-z_]\w*)'
    r'|(\n)'
    r'|([ \t\r]+|\#[^\n]*)'
    r'|(==|!=|<=|>=|\+=|-=|\*=|/=|//|[-+*/%^()\[\]{},:=<>])'
    r'|(\S)'
)


# Characters people paste in from Word / Google Docs, and what they meant.
CONFUSABLES = {
    "“": 'a straight quote "', "”": 'a straight quote "',
    "‘": "a straight quote '", "’": "a straight quote '",
    "–": "a minus sign -", "—": "a minus sign -",
    "×": "a star * for multiplying", "÷": "a slash / for dividing",
}


def tokenize(src):
    toks = []
    line = 1
    depth = 0  # inside ( [ { ... } ] ) newlines don't end the statement
    for m in TOKEN_RE.finditer(src.lstrip("\ufeff")):
        s, num, word, nl, skip, op, bad = m.groups()
        if skip is not None:
            continue
        if bad is not None:
            if bad in CONFUSABLES:
                raise SyntaxError(
                    f"Line {line}: That looks like a character pasted from a "
                    f"word processor. Use {CONFUSABLES[bad]} instead.")
            raise SyntaxError(
                f"Line {line}: I don't understand the symbol {bad!r}")
        if nl is not None:
            if depth == 0 and toks and toks[-1][0] != "NL":
                toks.append(("NL", None, line))
            line += 1
            continue
        if s is not None:
            toks.append(("STR", s, line))
        elif num is not None:
            toks.append(("NUM", float(num) if "." in num else int(num), line))
        elif op is not None:
            if op in "([{":
                depth += 1
            elif op in ")]}":
                depth = max(0, depth - 1)
            toks.append(("OP", op, line))
        elif word is not None:
            lw = word.lower()
            if lw in KEYWORDS:
                toks.append(("KW", lw, line))
            else:
                toks.append(("ID", word, line))
    toks.append(("EOF", None, line))
    return toks


# ============================================================
# 2. PARSER
# ============================================================

class Parser:
    def __init__(self, toks):
        self.t = toks
        self.i = 0

    def peek(self):
        return self.t[self.i][:2]

    def peek2(self):
        if self.i + 1 < len(self.t):
            return self.t[self.i + 1][:2]
        return ("EOF", None)

    def line(self):
        return self.t[self.i][2]

    def eat(self):
        tok = self.t[self.i]
        self.i += 1
        return tok[:2]

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
                f"Line {self.line()}: Expected '{val or kind}', got '{got}'",
                self.peek()))
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
    # Every statement is tagged with its line number so runtime errors
    # can say where they happened.
    ln = p.line()
    return ("stmt", ln, parse_stmt_inner(p))


def parse_stmt_inner(p):
    tok = p.peek()

    if tok == ("KW", "set"):
        p.eat()
        # set item N of NAME to VALUE   (also: set item N of item M of NAME ...)
        if p.accept("KW", "item"):
            keys = [parse_expr(p)]
            p.expect("KW", "of")
            while p.accept("KW", "item"):
                keys.append(parse_expr(p))
                p.expect("KW", "of")
            name = p.expect("ID")[1]
            keys.reverse()
            if not p.accept("OP", "="):
                p.expect("KW", "to")
            return ("setpath", name, keys, parse_expr(p))
        name = p.expect("ID")[1]
        # set lo and hi to ... - unpack a list of values into several names
        if p.accept("KW", "and"):
            names = [name, p.expect("ID")[1]]
            while p.accept("KW", "and"):
                names.append(p.expect("ID")[1])
            if not p.accept("OP", "="):
                p.expect("KW", "to")
            return ("setmulti", names, parse_expr(p))
        # set NAME at KEY to VALUE / set NAME[KEY] to VALUE  (lookups and lists)
        keys = []
        while True:
            if p.accept("KW", "at"):
                keys.append(parse_atom_base(p))
            elif p.accept("OP", "["):
                keys.append(parse_expr(p))
                p.expect("OP", "]")
            else:
                break
        if not p.accept("OP", "="):
            p.expect("KW", "to")
        if keys:
            return ("setpath", name, keys, parse_expr(p))
        return ("set", name, parse_expr(p))

    if tok == ("KW", "add"):
        p.eat()
        e = parse_expr(p)
        p.expect("KW", "to")
        name, keys = parse_target(p)
        if keys:
            return ("addpath", name, keys, e)
        return ("add", name, e)

    if tok == ("KW", "subtract"):
        p.eat()
        e = parse_expr(p)
        p.expect("KW", "from")
        name, keys = parse_target(p)
        if keys:
            return ("subpath", name, keys, e)
        return ("sub", name, e)

    if tok == ("KW", "put"):
        p.eat()
        val = parse_expr(p)
        p.expect("KW", "into")
        name, keys = parse_target(p)
        if keys:
            return ("setpath", name, keys, val)
        return ("set", name, val)

    if tok == ("KW", "remove"):
        p.eat()
        # remove the first/last from LIST [into VAR]
        if p.accept("KW", "the"):
            if p.accept("KW", "first"):
                which = "first"
            elif p.accept("KW", "last"):
                which = "last"
            else:
                raise SyntaxError(
                    f"Line {p.line()}: Expected 'first' or 'last' after 'remove the'")
            p.expect("KW", "from")
            name = p.expect("ID")[1]
            dest = p.expect("ID")[1] if p.accept("KW", "into") else None
            return ("removepos", name, which, dest)
        # remove item N from LIST [into VAR]
        if p.accept("KW", "item"):
            idx = parse_expr(p)
            p.expect("KW", "from")
            name = p.expect("ID")[1]
            dest = p.expect("ID")[1] if p.accept("KW", "into") else None
            return ("removeat", name, idx, dest)
        e = parse_expr(p)
        p.expect("KW", "from")
        return ("remove", p.expect("ID")[1], e)

    if tok == ("KW", "insert"):
        p.eat()
        val = parse_expr(p)
        p.expect("KW", "into")
        name = p.expect("ID")[1]
        p.expect("KW", "at")
        return ("insertat", name, parse_expr(p), val)

    if tok == ("KW", "swap"):
        p.eat()
        t1 = parse_target(p)
        p.expect("KW", "and")
        return ("swap", t1, parse_target(p))

    if tok == ("KW", "sort"):
        p.eat()
        name = p.expect("ID")[1]
        # sort LIST by EXPR  - 'it' is each item, e.g. sort pairs by it[2]
        key = None
        if p.accept("KW", "by"):
            key = parse_expr(p)
        desc = bool(p.accept("KW", "backwards"))
        return ("sort", name, desc, key)

    if tok == ("KW", "reverse"):
        p.eat()
        return ("reverse", p.expect("ID")[1])

    if tok == ("KW", "print") or tok == ("KW", "say"):
        p.eat()
        return ("print", parse_expr(p))

    if tok == ("KW", "expect"):
        p.eat()
        left = parse_expr(p)
        if not p.accept("OP", "=="):
            p.expect("KW", "to")
            p.expect("KW", "equal")
        right = parse_expr(p)
        return ("expect", left, right)

    if tok == ("KW", "ask"):
        p.eat()
        name = p.expect("ID")[1]
        prompt = None
        if p.accept("KW", "with"):
            prompt = parse_expr(p)
        return ("ask", name, prompt)

    if tok == ("KW", "try"):
        # try ... otherwise ... end - if anything in the try part goes
        # wrong, the otherwise part runs with 'error' holding the message.
        p.eat()
        body = parse_block(p, ["otherwise", "end"])
        handler = []
        if p.accept("KW", "otherwise"):
            handler = parse_block(p, ["end"])
        p.expect("KW", "end")
        return ("try", body, handler)

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
        e = parse_expr(p)
        # give back lo and hi  - several values come back as a list
        if p.accept("KW", "and"):
            items = [e, parse_expr(p)]
            while p.accept("KW", "and"):
                items.append(parse_expr(p))
            return ("return", ("list", items))
        return ("return", e)

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
        return parse_if(p)

    if tok == ("KW", "exit"):
        p.eat()
        return ("exit",)

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
        # One loop, or several nested in one line:
        #   for each r from 1 to 3 and c from 1 to 3 ... end
        #   for each row in grid and cell in row ... end
        specs = [parse_loop_spec(p, first=True)]
        while p.accept("KW", "and"):
            specs.append(parse_loop_spec(p, first=False))
        body = parse_block(p, ["end"])
        p.expect("KW", "end")
        if len(specs) == 1:
            s = specs[0]
            if s[0] == "range":
                _, name, start, stop, step_expr = s
                return ("rangefor", name, start, stop, step_expr, body)
            if s[0] == "pairs":
                _, n1, n2, seq = s
                return ("pairfor", n1, n2, seq, body)
            _, name, seq, step, backwards, iname = s
            return ("for", name, seq, step, backwards, iname, body)
        return ("multifor", specs, body)

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

    # Statements that start with a plain name:
    #   x = 5      x += 1     nums[2] = 9     grid[r][c] = 0     f(a, b)
    if tok[0] == "ID":
        ln = p.line()
        name = p.eat()[1]
        if p.accept("OP", "("):
            args = []
            if not p.accept("OP", ")"):
                args.append(parse_expr(p))
                while p.accept("OP", ","):
                    args.append(parse_expr(p))
                p.expect("OP", ")")
            return ("exprstmt", ("userfn", name, args))
        keys = []
        while p.accept("OP", "["):
            keys.append(parse_expr(p))
            p.expect("OP", "]")
        if keys:
            if p.accept("OP", "+="):
                return ("addpath", name, keys, parse_expr(p))
            if p.accept("OP", "-="):
                return ("subpath", name, keys, parse_expr(p))
            cur = ("var", name)
            for k in keys:
                cur = ("index", cur, k)
            if p.accept("OP", "*="):
                return ("setpath", name, keys, ("bin", "*", cur, parse_expr(p)))
            if p.accept("OP", "/="):
                return ("setpath", name, keys, ("bin", "/", cur, parse_expr(p)))
            if not p.accept("OP", "="):
                p.expect("KW", "to")
            return ("setpath", name, keys, parse_expr(p))
        if p.accept("OP", "="):
            return ("set", name, parse_expr(p))
        if p.accept("OP", "+="):
            return ("add", name, parse_expr(p))
        if p.accept("OP", "-="):
            return ("sub", name, parse_expr(p))
        if p.accept("OP", "*="):
            return ("set", name, ("bin", "*", ("var", name), parse_expr(p)))
        if p.accept("OP", "/="):
            return ("set", name, ("bin", "/", ("var", name), parse_expr(p)))
        raise SyntaxError(suggest(
            f"Line {ln}: I don't understand '{name}' here. To change it, "
            f"write 'set {name} to ...' or '{name} = ...'", ("ID", name)))

    raise SyntaxError(suggest(
        f"Line {p.line()}: I don't understand '{tok[1] or tok[0]}'", tok))


def parse_target(p):
    # A place a value can live: x, nums[2], board[r][c], ages at "amy"
    name = p.expect("ID")[1]
    keys = []
    while True:
        if p.accept("KW", "at"):
            keys.append(parse_atom_base(p))
        elif p.accept("OP", "["):
            keys.append(parse_expr(p))
            p.expect("OP", "]")
        else:
            return (name, keys)


def parse_loop_spec(p, first):
    if p.accept("KW", "each"):
        step = 1
    elif p.accept("KW", "every"):
        p.expect("KW", "other")
        step = 2
    elif first:
        raise SyntaxError(
            f"Line {p.line()}: Expected 'each' or 'every other' after 'for'")
    else:
        step = 1  # "and c from 1 to 3" - the extra 'each' is optional
    # for each pair of x and y in nums - walks neighbors: (1st,2nd), (2nd,3rd)...
    if p.peek() == ("ID", "pair") and p.peek2() == ("KW", "of"):
        p.eat()
        p.eat()
        n1 = p.expect("ID")[1]
        p.expect("KW", "and")
        n2 = p.expect("ID")[1]
        p.expect("KW", "in")
        return ("pairs", n1, n2, parse_expr(p))
    name = p.expect("ID")[1]
    # for each ch at position i in word  - i counts 1, 2, 3, ...
    iname = None
    if p.accept("KW", "at"):
        p.expect("KW", "position")
        iname = p.expect("ID")[1]
    if p.accept("KW", "from"):
        if iname:
            raise SyntaxError(
                f"Line {p.line()}: 'at position' only works with 'in', "
                f"not number ranges (the loop value already counts).")
        start = parse_expr(p)
        p.expect("KW", "to")
        stop = parse_expr(p)
        step_expr = ("num", 1)
        if p.accept("KW", "by"):
            step_expr = parse_expr(p)
        return ("range", name, start, stop, step_expr)
    p.expect("KW", "in")
    seq = parse_expr(p)
    backwards = bool(p.accept("KW", "going"))
    if backwards:
        p.expect("KW", "backwards")
    return ("seq", name, seq, step, backwards, iname)


def parse_if(p):
    # The 'if' keyword has already been eaten.
    cond = parse_cond(p)
    p.expect("KW", "then")
    body = parse_block(p, ["end", "otherwise"])
    else_body = []
    if p.accept("KW", "otherwise"):
        # "otherwise if ... then" chains share a single final 'end'.
        if p.accept("KW", "if"):
            else_body = [("stmt", p.line(), parse_if(p))]
            return ("if", cond, body, else_body)
        else_body = parse_block(p, ["end"])
    p.expect("KW", "end")
    return ("if", cond, body, else_body)


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
    # "if not done then ..."
    if p.accept("KW", "not"):
        return ("logic", "not", parse_cmp(p), None)
    left = parse_expr(p)

    # symbol comparisons: == (or =), !=, <, >, <=, >=
    for sym, op in (("==", "eq"), ("=", "eq"), ("!=", "ne"),
                    ("<=", "le"), (">=", "ge"), ("<", "lt"), (">", "gt")):
        if p.accept("OP", sym):
            return ("cmp", op, left, parse_expr(p))

    # word-style checks that don't need 'is':
    #   X contains Y / X has Y / X starts with Y / X ends with Y
    if p.accept("KW", "contains") or p.accept("KW", "has"):
        return ("member", parse_expr(p), left)
    if p.accept("KW", "starts"):
        p.expect("KW", "with")
        return ("startswith", left, parse_expr(p))
    if p.accept("KW", "ends"):
        p.expect("KW", "with")
        return ("endswith", left, parse_expr(p))

    # X does not contain Y / have Y / start with Y / end with Y
    if p.peek() == ("ID", "does") and p.peek2() == ("KW", "not"):
        p.eat()
        p.eat()
        if p.accept("ID", "contain") or p.accept("ID", "have"):
            return ("logic", "not", ("member", parse_expr(p), left), None)
        if p.accept("ID", "start"):
            p.expect("KW", "with")
            return ("logic", "not", ("startswith", left, parse_expr(p)), None)
        if p.accept("KW", "end"):
            p.expect("KW", "with")
            return ("logic", "not", ("endswith", left, parse_expr(p)), None)
        raise SyntaxError(
            f"Line {p.line()}: Expected 'contain', 'have', 'start with', "
            f"or 'end with' after 'does not'")

    if not p.accept("KW", "is"):
        # No comparison at all: the value itself is the condition
        # (so "if done then" works when done is true/false).
        return left
    negate = bool(p.accept("KW", "not"))
    if p.accept("KW", "at"):
        if p.accept("KW", "least"):
            node = ("cmp", "ge", left, parse_expr(p))
        elif p.accept("KW", "most"):
            node = ("cmp", "le", left, parse_expr(p))
        else:
            raise SyntaxError(
                f"Line {p.line()}: Expected 'least' or 'most' after 'is at'")
    elif p.accept("KW", "equal"):
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
    elif p.accept("KW", "empty"):
        node = ("isempty", left)
    elif p.accept("KW", "in"):
        node = ("member", left, parse_atom(p))
    elif p.accept("KW", "positive"):
        node = ("cmp", "gt", left, ("num", 0))
    elif p.accept("KW", "negative"):
        node = ("cmp", "lt", left, ("num", 0))
    elif p.accept("KW", "odd"):
        node = ("parity", left, 1)
    elif p.accept("KW", "even"):
        node = ("parity", left, 0)
    elif p.peek() == ("ID", "a") and p.peek2() in (
            ("ID", "number"), ("KW", "list"), ("KW", "lookup"), ("ID", "text")):
        # type checks: is a number / is a list / is a lookup / is a text
        p.eat()
        if p.accept("ID", "number"):
            node = ("typeis", left, "number")
        elif p.accept("KW", "list"):
            node = ("typeis", left, "list")
        elif p.accept("KW", "lookup"):
            node = ("typeis", left, "lookup")
        else:
            p.expect("ID", "text")
            node = ("typeis", left, "text")
    elif p.accept("ID", "text"):
        node = ("typeis", left, "text")
    else:
        raise SyntaxError(
            "Expected 'equal to', 'greater/less than', 'one of', or 'between'"
        )
    return ("logic", "not", node, None) if negate else node


# ---------- Expressions ----------

def parse_expr(p):
    left = parse_term(p)
    while True:
        if p.accept("KW", "plus") or p.accept("OP", "+"):
            left = ("bin", "+", left, parse_term(p))
        elif p.accept("KW", "minus") or p.accept("OP", "-"):
            left = ("bin", "-", left, parse_term(p))
        else:
            return left


def parse_term(p):
    left = parse_power(p)
    while True:
        if p.accept("KW", "multiplied"):
            p.expect("KW", "by")
            left = ("bin", "*", left, parse_power(p))
        elif p.accept("OP", "*"):
            left = ("bin", "*", left, parse_power(p))
        elif p.accept("KW", "divided"):
            p.expect("KW", "by")
            left = ("bin", "/", left, parse_power(p))
        elif p.accept("OP", "/"):
            left = ("bin", "/", left, parse_power(p))
        elif p.accept("OP", "//"):
            left = ("bin", "//", left, parse_power(p))
        elif p.accept("OP", "%"):
            left = ("call", "mod", [left, parse_power(p)])
        else:
            return left


def parse_power(p):
    left = parse_atom(p)
    if p.accept("OP", "^"):
        return ("bin", "**", left, parse_power(p))
    return left


# One-argument built-in expressions: (keyword, internal-name, separator-keyword)
UNARY_BUILTINS = [
    ("sum",       "sum",       "of"),
    ("average",   "average",   "of"),
    ("biggest",   "max",       "in"),
    ("smallest",  "min",       "in"),
    ("first",     "first",     "of"),
    ("last",      "last",      "of"),
    ("uppercase", "uppercase", "of"),
    ("lowercase", "lowercase", "of"),
    ("letters",   "letters",   "of"),
    ("keys",      "keys",      "of"),
    ("values",    "values",    "of"),
    ("value",     "coerce",    "of"),
    ("floor",     "floor",     "of"),
]


def parse_atom(p):
    node = parse_atom_base(p)
    while True:
        # postfix indexing: LIST at 2, LOOKUP at "key", nums[2], d["key"]
        if p.accept("KW", "at"):
            node = ("index", node, parse_atom_base(p))
        elif p.accept("OP", "["):
            node = ("index", node, parse_expr(p))
            p.expect("OP", "]")
        elif p.accept("ID", "squared"):
            node = ("bin", "*", node, node)
        else:
            return node


def parse_atom_base(p):
    # ( grouping ) - may hold a value or a whole condition
    if p.accept("OP", "("):
        node = parse_cond(p)
        p.expect("OP", ")")
        return node

    # [1, 2, 3] list literal (nests: [[1, 2], [3, 4]])
    if p.accept("OP", "["):
        if p.accept("OP", "]"):
            return ("list", [])
        items = [parse_expr(p)]
        while p.accept("OP", ","):
            items.append(parse_expr(p))
        p.expect("OP", "]")
        return ("list", items)

    # {"key": value} lookup literal
    if p.accept("OP", "{"):
        if p.accept("OP", "}"):
            return ("dict", [])
        pairs = []
        while True:
            k = parse_expr(p)
            p.expect("OP", ":")
            pairs.append((k, parse_expr(p)))
            if not p.accept("OP", ","):
                break
        p.expect("OP", "}")
        return ("dict", pairs)

    # unary minus: -5
    if p.accept("OP", "-"):
        return ("bin", "-", ("num", 0), parse_atom(p))

    # list literals
    if p.accept("KW", "list"):
        p.expect("KW", "of")
        items = [parse_atom(p)]
        while p.accept("KW", "and"):
            items.append(parse_atom(p))
        return ("list", items)
    if p.accept("KW", "empty"):
        if p.accept("KW", "lookup"):
            return ("dict", [])
        p.expect("KW", "list")
        return ("list", [])

    # lookup literal: lookup of "a" being 1 and "b" being 2
    if p.accept("KW", "lookup"):
        p.expect("KW", "of")
        pairs = []
        while True:
            k = parse_atom_base(p)
            p.expect("KW", "being")
            pairs.append((k, parse_atom(p)))
            if not p.accept("KW", "and"):
                break
        return ("dict", pairs)

    # item N of LIST  (1-based)
    if p.accept("KW", "item"):
        idx = parse_expr(p)
        p.expect("KW", "of")
        return ("index", parse_atom(p), idx)

    # position of X in LIST  (1-based; 0 means not found)
    if p.accept("KW", "position"):
        p.expect("KW", "of")
        x = parse_atom(p)
        p.expect("KW", "in")
        return ("call", "position", [x, parse_atom(p)])

    # remainder of A divided by B
    if p.accept("KW", "remainder"):
        p.expect("KW", "of")
        a = parse_atom(p)
        p.expect("KW", "divided")
        p.expect("KW", "by")
        return ("call", "mod", [a, parse_atom(p)])

    # middle of A and B  (whole-number midpoint, great for binary search)
    if p.accept("KW", "middle"):
        p.expect("KW", "of")
        a = parse_atom(p)
        p.expect("KW", "and")
        return ("call", "middle", [a, parse_atom(p)])

    # count of LIST, and count of X in LIST (how many times X appears)
    if p.accept("KW", "count") or p.accept("KW", "length"):
        p.expect("KW", "of")
        a = parse_atom(p)
        if p.accept("KW", "in"):
            return ("call", "countin", [a, parse_atom(p)])
        return ("call", "count", [a])

    # replace "a" with "b" in TEXT (or in a list, swapping matching items)
    if p.accept("KW", "replace"):
        a = parse_atom(p)
        p.expect("KW", "with")
        b = parse_atom(p)
        p.expect("KW", "in")
        return ("call", "replace", [a, b, parse_atom(p)])

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

    # unary minus: "negative 5"
    if p.accept("KW", "negative"):
        return ("bin", "-", ("num", 0), parse_atom(p))

    # current time
    if p.accept("KW", "now"):
        return ("call", "now", [])

    # values typed after the program name on the command line
    if p.accept("KW", "arguments"):
        return ("call", "argv", [])

    # slicing: "the first N of LIST" / "the last N of LIST"
    if p.accept("KW", "the"):
        if p.accept("KW", "first"):
            n = parse_atom(p)
            p.expect("KW", "of")
            return ("call", "take_first", [parse_atom(p), n])
        if p.accept("KW", "last"):
            n = parse_atom(p)
            p.expect("KW", "of")
            return ("call", "take_last", [parse_atom(p), n])
        raise SyntaxError("Expected 'first' or 'last' after 'the'")

    # map: "each NAME in LIST as EXPR"
    if p.accept("KW", "each"):
        name = p.expect("ID")[1]
        p.expect("KW", "in")
        src = parse_atom(p)
        p.expect("KW", "as")
        body = parse_expr(p)
        return ("map", name, src, body)

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
            args.append(parse_expr(p))
            while p.accept("KW", "and"):
                args.append(parse_expr(p))
        return ("userfn", name, args)

    # 'it' is the implicit element inside a filter
    if p.accept("KW", "it"):
        return ("var", "it")

    # grid of 3 by 4 filled with 0   (a list of lists, ready for 2D problems;
    # 'grid' stays usable as a normal variable name everywhere else)
    if p.peek() == ("ID", "grid") and p.peek2() == ("KW", "of"):
        p.eat()
        p.eat()
        rows = parse_atom(p)
        p.expect("KW", "by")
        cols = parse_atom(p)
        p.expect("ID", "filled")
        p.expect("KW", "with")
        return ("call", "grid", [rows, cols, parse_atom(p)])

    # trim of TEXT - remove spaces from both ends ('trim' is not reserved)
    if p.peek() == ("ID", "trim") and p.peek2() == ("KW", "of"):
        p.eat()
        p.eat()
        return ("call", "trim", [parse_atom(p)])

    # items 2 to 4 of LIST - a slice by positions (works on text too)
    if p.peek() == ("ID", "items") and p.peek2()[0] in ("NUM", "ID"):
        p.eat()
        a = parse_expr(p)
        p.expect("KW", "to")
        b = parse_expr(p)
        p.expect("KW", "of")
        return ("call", "slice", [parse_atom(p), a, b])

    # numbers from 1 to 10 [by 2] - a ready-made list of numbers
    if p.peek() == ("ID", "numbers") and p.peek2() == ("KW", "from"):
        p.eat()
        p.eat()
        a = parse_atom(p)
        p.expect("KW", "to")
        b = parse_atom(p)
        step = ("num", 1)
        if p.accept("KW", "by"):
            step = parse_atom(p)
        return ("call", "numrange", [a, b, step])

    # bigger of A and B / smaller of A and B  (also not reserved words)
    if p.peek() == ("ID", "bigger") and p.peek2() == ("KW", "of"):
        p.eat()
        p.eat()
        a = parse_atom(p)
        p.expect("KW", "and")
        return ("call", "max2", [a, parse_atom(p)])
    if p.peek() == ("ID", "smaller") and p.peek2() == ("KW", "of"):
        p.eat()
        p.eat()
        a = parse_atom(p)
        p.expect("KW", "and")
        return ("call", "min2", [a, parse_atom(p)])

    line = p.line()
    tok = p.eat()
    if tok[0] == "NUM": return ("num", tok[1])
    if tok[0] == "STR": return ("str", tok[1])
    if tok[0] == "ID":
        # Python-style call: name(arg, arg)
        if p.accept("OP", "("):
            args = []
            if not p.accept("OP", ")"):
                args.append(parse_expr(p))
                while p.accept("OP", ","):
                    args.append(parse_expr(p))
                p.expect("OP", ")")
            return ("userfn", tok[1], args)
        return ("var", tok[1])
    if tok == ("KW", "true"):  return ("num", 1)
    if tok == ("KW", "false"): return ("num", 0)
    raise SyntaxError(suggest(
        f"Line {line}: Expected a value, got '{tok[1] or tok[0]}'", tok))


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


class PlainRuntimeError(Exception):
    """A runtime problem, already labeled with the line it happened on."""


# --trace / --explain mode: narrate each line as it runs.
TRACE = {"on": False, "src": []}


def to_str(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, list):
        return "[" + ", ".join(to_str(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{to_str(k)}: {to_str(x)}" for k, x in v.items()) + "}"
    return str(v)


def index_get(base, key):
    if isinstance(base, dict):
        if key not in base:
            raise RuntimeError(f"The lookup doesn't have '{to_str(key)}' yet.")
        return base[key]
    if isinstance(base, (list, str)):
        i = int(key)
        kind = "list" if isinstance(base, list) else "text"
        if i < 1 or i > len(base):
            raise RuntimeError(
                f"Position {i} is outside the {kind} (it has {len(base)} items).")
        return base[i - 1]
    raise RuntimeError("'at' only works on lists, text, and lookups.")


def add_vals(a, b):
    if isinstance(a, str) or isinstance(b, str):
        return to_str(a) + to_str(b)
    return a + b


def kind_name(v):
    if isinstance(v, bool):
        return "a true/false value"
    if isinstance(v, (int, float)):
        return "a number"
    if isinstance(v, str):
        return "text"
    if isinstance(v, list):
        return "a list"
    if isinstance(v, dict):
        return "a lookup"
    return "that"


def path_get(env, name, keys):
    if name not in env:
        raise NameError(f"You haven't set '{name}' yet.")
    v = env[name]
    for k in keys:
        v = index_get(v, k)
    return v


def path_set(env, name, keys, val):
    if not keys:
        env[name] = val
        return
    if name not in env:
        raise NameError(f"You haven't set '{name}' yet.")
    target = env[name]
    for k in keys[:-1]:
        target = index_get(target, k)
    key = keys[-1]
    if isinstance(target, dict):
        target[key] = val
    elif isinstance(target, list):
        i = int(key)
        if i < 1 or i > len(target):
            raise RuntimeError(
                f"Position {i} is outside the list (it has {len(target)} "
                f"items). Use 'add ... to {name}' to make it longer.")
        target[i - 1] = val
    else:
        raise RuntimeError(f"'{name}' is not a list or lookup.")


# Shared by the AST interpreter and the bytecode VM so both engines give
# the exact same results and the exact same friendly error messages.

def bin_op(op, av, bv):
    try:
        if op == "+": return add_vals(av, bv)
        if op == "-": return av - bv
        if op == "*": return av * bv
        if op == "/":
            if bv == 0:
                raise RuntimeError("You can't divide by zero.")
            return av / bv
        if op == "//":
            if bv == 0:
                raise RuntimeError("You can't divide by zero.")
            return av // bv
        if op == "**":
            return av ** bv
    except TypeError:
        shown = "^" if op == "**" else op
        tip = (" Tip: 'value of x' turns text into a number."
               if isinstance(av, str) or isinstance(bv, str) else "")
        raise RuntimeError(
            f"You can't use '{shown}' with {kind_name(av)} and "
            f"{kind_name(bv)}.{tip}") from None


def cmp_op(op, av, bv):
    try:
        return {"eq": av == bv, "ne": av != bv, "gt": av > bv,
                "lt": av < bv, "ge": av >= bv, "le": av <= bv}[op]
    except TypeError:
        raise RuntimeError(
            f"You can't compare {kind_name(av)} with {kind_name(bv)}.") from None


def call_builtin(name, vals):
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
    if name == "round":
        # round halves away from zero, like school math (Python's
        # round() would give round(4.5) == 4)
        return int(math.floor(x + 0.5)) if x >= 0 else int(math.ceil(x - 0.5))
    if name == "split":     return str(vals[0]).split(vals[1])
    if name == "join":      return str(vals[1]).join(to_str(v) for v in vals[0])
    if name == "take_first":
        seq = vals[0] if isinstance(vals[0], (str, list)) else list(vals[0])
        n = int(vals[1])
        return seq[:n] if n > 0 else seq[:0]
    if name == "take_last":
        seq = vals[0] if isinstance(vals[0], (str, list)) else list(vals[0])
        n = int(vals[1])
        return seq[-n:] if n > 0 else seq[:0]
    if name == "now":       return time.strftime("%Y-%m-%d %H:%M:%S")
    if name == "mod":
        if vals[1] == 0:
            raise RuntimeError("You can't take a remainder when dividing by zero.")
        return vals[0] % vals[1]
    if name == "floor":     return math.floor(x)
    if name == "middle":    return (int(vals[0]) + int(vals[1])) // 2
    if name == "position":
        item, container = vals
        if isinstance(container, str):
            return container.find(to_str(item)) + 1
        return container.index(item) + 1 if item in container else 0
    if name == "grid":
        rows, cols, fill = int(vals[0]), int(vals[1]), vals[2]
        return [[fill for _ in range(cols)] for _ in range(rows)]
    if name == "max2":    return max(vals)
    if name == "min2":    return min(vals)
    if name == "argv":    return [coerce(a) for a in sys.argv[2:]]
    if name == "countin":
        item, container = vals
        if isinstance(container, list):
            return container.count(item)
        return to_str(container).count(to_str(item))
    if name == "replace":
        old, new, container = vals
        if isinstance(container, list):
            return [new if item == old else item for item in container]
        return to_str(container).replace(to_str(old), to_str(new))
    if name == "trim":      return to_str(x).strip()
    if name == "slice":
        seq = vals[0] if isinstance(vals[0], (str, list)) else list(vals[0])
        i, j = max(1, int(vals[1])), min(len(seq), int(vals[2]))
        return seq[i - 1:j] if i <= j else seq[:0]
    if name == "numrange":
        a, b, s = int(vals[0]), int(vals[1]), int(vals[2])
        if s <= 0:
            raise RuntimeError(
                "The step in 'numbers from ... by ...' must be a positive number.")
        return list(range(a, b + 1, s)) if b >= a else list(range(a, b - 1, -s))
    if name == "letters":   return list(to_str(x))
    if name == "keys":      return list(x.keys())
    if name == "values":    return list(x.values())
    if name == "coerce":    return coerce(to_str(x))
    raise RuntimeError(f"There is no built-in named '{name}'.")


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
        return bin_op(op, evaluate(a, env), evaluate(b, env))
    if t == "cmp":
        _, op, a, b = node
        return cmp_op(op, evaluate(a, env), evaluate(b, env))
    if t == "index":
        return index_get(evaluate(node[1], env), evaluate(node[2], env))
    if t == "dict":
        return {evaluate(k, env): evaluate(v, env) for k, v in node[1]}
    if t == "startswith":
        return to_str(evaluate(node[1], env)).startswith(to_str(evaluate(node[2], env)))
    if t == "endswith":
        return to_str(evaluate(node[1], env)).endswith(to_str(evaluate(node[2], env)))
    if t == "member":
        return evaluate(node[1], env) in evaluate(node[2], env)
    if t == "between":
        v = evaluate(node[1], env)
        lo = evaluate(node[2], env)
        hi = evaluate(node[3], env)
        return lo <= v <= hi
    if t == "divisible":
        return evaluate(node[1], env) % evaluate(node[2], env) == 0
    if t == "parity":
        return int(evaluate(node[1], env)) % 2 == node[2]
    if t == "typeis":
        v = evaluate(node[1], env)
        kind = node[2]
        if kind == "number":
            return isinstance(v, (int, float)) and not isinstance(v, bool)
        if kind == "text":
            return isinstance(v, str)
        if kind == "list":
            return isinstance(v, list)
        return isinstance(v, dict)
    if t == "isempty":
        return len(evaluate(node[1], env)) == 0
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
        return call_builtin(name, [evaluate(a, env) for a in args])
    if t == "userfn":
        return call_user_fn(node[1], [evaluate(a, env) for a in node[2]], env)
    if t == "map":
        _, name, src_node, body = node
        src = evaluate(src_node, env)
        result = []
        had = name in env
        saved = env.get(name)
        try:
            for x in src:
                env[name] = x
                result.append(evaluate(body, env))
        finally:
            if had:
                env[name] = saved
            else:
                env.pop(name, None)
        return result
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
    elif t == "stmt":
        # Label any runtime problem with the line it happened on.
        if TRACE["on"]:
            ln = node[1]
            text = TRACE["src"][ln - 1].strip() if 0 < ln <= len(TRACE["src"]) else ""
            print(f"[line {ln}] {text}")
        try:
            run(node[2], env)
        except PlainRuntimeError:
            raise
        except (NameError, RuntimeError, ValueError, TypeError,
                ZeroDivisionError, IndexError, KeyError) as e:
            raise PlainRuntimeError(f"Line {node[1]}: {e}") from None
        if TRACE["on"]:
            inner = node[2]
            if inner[0] in ("set", "add", "sub") and inner[1] in env:
                print(f"          ... {inner[1]} is now {to_str(env[inner[1]])}")
            elif inner[0] == "setmulti":
                for n in inner[1]:
                    print(f"          ... {n} is now {to_str(env.get(n))}")
            elif inner[0] in ("setpath", "addpath", "subpath") and inner[1] in env:
                print(f"          ... {inner[1]} is now {to_str(env[inner[1]])}")
    elif t == "set":
        env[node[1]] = evaluate(node[2], env)
    elif t == "setmulti":
        _, names, e = node
        v = evaluate(e, env)
        if not isinstance(v, list):
            raise RuntimeError(
                f"To fill {len(names)} names at once, the value must be a "
                f"list, but this is {kind_name(v)}.")
        if len(v) != len(names):
            raise RuntimeError(
                f"Expected {len(names)} values for "
                f"{', '.join(names)} but the list has {len(v)}.")
        for n, val in zip(names, v):
            env[n] = val
    elif t == "setpath":
        _, name, key_nodes, val_n = node
        if name not in env:
            raise NameError(f"You haven't set '{name}' yet.")
        keys = [evaluate(k, env) for k in key_nodes]
        path_set(env, name, keys, evaluate(val_n, env))
    elif t == "addpath" or t == "subpath":
        # add 1 to tally at word / nums[2] += 1 / subtract 1 from hp["boss"]
        # Adding to a lookup key that isn't there yet starts it at 0,
        # just like 'add 1 to x' does for a brand-new variable.
        _, name, key_nodes, e = node
        keys = [evaluate(k, env) for k in key_nodes]
        v = evaluate(e, env)
        container = path_get(env, name, keys[:-1])
        key = keys[-1]
        if isinstance(container, dict):
            cur = container.get(key, 0)
            if t == "addpath" and isinstance(cur, list):
                cur.append(v)
            else:
                container[key] = add_vals(cur, v) if t == "addpath" else cur - v
        elif isinstance(container, list):
            i = int(key)
            if i < 1 or i > len(container):
                raise RuntimeError(
                    f"Position {i} is outside the list (it has {len(container)} items).")
            cur = container[i - 1]
            if t == "addpath" and isinstance(cur, list):
                cur.append(v)
            else:
                container[i - 1] = add_vals(cur, v) if t == "addpath" else cur - v
        else:
            raise RuntimeError(f"'{name}' is not a list or lookup.")
    elif t == "removepos":
        _, name, which, dest = node
        lst = env.get(name)
        if not isinstance(lst, list):
            raise RuntimeError(f"'{name}' is not a list.")
        if not lst:
            raise RuntimeError(f"'{name}' is already empty.")
        v = lst.pop(0) if which == "first" else lst.pop()
        if dest:
            env[dest] = v
    elif t == "removeat":
        _, name, idx_n, dest = node
        lst = env.get(name)
        if not isinstance(lst, list):
            raise RuntimeError(f"'{name}' is not a list.")
        i = int(evaluate(idx_n, env))
        if i < 1 or i > len(lst):
            raise RuntimeError(
                f"Position {i} is outside the list (it has {len(lst)} items).")
        v = lst.pop(i - 1)
        if dest:
            env[dest] = v
    elif t == "insertat":
        _, name, idx_n, val_n = node
        lst = env.get(name)
        if not isinstance(lst, list):
            raise RuntimeError(f"'{name}' is not a list.")
        i = int(evaluate(idx_n, env))
        if i < 1 or i > len(lst) + 1:
            raise RuntimeError(
                f"Position {i} is outside the list (you can insert at 1 "
                f"to {len(lst) + 1}).")
        lst.insert(i - 1, evaluate(val_n, env))
    elif t == "swap":
        _, (n1, kn1), (n2, kn2) = node
        k1 = [evaluate(k, env) for k in kn1]
        k2 = [evaluate(k, env) for k in kn2]
        v1 = path_get(env, n1, k1)
        v2 = path_get(env, n2, k2)
        path_set(env, n1, k1, v2)
        path_set(env, n2, k2, v1)
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
        target = env.get(node[1])
        if isinstance(target, list) and v in target:
            target.remove(v)
        elif isinstance(target, dict) and v in target:
            del target[v]
    elif t == "sort":
        lst = env.get(node[1])
        if not isinstance(lst, list):
            raise RuntimeError(f"'{node[1]}' is not a list, so it can't be sorted.")
        if node[3] is None:
            lst.sort(reverse=node[2])
        else:
            had = "it" in env
            saved = env.get("it")

            def sort_key(x):
                env["it"] = x
                return evaluate(node[3], env)

            try:
                lst.sort(key=sort_key, reverse=node[2])
            finally:
                if had:
                    env["it"] = saved
                else:
                    env.pop("it", None)
    elif t == "reverse":
        env[node[1]].reverse()
    elif t == "print":
        print(to_str(evaluate(node[1], env)))
    elif t == "ask":
        prompt = "> "
        if node[2] is not None:
            prompt = to_str(evaluate(node[2], env)) + " "
        env[node[1]] = coerce(input(prompt))
    elif t == "try":
        try:
            for s in node[1]:
                run(s, env)
        except PlainRuntimeError as e:
            env["error"] = str(e)
            for s in node[2]:
                run(s, env)
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
        _, name, seq_node, step, backwards, iname, body = node
        seq = list(evaluate(seq_node, env))
        indexed = list(enumerate(seq, 1))  # position = place in the original list
        if backwards:
            indexed.reverse()
        for i, item in indexed[::step]:
            env[name] = item
            if iname:
                env[iname] = i
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
    elif t == "pairfor":
        _, n1, n2, seq_n, body = node
        seq = list(evaluate(seq_n, env))
        for a, b in zip(seq, seq[1:]):
            env[n1] = a
            env[n2] = b
            try:
                for s in body:
                    run(s, env)
            except SkipLoop:
                continue
            except StopLoop:
                break
    elif t == "multifor":
        # Several loops written as one: "for each r ... and c ... end".
        # 'skip' moves to the next combination; 'stop' leaves the whole thing.
        _, specs, body = node

        def run_level(k):
            if k == len(specs):
                try:
                    for s in body:
                        run(s, env)
                except SkipLoop:
                    pass
                return
            spec = specs[k]
            if spec[0] == "range":
                _, name, start_n, stop_n, step_n = spec
                start = int(evaluate(start_n, env))
                stop = int(evaluate(stop_n, env))
                step = int(evaluate(step_n, env))
                direction = 1 if stop >= start else -1
                v = start
                while (direction > 0 and v <= stop) or (direction < 0 and v >= stop):
                    env[name] = v
                    run_level(k + 1)
                    v += direction * step
            elif spec[0] == "pairs":
                _, n1, n2, seq_n = spec
                seq = list(evaluate(seq_n, env))
                for a, b in zip(seq, seq[1:]):
                    env[n1] = a
                    env[n2] = b
                    run_level(k + 1)
            else:
                _, name, seq_n, step, backwards, iname = spec
                seq = list(evaluate(seq_n, env))
                indexed = list(enumerate(seq, 1))
                if backwards:
                    indexed.reverse()
                for i, item in indexed[::step]:
                    env[name] = item
                    if iname:
                        env[iname] = i
                    run_level(k + 1)

        try:
            run_level(0)
        except StopLoop:
            pass
    elif t == "readlines":
        path = evaluate(node[2], env)
        with open(path, "r", encoding="utf-8-sig") as f:
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
    elif t == "exit":
        sys.exit(0)
    elif t == "return":
        raise ReturnValue(evaluate(node[1], env))
    elif t == "expect":
        a = evaluate(node[1], env)
        b = evaluate(node[2], env)
        if a == b:
            print(f"OK: got {to_str(a)}")
        else:
            print(f"FAIL: expected {to_str(b)}, got {to_str(a)}")
            env["__fails__"] = env.get("__fails__", 0) + 1


def coerce(s):
    s = s.strip().strip("\ufeff").strip()
    if s.startswith("\u00ef\u00bb\u00bf"):  # a UTF-8 marker read under the wrong encoding
        s = s[3:].strip()
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
# 4. BYTECODE COMPILER + VIRTUAL MACHINE
# ============================================================
# The default engine. The parser's AST is lowered to flat bytecode
# (one instruction list per function, plus the main program), and a
# stack-based VM executes it. Semantics are identical to the
# tree-walking interpreter above, including every friendly
# line-numbered error message:
#   - every statement compiles to a SET_LINE so the VM always knows
#     which source line is running;
#   - 'stop' / 'skip' lower to plain jumps when the loop is in the
#     same function, with no exceptions on the hot path. A 'stop'
#     that crosses a function call (legal in the tree-walker) still
#     works: it raises and the VM unwinds to the caller's loop block;
#   - the VM reuses the same runtime helpers (bin_op, cmp_op,
#     call_builtin, path_get/path_set, index_get, to_str), so error
#     text can't drift between engines.
# --trace / --explain always narrates through the AST engine, whose
# recursive shape matches the line-by-line story being told.

(OP_CONST, OP_STR, OP_LOAD, OP_STORE, OP_POP, OP_SET_LINE,
 OP_BIN, OP_CMP, OP_NOT, OP_BOOL, OP_JUMP, OP_JF, OP_JF_KEEP, OP_JT_KEEP,
 OP_INDEX, OP_LIST, OP_MAP_LIT, OP_MEMBER, OP_STARTS, OP_ENDS,
 OP_BETWEEN, OP_DIVISIBLE, OP_PARITY, OP_TYPEIS, OP_ISEMPTY,
 OP_BUILTIN, OP_CALL, OP_RETURN, OP_DEF, OP_FILTER, OP_MAPEXPR,
 OP_PRINT, OP_EXPECT, OP_ASK, OP_WAIT,
 OP_STOREMULTI, OP_CHECKVAR, OP_SETPATH, OP_ADDPATH, OP_SUBPATH,
 OP_LOAD0, OP_ADDVAR, OP_SUBVAR, OP_REMOVEVAL, OP_REMOVEPOS,
 OP_LISTFETCH, OP_REMOVEAT, OP_INSERTIDX, OP_INSERTDO, OP_SWAP,
 OP_SORT, OP_REVERSE, OP_READLINES, OP_SAVE,
 OP_TRY, OP_LOOP, OP_POPBLOCK, OP_POPITERS,
 OP_FORPREP, OP_RANGEPREP, OP_PAIRPREP, OP_REPEATPREP, OP_FORNEXT,
 OP_RAISESTOP, OP_RAISESKIP, OP_EXIT, OP_HALT, OP_EXPREND,
 # superinstructions, emitted only by the optimizer
 OP_BIN_LC, OP_BIN_LL, OP_BIN_XC, OP_CMP_LC, OP_CMP_XC,
 OP_ADDVAR_C) = range(74)

OP_NAMES = {v: k[3:] for k, v in list(globals().items()) if k.startswith("OP_")}

# How many Plain calls may be in flight at once. The AST engine hits
# Python's own recursion limit around this depth; the VM uses explicit
# frames, so it enforces the cap itself to keep the engines aligned.
MAX_FRAMES = 700

_SENTINEL = object()   # tells a missing variable apart from a stored None

# The peephole optimizer (constant folding, dead jumps, superinstructions).
# bench.py flips this off to measure how much the optimizer buys.
OPTIMIZE = True


class Code:
    """One compiled chunk: the main program, a function body, or a small
    expression (a filter condition, map body, or sort key). SET_LINE
    markers are stripped out of the instruction stream during finalize()
    and kept here as a line-number table (starts[i] is the first
    instruction belonging to lines[i]), so tracking the current line
    costs nothing until an error actually needs it."""
    __slots__ = ("name", "instrs", "starts", "lines")

    def __init__(self, name, instrs, starts, lines):
        self.name = name
        self.instrs = instrs
        self.starts = starts
        self.lines = lines


def _line_at(code, idx, default=0):
    """The source line of instruction idx, from the chunk's line table."""
    j = bisect.bisect_right(code.starts, idx) - 1
    return code.lines[j] if j >= 0 else default


class _Lbl:
    """A jump target that gets its final position during finalize()."""
    __slots__ = ("pos",)

    def __init__(self):
        self.pos = None


# ---- peephole optimizer ----

_JUMPY = (OP_JUMP, OP_JF, OP_JF_KEEP, OP_JT_KEEP, OP_TRY)


def _targets_of(op, arg):
    if op in _JUMPY:
        return (arg,)
    if op == OP_LOOP:
        return (arg[0], arg[1])
    if op == OP_FORNEXT:
        return (arg[0],)
    return ()


def _retarget(op, arg, m):
    if op in _JUMPY:
        return m(arg)
    if op == OP_LOOP:
        return (m(arg[0]), m(arg[1]), arg[2])
    if op == OP_FORNEXT:
        return (m(arg[0]),) + tuple(arg[1:])
    return arg


def _optimize(instrs, starts, lines):
    """Constant folding, dead-jump removal, and superinstruction fusion.
    Semantics-preserving by construction: folding is skipped whenever the
    operation would raise (so runtime errors still happen at runtime, on
    the right line), no rewrite window may contain a jump target or a
    statement start in its interior, and every fused opcode performs the
    exact same checks as the instructions it replaces."""
    while True:
        n = len(instrs)

        # Collapse jump-to-jump chains. The cycle guard matters: 'forever'
        # with an empty body is a legal jump to itself.
        def final_target(t):
            seen = set()
            while t < n and t not in seen and instrs[t][0] == OP_JUMP:
                seen.add(t)
                t = instrs[t][1]
            return t

        retargeted = False
        for i, (op, arg) in enumerate(instrs):
            ts = _targets_of(op, arg)
            if ts and tuple(final_target(t) for t in ts) != tuple(ts):
                instrs[i] = (op, _retarget(op, arg, final_target))
                retargeted = True

        protected = set(starts)
        for op, arg in instrs:
            protected.update(_targets_of(op, arg))

        out = []
        new_index = [0] * (n + 1)
        rewrote = False
        i = 0
        while i < n:
            op, arg = instrs[i]
            op2, arg2 = instrs[i + 1] if i + 1 < n else (None, None)
            op3, arg3 = instrs[i + 2] if i + 2 < n else (None, None)
            free2 = i + 1 not in protected
            free3 = free2 and i + 2 not in protected
            fused = None
            width = 1
            if free3:
                if op == OP_CONST and op2 == OP_CONST and op3 in (OP_BIN, OP_CMP):
                    try:
                        val = (bin_op if op3 == OP_BIN else cmp_op)(arg3, arg, arg2)
                        fused, width = (OP_CONST, val), 3
                    except Exception:
                        pass   # would raise at runtime: leave it there
                if fused is None and op == OP_LOAD and op3 == OP_BIN:
                    if op2 == OP_CONST:
                        fused, width = (OP_BIN_LC, (arg, arg2, arg3)), 3
                    elif op2 == OP_LOAD:
                        fused, width = (OP_BIN_LL, (arg, arg2, arg3)), 3
                if fused is None and op == OP_LOAD and op2 == OP_CONST and op3 == OP_CMP:
                    fused, width = (OP_CMP_LC, (arg, arg2, arg3)), 3
                if fused is None and op == OP_LOAD0 and op2 == OP_CONST \
                        and op3 == OP_ADDVAR and arg3 == arg:
                    fused, width = (OP_ADDVAR_C, (arg, arg2)), 3
            if fused is None and free2 and op == OP_CONST:
                if op2 == OP_BIN:
                    fused, width = (OP_BIN_XC, (arg2, arg)), 2
                elif op2 == OP_CMP:
                    fused, width = (OP_CMP_XC, (arg2, arg)), 2
                elif op2 == OP_NOT:
                    fused, width = (OP_CONST, not arg), 2
                elif op2 == OP_BOOL:
                    fused, width = (OP_CONST, bool(arg)), 2
            if fused is None and op == OP_JUMP and arg == i + 1:
                new_index[i] = len(out)   # jump to next instruction: dead
                rewrote = True
                i += 1
                continue
            for k in range(width):
                new_index[i + k] = len(out)
            out.append(fused if fused else (op, arg))
            if fused:
                rewrote = True
            i += width
        new_index[n] = len(out)

        instrs = [(op, _retarget(op, arg, lambda p: new_index[p]))
                  for op, arg in out]
        new_starts, new_lines = [], []
        for s, ln in zip(starts, lines):
            p = new_index[s]
            if new_starts and new_starts[-1] == p:
                new_lines[-1] = ln
            elif not new_lines or new_lines[-1] != ln:
                new_starts.append(p)
                new_lines.append(ln)
        starts, lines = new_starts, new_lines
        if not (rewrote or retargeted):
            return instrs, starts, lines


class _Compiler:
    def __init__(self):
        self.ins = []        # [op, arg] pairs; labels resolved at the end
        self.blocks = []     # compile-time stack of open loops / trys
        self.iters = 0       # how many runtime iterators are live here

    # ---- emit helpers ----

    def emit(self, op, arg=None):
        self.ins.append([op, arg])

    def lbl(self):
        return _Lbl()

    def mark(self, label):
        label.pos = len(self.ins)

    def finalize(self, name):
        raw = self.ins
        # New index of each raw position once SET_LINE markers are gone.
        # A dropped marker maps to the next kept instruction, which is
        # exactly where its line starts applying.
        new_index = []
        n = 0
        for op, _ in raw:
            new_index.append(n)
            if op != OP_SET_LINE:
                n += 1
        end = n

        def m(p):
            return new_index[p] if p < len(raw) else end

        instrs = []
        starts, lines = [], []
        for op, arg in raw:
            if op == OP_SET_LINE:
                pos = len(instrs)
                if starts and starts[-1] == pos:
                    lines[-1] = arg
                elif not lines or lines[-1] != arg:
                    starts.append(pos)
                    lines.append(arg)
                continue
            if isinstance(arg, _Lbl):
                arg = m(arg.pos)
            elif isinstance(arg, tuple) and any(isinstance(a, _Lbl) for a in arg):
                arg = tuple(m(a.pos) if isinstance(a, _Lbl) else a for a in arg)
            instrs.append((op, arg))
        if OPTIMIZE:
            instrs, starts, lines = _optimize(instrs, starts, lines)
        return Code(name, instrs, starts, lines)

    # ---- statements ----

    def block(self, stmts):
        for s in stmts:
            _, ln, inner = s
            self.emit(OP_SET_LINE, ln)
            self.stmt(inner, ln)

    def stmt(self, n, ln):
        t = n[0]
        if t == "set":
            self.expr(n[2])
            self.emit(OP_STORE, n[1])
        elif t == "setmulti":
            self.expr(n[2])
            self.emit(OP_STOREMULTI, n[1])
        elif t == "setpath":
            _, name, keys, val = n
            self.emit(OP_CHECKVAR, name)
            for k in keys:
                self.expr(k)
            self.expr(val)
            self.emit(OP_SETPATH, (name, len(keys)))
        elif t == "addpath" or t == "subpath":
            _, name, keys, e = n
            for k in keys:
                self.expr(k)
            self.expr(e)
            self.emit(OP_ADDPATH if t == "addpath" else OP_SUBPATH,
                      (name, len(keys)))
        elif t == "add":
            self.emit(OP_LOAD0, n[1])
            self.expr(n[2])
            self.emit(OP_ADDVAR, n[1])
        elif t == "sub":
            self.emit(OP_LOAD0, n[1])
            self.expr(n[2])
            self.emit(OP_SUBVAR, n[1])
        elif t == "remove":
            self.expr(n[2])
            self.emit(OP_REMOVEVAL, n[1])
        elif t == "removepos":
            self.emit(OP_REMOVEPOS, (n[1], n[2], n[3]))
        elif t == "removeat":
            _, name, idx, dest = n
            self.emit(OP_LISTFETCH, name)
            self.expr(idx)
            self.emit(OP_REMOVEAT, dest)
        elif t == "insertat":
            _, name, idx, val = n
            self.emit(OP_LISTFETCH, name)
            self.expr(idx)
            self.emit(OP_INSERTIDX)
            self.expr(val)
            self.emit(OP_INSERTDO)
        elif t == "swap":
            _, (n1, kn1), (n2, kn2) = n
            for k in kn1:
                self.expr(k)
            for k in kn2:
                self.expr(k)
            self.emit(OP_SWAP, (n1, len(kn1), n2, len(kn2)))
        elif t == "sort":
            _, name, desc, key = n
            keycode = _compile_expr_code(key, "sort key") if key else None
            self.emit(OP_SORT, (name, desc, keycode))
        elif t == "reverse":
            self.emit(OP_REVERSE, n[1])
        elif t == "print":
            self.expr(n[1])
            self.emit(OP_PRINT)
        elif t == "expect":
            self.expr(n[1])
            self.expr(n[2])
            self.emit(OP_EXPECT)
        elif t == "ask":
            if n[2] is not None:
                self.expr(n[2])
                self.emit(OP_ASK, (n[1], True))
            else:
                self.emit(OP_ASK, (n[1], False))
        elif t == "wait":
            self.expr(n[1])
            self.emit(OP_WAIT)
        elif t == "try":
            handler, end = self.lbl(), self.lbl()
            self.emit(OP_TRY, handler)
            self.blocks.append({"kind": "try", "iters": self.iters})
            self.block(n[1])
            self.blocks.pop()
            self.emit(OP_POPBLOCK, 1)
            self.emit(OP_JUMP, end)
            self.mark(handler)
            self.block(n[2])
            self.mark(end)
        elif t == "if":
            _, cond, body, else_body = n
            els, end = self.lbl(), self.lbl()
            self.expr(cond)
            self.emit(OP_JF, els)
            self.block(body)
            self.emit(OP_JUMP, end)
            self.mark(els)
            self.block(else_body)
            self.mark(end)
        elif t == "repeat":
            brk, cont, done = self.lbl(), self.lbl(), self.lbl()
            self.emit(OP_LOOP, (brk, cont, 1))
            self.blocks.append({"kind": "loop", "brk": brk, "cont": cont,
                                "iters": self.iters, "iters_cont": self.iters + 1})
            self.expr(n[1])
            self.emit(OP_REPEATPREP)
            self.iters += 1
            self.mark(cont)
            self.emit(OP_FORNEXT, (done, 0))
            self.block(n[2])
            self.emit(OP_JUMP, cont)
            self.mark(done)
            self.emit(OP_POPBLOCK, 1)
            self.mark(brk)
            self.iters -= 1
            self.blocks.pop()
        elif t == "while":
            brk, cont, done = self.lbl(), self.lbl(), self.lbl()
            self.emit(OP_LOOP, (brk, cont, 0))
            self.blocks.append({"kind": "loop", "brk": brk, "cont": cont,
                                "iters": self.iters, "iters_cont": self.iters})
            self.mark(cont)
            self.emit(OP_SET_LINE, ln)   # the condition belongs to this line
            self.expr(n[1])
            self.emit(OP_JF, done)
            self.block(n[2])
            self.emit(OP_JUMP, cont)
            self.mark(done)
            self.emit(OP_POPBLOCK, 1)
            self.mark(brk)
            self.blocks.pop()
        elif t == "forever":
            brk, cont = self.lbl(), self.lbl()
            self.emit(OP_LOOP, (brk, cont, 0))
            self.blocks.append({"kind": "loop", "brk": brk, "cont": cont,
                                "iters": self.iters, "iters_cont": self.iters})
            self.mark(cont)
            self.block(n[1])
            self.emit(OP_JUMP, cont)
            self.mark(brk)   # only reachable through 'stop'
            self.blocks.pop()
        elif t == "for":
            _, name, seq, step, backwards, iname, body = n
            self._countloop(ln, body,
                            lambda: (self.expr(seq),
                                     self.emit(OP_FORPREP, (step, backwards))),
                            (1, name, iname))
        elif t == "rangefor":
            _, name, start, stop, step, body = n
            self._countloop(ln, body,
                            lambda: (self.expr(start), self.expr(stop),
                                     self.expr(step), self.emit(OP_RANGEPREP)),
                            (2, name))
        elif t == "pairfor":
            _, n1, n2, seq, body = n
            self._countloop(ln, body,
                            lambda: (self.expr(seq), self.emit(OP_PAIRPREP)),
                            (3, n1, n2))
        elif t == "multifor":
            _, specs, body = n
            brk = self.lbl()
            loop_arg_idx = len(self.ins)
            self.emit(OP_LOOP, None)   # patched once we know the targets
            self.blocks.append({"kind": "loop", "brk": brk, "cont": None,
                                "iters": self.iters,
                                "iters_cont": self.iters + len(specs)})
            nexts, dones = [], []
            for spec in specs:
                self.emit(OP_SET_LINE, ln)   # specs re-evaluate on each pass
                if spec[0] == "range":
                    _, name, start, stop, step = spec
                    self.expr(start); self.expr(stop); self.expr(step)
                    self.emit(OP_RANGEPREP)
                    binder = (2, name)
                elif spec[0] == "pairs":
                    _, a, b, seq = spec
                    self.expr(seq)
                    self.emit(OP_PAIRPREP)
                    binder = (3, a, b)
                else:
                    _, name, seq, step, backwards, iname = spec
                    self.expr(seq)
                    self.emit(OP_FORPREP, (step, backwards))
                    binder = (1, name, iname)
                self.iters += 1
                nxt, done = self.lbl(), self.lbl()
                nexts.append(nxt)
                dones.append(done)
                self.mark(nxt)
                self.emit(OP_FORNEXT, (done,) + binder)
            cont = nexts[-1]   # 'skip' moves to the next combination
            self.blocks[-1]["cont"] = cont
            self.ins[loop_arg_idx][1] = (brk, cont, len(specs))
            self.block(body)
            self.emit(OP_JUMP, cont)
            for k in range(len(specs) - 1, -1, -1):
                self.mark(dones[k])
                if k > 0:
                    self.emit(OP_JUMP, nexts[k - 1])
                else:
                    self.emit(OP_POPBLOCK, 1)
            self.mark(brk)
            self.iters -= len(specs)
            self.blocks.pop()
        elif t == "readlines":
            self.expr(n[2])
            self.emit(OP_READLINES, n[1])
        elif t == "save":
            self.expr(n[1])
            self.expr(n[2])
            self.emit(OP_SAVE)
        elif t == "def":
            _, name, params, body = n
            code = _compile_fn_code(params, body, name)
            self.emit(OP_DEF, (name, params, code))
        elif t == "exprstmt":
            self.expr(n[1])
            self.emit(OP_POP)
        elif t == "stop":
            self._loopjump(is_stop=True)
        elif t == "skip":
            self._loopjump(is_stop=False)
        elif t == "exit":
            self.emit(OP_EXIT)
        elif t == "return":
            self.expr(n[1])
            self.emit(OP_RETURN)
        else:
            raise RuntimeError(f"Cannot compile statement {n}")

    def _countloop(self, ln, body, prep, binder):
        """Shared shape of for / rangefor / pairfor: one prepared iterator."""
        brk, cont, done = self.lbl(), self.lbl(), self.lbl()
        self.emit(OP_LOOP, (brk, cont, 1))
        self.blocks.append({"kind": "loop", "brk": brk, "cont": cont,
                            "iters": self.iters, "iters_cont": self.iters + 1})
        prep()
        self.iters += 1
        self.mark(cont)
        self.emit(OP_FORNEXT, (done,) + binder)
        self.block(body)
        self.emit(OP_JUMP, cont)
        self.mark(done)
        self.emit(OP_POPBLOCK, 1)
        self.mark(brk)
        self.iters -= 1
        self.blocks.pop()

    def _loopjump(self, is_stop):
        """Lower 'stop'/'skip' to a jump when the loop is in this chunk.
        Outside any loop they raise, exactly like the tree-walker, so a
        'stop' inside a function can still end the caller's loop."""
        loop = None
        above = 0
        for b in reversed(self.blocks):
            if b["kind"] == "loop":
                loop = b
                break
            above += 1
        if loop is None:
            self.emit(OP_RAISESTOP if is_stop else OP_RAISESKIP)
            return
        if is_stop:
            drop_iters = self.iters - loop["iters"]
            drop_blocks = above + 1        # open trys plus the loop itself
            target = loop["brk"]
        else:
            drop_iters = self.iters - loop["iters_cont"]
            drop_blocks = above            # open trys only; the loop lives on
            target = loop["cont"]
        if drop_iters:
            self.emit(OP_POPITERS, drop_iters)
        if drop_blocks:
            self.emit(OP_POPBLOCK, drop_blocks)
        self.emit(OP_JUMP, target)

    # ---- expressions ----

    def expr(self, n):
        t = n[0]
        if t == "num":
            self.emit(OP_CONST, n[1])
        elif t == "str":
            if INTERP_RE.search(n[1]):
                self.emit(OP_STR, n[1])
            else:
                self.emit(OP_CONST, n[1])
        elif t == "var":
            self.emit(OP_LOAD, n[1])
        elif t == "bin":
            self.expr(n[2])
            self.expr(n[3])
            self.emit(OP_BIN, n[1])
        elif t == "cmp":
            self.expr(n[2])
            self.expr(n[3])
            self.emit(OP_CMP, n[1])
        elif t == "logic":
            _, op, a, b = n
            if op == "not":
                self.expr(a)
                self.emit(OP_NOT)
            else:
                end = self.lbl()
                self.expr(a)
                self.emit(OP_BOOL)
                self.emit(OP_JF_KEEP if op == "and" else OP_JT_KEEP, end)
                self.emit(OP_POP)
                self.expr(b)
                self.emit(OP_BOOL)
                self.mark(end)
        elif t == "index":
            self.expr(n[1])
            self.expr(n[2])
            self.emit(OP_INDEX)
        elif t == "list":
            for x in n[1]:
                self.expr(x)
            self.emit(OP_LIST, len(n[1]))
        elif t == "dict":
            for k, v in n[1]:
                self.expr(k)
                self.expr(v)
            self.emit(OP_MAP_LIT, len(n[1]))
        elif t == "member":
            self.expr(n[1])
            self.expr(n[2])
            self.emit(OP_MEMBER)
        elif t == "startswith":
            self.expr(n[1])
            self.expr(n[2])
            self.emit(OP_STARTS)
        elif t == "endswith":
            self.expr(n[1])
            self.expr(n[2])
            self.emit(OP_ENDS)
        elif t == "between":
            self.expr(n[1])
            self.expr(n[2])
            self.expr(n[3])
            self.emit(OP_BETWEEN)
        elif t == "divisible":
            self.expr(n[1])
            self.expr(n[2])
            self.emit(OP_DIVISIBLE)
        elif t == "parity":
            self.expr(n[1])
            self.emit(OP_PARITY, n[2])
        elif t == "typeis":
            self.expr(n[1])
            self.emit(OP_TYPEIS, n[2])
        elif t == "isempty":
            self.expr(n[1])
            self.emit(OP_ISEMPTY)
        elif t == "filter":
            self.expr(n[1])
            self.emit(OP_FILTER, _compile_expr_code(n[2], "filter condition"))
        elif t == "map":
            _, name, src, body = n
            self.expr(src)
            self.emit(OP_MAPEXPR,
                      (name, _compile_expr_code(body, "map expression")))
        elif t == "call":
            _, name, args = n
            for a in args:
                self.expr(a)
            self.emit(OP_BUILTIN, (name, len(args)))
        elif t == "userfn":
            _, name, args = n
            for a in args:
                self.expr(a)
            self.emit(OP_CALL, (name, len(args)))
        else:
            raise RuntimeError(f"Cannot compile expression {n}")


def _compile_expr_code(node, name):
    c = _Compiler()
    c.expr(node)
    c.emit(OP_EXPREND)
    return c.finalize(name)


def _compile_fn_code(params, body, name):
    c = _Compiler()
    c.block(body)
    c.emit(OP_CONST, None)
    c.emit(OP_RETURN)
    return c.finalize(name)


def compile_program(ast):
    c = _Compiler()
    c.block(ast[1])
    c.emit(OP_HALT)
    return c.finalize("main")


# ---- the virtual machine ----

class _Frame:
    __slots__ = ("code", "ip", "stack", "blocks", "iters", "line",
                 "params", "saved")

    def __init__(self, code, line=0):
        self.code = code
        self.ip = 0
        self.stack = []
        self.blocks = []   # open ('try', ...) / ('loop', ...) entries
        self.iters = []    # live loop iterators
        self.line = line
        self.params = None
        self.saved = None


def _range_iter(start, stop, step):
    direction = 1 if stop >= start else -1
    v = start
    while (direction > 0 and v <= stop) or (direction < 0 and v >= stop):
        yield v
        v += direction * step


def _restore_params(f, env):
    if f.params is not None:
        for k in f.params:
            if k in f.saved:
                env[k] = f.saved[k]
            else:
                env.pop(k, None)


_WRAPPABLE = (NameError, RuntimeError, ValueError, TypeError,
              ZeroDivisionError, IndexError, KeyError)


def _vm_unwind(frames, env, exc):
    """Route an exception: errors go to the nearest 'try', stop/skip to
    the nearest loop (crossing function frames, restoring their params,
    exactly like the tree-walker's exception propagation)."""
    if isinstance(exc, PlainRuntimeError):
        kind = 0
    elif isinstance(exc, StopLoop):
        kind = 1
    elif isinstance(exc, SkipLoop):
        kind = 2
    elif isinstance(exc, _WRAPPABLE):
        f = frames[-1]
        ln = _line_at(f.code, f.ip - 1, f.line)
        exc = PlainRuntimeError(f"Line {ln}: {exc}")
        kind = 0
    else:
        raise exc
    while frames:
        f = frames[-1]
        blocks = f.blocks
        while blocks:
            b = blocks.pop()
            if kind == 0 and b[0] == "try":
                del f.iters[b[2]:]
                del f.stack[b[3]:]
                env["error"] = str(exc)
                f.ip = b[1]
                return f
            if kind == 1 and b[0] == "loop":
                del f.iters[b[3]:]
                del f.stack[b[5]:]
                f.ip = b[1]
                return f
            if kind == 2 and b[0] == "loop":
                blocks.append(b)   # the loop keeps going
                del f.iters[b[4]:]
                del f.stack[b[5]:]
                f.ip = b[2]
                return f
        _restore_params(f, env)
        frames.pop()
    raise exc


def _vm_exec(frames, env):
    f = frames[-1]
    env_get = env.get
    _MISSING = _SENTINEL
    while True:
        instrs = f.code.instrs
        stack = f.stack
        ip = f.ip
        try:
            while True:
                op, arg = instrs[ip]
                ip += 1
                if op == OP_CONST:
                    stack.append(arg)
                elif op == OP_LOAD:
                    v = env_get(arg, _MISSING)
                    if v is _MISSING:
                        raise NameError(f"You haven't set '{arg}' yet.")
                    stack.append(v)
                elif op == OP_JF:
                    if not stack.pop():
                        ip = arg
                elif op == OP_BIN:
                    b = stack.pop()
                    stack[-1] = bin_op(arg, stack[-1], b)
                elif op == OP_BIN_LC:
                    name, c, bop = arg
                    v = env_get(name, _MISSING)
                    if v is _MISSING:
                        raise NameError(f"You haven't set '{name}' yet.")
                    stack.append(bin_op(bop, v, c))
                elif op == OP_CMP_LC:
                    name, c, cop = arg
                    v = env_get(name, _MISSING)
                    if v is _MISSING:
                        raise NameError(f"You haven't set '{name}' yet.")
                    stack.append(cmp_op(cop, v, c))
                elif op == OP_ADDVAR_C:
                    name, c = arg
                    cur = env_get(name, 0)
                    if isinstance(cur, list):
                        cur.append(c)
                    else:
                        env[name] = add_vals(cur, c)
                elif op == OP_FORNEXT:
                    try:
                        v = next(f.iters[-1])
                    except StopIteration:
                        f.iters.pop()
                        ip = arg[0]
                        continue
                    kind = arg[1]
                    if kind == 1:       # for each item [at position i]
                        env[arg[2]] = v[1]
                        if arg[3]:
                            env[arg[3]] = v[0]
                    elif kind == 2:     # for each n from a to b
                        env[arg[2]] = v
                    elif kind == 3:     # for each pair of a and b
                        env[arg[2]] = v[0]
                        env[arg[3]] = v[1]
                elif op == OP_CMP:
                    b = stack.pop()
                    stack[-1] = cmp_op(arg, stack[-1], b)
                elif op == OP_STORE:
                    env[arg] = stack.pop()
                elif op == OP_JUMP:
                    ip = arg
                elif op == OP_LOAD0:
                    stack.append(env_get(arg, 0))
                elif op == OP_ADDVAR:
                    v = stack.pop()
                    cur = stack.pop()
                    if isinstance(cur, list):
                        cur.append(v)
                    else:
                        env[arg] = add_vals(cur, v)
                elif op == OP_INDEX:
                    k = stack.pop()
                    stack[-1] = index_get(stack[-1], k)
                elif op == OP_BUILTIN:
                    name, argc = arg
                    if argc:
                        vals = stack[-argc:]
                        del stack[-argc:]
                    else:
                        vals = []
                    stack.append(call_builtin(name, vals))
                elif op == OP_CALL:
                    name, argc = arg
                    if argc:
                        args = stack[-argc:]
                        del stack[-argc:]
                    else:
                        args = []
                    fns = env.setdefault("__fns__", {})
                    if name not in fns:
                        raise NameError(f"No function named '{name}'.")
                    params, fcode = fns[name]
                    if len(args) != len(params):
                        raise RuntimeError(
                            f"'{name}' wants {len(params)} value(s), "
                            f"got {len(args)}.")
                    if len(frames) >= MAX_FRAMES:
                        raise RuntimeError("maximum recursion depth exceeded")
                    saved = {k: env[k] for k in params if k in env}
                    for k, v in zip(params, args):
                        env[k] = v
                    nf = _Frame(fcode)
                    nf.params = params
                    nf.saved = saved
                    f.ip = ip
                    frames.append(nf)
                    f = nf
                    break
                elif op == OP_RETURN:
                    val = stack.pop()
                    _restore_params(f, env)
                    frames.pop()
                    if not frames:
                        raise ReturnValue(val)
                    f = frames[-1]
                    f.stack.append(val)
                    break
                elif op == OP_STR:
                    stack.append(INTERP_RE.sub(
                        lambda m: to_str(env[m.group(1)])
                        if m.group(1) in env else m.group(0), arg))
                elif op == OP_BOOL:
                    stack[-1] = bool(stack[-1])
                elif op == OP_NOT:
                    stack[-1] = not stack[-1]
                elif op == OP_JF_KEEP:
                    if not stack[-1]:
                        ip = arg
                elif op == OP_JT_KEEP:
                    if stack[-1]:
                        ip = arg
                elif op == OP_POP:
                    stack.pop()
                elif op == OP_PRINT:
                    print(to_str(stack.pop()))
                elif op == OP_BIN_LL:
                    n1, n2, bop = arg
                    a = env_get(n1, _MISSING)
                    if a is _MISSING:
                        raise NameError(f"You haven't set '{n1}' yet.")
                    b = env_get(n2, _MISSING)
                    if b is _MISSING:
                        raise NameError(f"You haven't set '{n2}' yet.")
                    stack.append(bin_op(bop, a, b))
                elif op == OP_BIN_XC:
                    stack[-1] = bin_op(arg[0], stack[-1], arg[1])
                elif op == OP_CMP_XC:
                    stack[-1] = cmp_op(arg[0], stack[-1], arg[1])
                elif op == OP_SETPATH:
                    name, nkeys = arg
                    val = stack.pop()
                    keys = stack[-nkeys:]
                    del stack[-nkeys:]
                    path_set(env, name, keys, val)
                elif op == OP_ADDPATH or op == OP_SUBPATH:
                    name, nkeys = arg
                    v = stack.pop()
                    keys = stack[-nkeys:]
                    del stack[-nkeys:]
                    container = path_get(env, name, keys[:-1])
                    key = keys[-1]
                    adding = op == OP_ADDPATH
                    if isinstance(container, dict):
                        cur = container.get(key, 0)
                        if adding and isinstance(cur, list):
                            cur.append(v)
                        else:
                            container[key] = add_vals(cur, v) if adding else cur - v
                    elif isinstance(container, list):
                        i = int(key)
                        if i < 1 or i > len(container):
                            raise RuntimeError(
                                f"Position {i} is outside the list "
                                f"(it has {len(container)} items).")
                        cur = container[i - 1]
                        if adding and isinstance(cur, list):
                            cur.append(v)
                        else:
                            container[i - 1] = add_vals(cur, v) if adding else cur - v
                    else:
                        raise RuntimeError(f"'{name}' is not a list or lookup.")
                elif op == OP_CHECKVAR:
                    if arg not in env:
                        raise NameError(f"You haven't set '{arg}' yet.")
                elif op == OP_MEMBER:
                    container = stack.pop()
                    stack[-1] = stack[-1] in container
                elif op == OP_DIVISIBLE:
                    b = stack.pop()
                    stack[-1] = stack[-1] % b == 0
                elif op == OP_LOOP:
                    f.blocks.append(("loop", arg[0], arg[1],
                                     len(f.iters), len(f.iters) + arg[2],
                                     len(stack)))
                elif op == OP_TRY:
                    f.blocks.append(("try", arg, len(f.iters), len(stack)))
                elif op == OP_POPBLOCK:
                    del f.blocks[-arg:]
                elif op == OP_POPITERS:
                    del f.iters[-arg:]
                elif op == OP_FORPREP:
                    step, backwards = arg
                    seq = list(stack.pop())
                    indexed = list(enumerate(seq, 1))
                    if backwards:
                        indexed.reverse()
                    f.iters.append(iter(indexed[::step]))
                elif op == OP_RANGEPREP:
                    s3 = stack.pop()
                    s2 = stack.pop()
                    s1 = stack.pop()
                    f.iters.append(_range_iter(int(s1), int(s2), int(s3)))
                elif op == OP_PAIRPREP:
                    seq = list(stack.pop())
                    f.iters.append(iter(list(zip(seq, seq[1:]))))
                elif op == OP_REPEATPREP:
                    f.iters.append(iter(range(int(stack.pop()))))
                elif op == OP_LIST:
                    if arg:
                        vals = stack[-arg:]
                        del stack[-arg:]
                        stack.append(vals)
                    else:
                        stack.append([])
                elif op == OP_MAP_LIT:
                    d = {}
                    if arg:
                        kv = stack[-2 * arg:]
                        del stack[-2 * arg:]
                        for i in range(0, 2 * arg, 2):
                            d[kv[i]] = kv[i + 1]
                    stack.append(d)
                elif op == OP_STARTS:
                    b = stack.pop()
                    stack[-1] = to_str(stack[-1]).startswith(to_str(b))
                elif op == OP_ENDS:
                    b = stack.pop()
                    stack[-1] = to_str(stack[-1]).endswith(to_str(b))
                elif op == OP_BETWEEN:
                    hi = stack.pop()
                    lo = stack.pop()
                    stack[-1] = lo <= stack[-1] <= hi
                elif op == OP_PARITY:
                    stack[-1] = int(stack[-1]) % 2 == arg
                elif op == OP_TYPEIS:
                    v = stack.pop()
                    if arg == "number":
                        r = isinstance(v, (int, float)) and not isinstance(v, bool)
                    elif arg == "text":
                        r = isinstance(v, str)
                    elif arg == "list":
                        r = isinstance(v, list)
                    else:
                        r = isinstance(v, dict)
                    stack.append(r)
                elif op == OP_ISEMPTY:
                    stack[-1] = len(stack[-1]) == 0
                elif op == OP_FILTER:
                    src = stack.pop()
                    result = []
                    had = "it" in env
                    saved = env.get("it")
                    line = _line_at(f.code, ip - 1, f.line)
                    try:
                        for x in src:
                            env["it"] = x
                            if _vm_exec([_Frame(arg, line)], env):
                                result.append(x)
                    finally:
                        if had:
                            env["it"] = saved
                        else:
                            env.pop("it", None)
                    stack.append(result)
                elif op == OP_MAPEXPR:
                    name, code = arg
                    src = stack.pop()
                    result = []
                    had = name in env
                    saved = env.get(name)
                    line = _line_at(f.code, ip - 1, f.line)
                    try:
                        for x in src:
                            env[name] = x
                            result.append(_vm_exec([_Frame(code, line)], env))
                    finally:
                        if had:
                            env[name] = saved
                        else:
                            env.pop(name, None)
                    stack.append(result)
                elif op == OP_EXPECT:
                    b = stack.pop()
                    a = stack.pop()
                    if a == b:
                        print(f"OK: got {to_str(a)}")
                    else:
                        print(f"FAIL: expected {to_str(b)}, got {to_str(a)}")
                        env["__fails__"] = env.get("__fails__", 0) + 1
                elif op == OP_ASK:
                    name, has_prompt = arg
                    prompt = "> "
                    if has_prompt:
                        prompt = to_str(stack.pop()) + " "
                    env[name] = coerce(input(prompt))
                elif op == OP_WAIT:
                    time.sleep(float(stack.pop()))
                elif op == OP_STOREMULTI:
                    v = stack.pop()
                    if not isinstance(v, list):
                        raise RuntimeError(
                            f"To fill {len(arg)} names at once, the value must "
                            f"be a list, but this is {kind_name(v)}.")
                    if len(v) != len(arg):
                        raise RuntimeError(
                            f"Expected {len(arg)} values for "
                            f"{', '.join(arg)} but the list has {len(v)}.")
                    for nm, val in zip(arg, v):
                        env[nm] = val
                elif op == OP_SUBVAR:
                    v = stack.pop()
                    env[arg] = stack.pop() - v
                elif op == OP_REMOVEVAL:
                    v = stack.pop()
                    target = env.get(arg)
                    if isinstance(target, list) and v in target:
                        target.remove(v)
                    elif isinstance(target, dict) and v in target:
                        del target[v]
                elif op == OP_REMOVEPOS:
                    name, which, dest = arg
                    lst = env.get(name)
                    if not isinstance(lst, list):
                        raise RuntimeError(f"'{name}' is not a list.")
                    if not lst:
                        raise RuntimeError(f"'{name}' is already empty.")
                    v = lst.pop(0) if which == "first" else lst.pop()
                    if dest:
                        env[dest] = v
                elif op == OP_LISTFETCH:
                    lst = env.get(arg)
                    if not isinstance(lst, list):
                        raise RuntimeError(f"'{arg}' is not a list.")
                    stack.append(lst)
                elif op == OP_REMOVEAT:
                    i = int(stack.pop())
                    lst = stack.pop()
                    if i < 1 or i > len(lst):
                        raise RuntimeError(
                            f"Position {i} is outside the list "
                            f"(it has {len(lst)} items).")
                    v = lst.pop(i - 1)
                    if arg:
                        env[arg] = v
                elif op == OP_INSERTIDX:
                    i = int(stack.pop())
                    lst = stack[-1]
                    if i < 1 or i > len(lst) + 1:
                        raise RuntimeError(
                            f"Position {i} is outside the list (you can "
                            f"insert at 1 to {len(lst) + 1}).")
                    stack.append(i)
                elif op == OP_INSERTDO:
                    val = stack.pop()
                    i = stack.pop()
                    lst = stack.pop()
                    lst.insert(i - 1, val)
                elif op == OP_SWAP:
                    n1, nk1, n2, nk2 = arg
                    if nk2:
                        k2 = stack[-nk2:]
                        del stack[-nk2:]
                    else:
                        k2 = []
                    if nk1:
                        k1 = stack[-nk1:]
                        del stack[-nk1:]
                    else:
                        k1 = []
                    v1 = path_get(env, n1, k1)
                    v2 = path_get(env, n2, k2)
                    path_set(env, n1, k1, v2)
                    path_set(env, n2, k2, v1)
                elif op == OP_SORT:
                    name, desc, keycode = arg
                    lst = env.get(name)
                    if not isinstance(lst, list):
                        raise RuntimeError(
                            f"'{name}' is not a list, so it can't be sorted.")
                    if keycode is None:
                        lst.sort(reverse=desc)
                    else:
                        had = "it" in env
                        saved = env.get("it")
                        line = _line_at(f.code, ip - 1, f.line)

                        def sort_key(x):
                            env["it"] = x
                            return _vm_exec([_Frame(keycode, line)], env)

                        try:
                            lst.sort(key=sort_key, reverse=desc)
                        finally:
                            if had:
                                env["it"] = saved
                            else:
                                env.pop("it", None)
                elif op == OP_REVERSE:
                    env[arg].reverse()
                elif op == OP_READLINES:
                    path = stack.pop()
                    with open(path, "r", encoding="utf-8-sig") as fh:
                        env[arg] = [line.rstrip("\n") for line in fh]
                elif op == OP_SAVE:
                    path = stack.pop()
                    val = stack.pop()
                    with open(path, "w", encoding="utf-8") as fh:
                        if isinstance(val, list):
                            fh.write("\n".join(to_str(x) for x in val))
                        else:
                            fh.write(to_str(val))
                elif op == OP_DEF:
                    name, params, code = arg
                    env.setdefault("__fns__", {})[name] = (params, code)
                elif op == OP_RAISESTOP:
                    raise StopLoop()
                elif op == OP_RAISESKIP:
                    raise SkipLoop()
                elif op == OP_EXIT:
                    sys.exit(0)
                elif op == OP_HALT:
                    return None
                elif op == OP_EXPREND:
                    return stack.pop()
        except Exception as e:
            f.ip = ip   # so the unwinder can read the failing line
            f = _vm_unwind(frames, env, e)


def run_bytecode(ast, env):
    """Compile the parsed program and run it on the VM."""
    _vm_exec([_Frame(compile_program(ast))], env)


# ---- disassembler (--disasm, and the web demo's bytecode view) ----

def _fmt_arg(op, arg, queue):
    if arg is None:
        return ""
    if op == OP_DEF:
        name, params, code = arg
        queue.append((f"function {name}({', '.join(params)})", code))
        return f"{name}({', '.join(params)})"
    if op == OP_FILTER:
        queue.append((f"{arg.name} #{len(queue)}", arg))
        return f"<{arg.name} #{len(queue) - 1}>"
    if op == OP_MAPEXPR:
        name, code = arg
        queue.append((f"{code.name} #{len(queue)}", code))
        return f"{name}, <{code.name} #{len(queue) - 1}>"
    if op == OP_SORT:
        name, desc, keycode = arg
        text = f"{name}{', backwards' if desc else ''}"
        if keycode is not None:
            queue.append((f"sort key #{len(queue)}", keycode))
            text += f", <sort key #{len(queue) - 1}>"
        return text
    if op == OP_LOOP:
        return f"break->{arg[0]} continue->{arg[1]} iters={arg[2]}"
    if op == OP_FORNEXT:
        names = ", ".join(str(a) for a in arg[2:] if a)
        kind = {0: "repeat", 1: "each", 2: "range", 3: "pair"}[arg[1]]
        return f"{kind} {names} done->{arg[0]}".replace("repeat  ", "repeat ")
    return repr(arg)


def disassemble(code):
    """Human-readable listing of a compiled program and everything in it."""
    out = []
    queue = [("main", code)]
    seen = 0
    while seen < len(queue):
        title, c = queue[seen]
        seen += 1
        if out:
            out.append("")
        out.append(f"== {title} ==")
        out.append(" line    ip  instruction")
        last_ln = None
        for i, (op, arg) in enumerate(c.instrs):
            ln = _line_at(c, i, 0)
            ln_text = str(ln) if ln and ln != last_ln else ""
            last_ln = ln
            out.append(f"{ln_text:>5} {i:>5}  {OP_NAMES[op]:<11} "
                       f"{_fmt_arg(op, arg, queue)}".rstrip())
    return "\n".join(out)


def disassemble_source(src):
    return disassemble(compile_program(parse(tokenize(src))))


# ============================================================
# 5. ENTRY POINT
# ============================================================

def repl(engine="vm"):
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
            if engine == "ast":
                run(ast, env)
            else:
                run_bytecode(ast, env)
        except (NameError, RuntimeError, ZeroDivisionError, PlainRuntimeError) as e:
            print(f"Oops: {e}")
        except ReturnValue:
            print("Oops: 'give back' only works inside a function.")
        buf = ""


def main():
    sys.setrecursionlimit(6000)
    # Never let an unprintable character crash the program's own output.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except AttributeError:
            pass
    # python plain.py program.plain --trace  narrates every line as it runs
    for flag in ("--trace", "--explain"):
        if flag in sys.argv:
            TRACE["on"] = True
            sys.argv.remove(flag)
    # python plain.py program.plain --disasm  prints the bytecode and exits
    disasm = False
    if "--disasm" in sys.argv:
        disasm = True
        sys.argv.remove("--disasm")
    # --engine=vm (default) runs the bytecode VM; --engine=ast the tree-walker
    engine = "vm"
    for a in list(sys.argv):
        if a.startswith("--engine="):
            engine = a.split("=", 1)[1]
            sys.argv.remove(a)
    if "--engine" in sys.argv:
        i = sys.argv.index("--engine")
        if i + 1 < len(sys.argv):
            engine = sys.argv[i + 1]
            del sys.argv[i:i + 2]
        else:
            sys.argv.remove("--engine")
    if engine not in ("ast", "vm"):
        print(f"Oops: --engine must be 'ast' or 'vm', not '{engine}'.")
        sys.exit(1)
    if TRACE["on"]:
        engine = "ast"   # trace narration walks the tree
    if len(sys.argv) < 2:
        repl(engine)
        return
    with open(sys.argv[1], "r", encoding="utf-8-sig") as f:
        src = f.read()
    if disasm:
        try:
            print(disassemble_source(src))
        except SyntaxError as e:
            print(f"Oops: {e}")
            sys.exit(1)
        return
    TRACE["src"] = src.splitlines()
    env = {}
    try:
        ast = parse(tokenize(src))
        if engine == "ast":
            run(ast, env)
        else:
            run_bytecode(ast, env)
    except (SyntaxError, PlainRuntimeError, NameError, RuntimeError) as e:
        print(f"Oops: {e}")
        sys.exit(1)
    except ReturnValue:
        print("Oops: 'give back' only works inside a function.")
        sys.exit(1)
    if env.get("__fails__"):
        sys.exit(1)


if __name__ == "__main__":
    main()
