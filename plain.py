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
    if t == "cmp":
        _, op, a, b = node
        av, bv = evaluate(a, env), evaluate(b, env)
        try:
            return {"eq": av == bv, "ne": av != bv, "gt": av > bv,
                    "lt": av < bv, "ge": av >= bv, "le": av <= bv}[op]
        except TypeError:
            raise RuntimeError(
                f"You can't compare {kind_name(av)} with {kind_name(bv)}.") from None
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
        try:
            run(node[2], env)
        except PlainRuntimeError:
            raise
        except (NameError, RuntimeError, ValueError, TypeError,
                ZeroDivisionError, IndexError, KeyError) as e:
            raise PlainRuntimeError(f"Line {node[1]}: {e}") from None
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
    if len(sys.argv) < 2:
        repl()
        return
    with open(sys.argv[1], "r", encoding="utf-8-sig") as f:
        src = f.read()
    env = {}
    try:
        run(parse(tokenize(src)), env)
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
