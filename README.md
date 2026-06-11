# Plain

![CI](https://github.com/TylerJForstrom/Plain/actions/workflows/ci.yml/badge.svg)

Plain is a programming language that reads like English. It sits between
block coding and Python: real typed-out code, but with words instead of
symbols. The goal is that a normal person can learn it in an afternoon and
use it to solve real problems — including LeetCode-style puzzles.

```
to two_sum with nums and target
    set seen to empty lookup
    set i to 0
    for each n in nums
        add 1 to i
        set need to target minus n
        if seen has need then
            give back list of seen at need and i
        end
        set seen at n to i
    end
    give back empty list
end
```

That's a real, working solution to LeetCode #1 (Two Sum).

And when you're ready for symbols, Plain accepts those too — every word
has an operator twin, and you can mix them freely:

```
to two_sum with nums and target
    set seen to {}
    set i to 0
    for each n in nums
        i += 1
        set need to target - n
        if seen has need then
            give back [seen[need], i]
        end
        seen[n] = i
    end
    give back []
end
```

## Try it in your browser

The `web/` folder is a full demo site — a playground that runs the real
interpreter in your browser (via Pyodide), practice problems with explained
solutions, and searchable docs with a built-in assistant. It's completely
static and free to host:

- **Deploy:** connect this repo to Netlify — `netlify.toml` already points
  the build at `web/` and copies the interpreter in.
- **Run locally:** `python -m http.server 8765 --directory web` after
  copying `plain.py` into `web/`, then open `http://localhost:8765`.

## Running Plain

You need Python installed. Then:

```
python plain.py program.plain              # run a file (bytecode VM)
python plain.py program.plain --trace      # narrate every line as it runs
python plain.py program.plain --disasm     # show the compiled bytecode
python plain.py program.plain --engine=ast # use the tree-walking interpreter
python plain.py                            # interactive mode (type code, see results)
python plain.py tests.plain                # run the language's own test suite
```

`--trace` is made for learning — it shows each line as it runs and how
variables change, so you can watch a loop accumulate step by step.

The `examples/` folder has solved LeetCode problems to learn from, from
easy (fizzbuzz, two_sum, palindrome) up to medium (number_of_islands,
merge_intervals). The `vscode-plain/` folder is a VS Code extension that
colors `.plain` files (see its README for the one-line install).

## Under the hood: a bytecode compiler and VM

Plain has two engines that are guaranteed to behave identically:

- **The bytecode VM (default).** Programs are parsed to an AST, the AST
  is compiled to flat bytecode (one instruction list per function plus
  the main program), and a stack-based virtual machine executes it with
  explicit call frames. `stop`, `skip`, and `give back` compile to plain
  jumps — no exceptions on the hot path. Each compiled chunk carries a
  line-number table (like CPython's), so tracking the current line costs
  nothing until an error actually needs to report one. A peephole
  optimizer then folds constant expressions (`2 + 3 * 4` becomes one
  `CONST 14`), collapses jump-to-jump chains, deletes dead jumps, and
  fuses hot instruction pairs into superinstructions (`add 1 to i` is a
  single `ADDVAR_C` instead of three instructions). Folding is skipped
  whenever the operation would raise, so runtime errors still happen at
  runtime, on the right line — the differential suite and the fuzzer
  hold the optimizer to the exact same behavior as the tree-walker.
- **The tree-walking interpreter** (`--engine=ast`). The original
  engine: it walks the AST directly and uses Python exceptions for
  control flow. `--trace` always uses this engine, because its recursive
  shape matches the line-by-line narration.

Identical behavior isn't an aspiration, it's a test gate, three layers
deep — and CI runs all of it on every push:

- `python difftest.py` runs the full test suite, the demo script, every
  example program, and ~35 corner cases (error messages with line
  numbers, `try`/`otherwise`, `stop` that crosses a function call,
  parameter shadowing, and so on) through **both** engines and requires
  byte-for-byte identical output and exit codes.
- `python fuzz.py` generates hundreds of random valid Plain programs —
  bounded loops, functions, lookups, error paths and all — and requires
  the same byte-for-byte agreement. Any divergence is saved to
  `fuzz_failures/` with its seed for replay.
- Both engines share one implementation of the arithmetic, comparison,
  and built-in functions, so error text can't drift between them.

`--disasm` prints the human-readable bytecode for any program — the web
playground has a "Show bytecode" toggle that does the same thing.

### The step debugger

The playground's **Debug** button runs your program one statement at a
time on the VM: the current line is highlighted in the editor, and a
panel shows every variable, the call stack, and the next few bytecode
instructions. Step into a function call and watch the call stack grow
and the parameters appear; step out and watch them restore. Debug
compiles keep each statement boundary in the bytecode as a pause
marker; the VM stops there, reports the world, and resumes exactly
where it left off — across loops, `try` blocks, and function frames.
The tree-walking interpreter couldn't pause like this (it would be
stuck halfway down a Python call stack), which is a nice demonstration
of why bytecode VMs exist.

### Measured speed

Three engines, one story: tree-walker → bytecode VM → optimizing VM.
Measured by CI on a quiet GitHub Actions runner (Python 3.12, best of
7 interleaved rounds per engine; programs parsed once, output
suppressed during timing; compiling took ~0.1–0.2 ms per workload).
CI posts this table as a commit comment on every push to main, so the
numbers below are reproducible, not hand-picked:

| workload               | AST engine | bytecode VM | + optimizer | speedup |
| ---------------------- | ---------: | ----------: | ----------: | ------: |
| fib(18), recursive     |   122.3 ms |     29.0 ms |     25.5 ms |   4.79x |
| loop arithmetic (200k) |   373.8 ms |    281.1 ms |    252.7 ms |   1.48x |
| string building (20k)  |    50.8 ms |     36.6 ms |     33.2 ms |   1.53x |
| list ops (40k)         |   122.6 ms |     96.2 ms |     90.5 ms |   1.35x |
| lookup tally (30k)     |    80.1 ms |     74.8 ms |     74.5 ms |   1.07x |

Honest summary: the VM shines on function-call-heavy code (calls become
frame pushes instead of nested Python calls plus exception-based
returns), the optimizer adds a further 5–10% nearly everywhere, and
statement-heavy dictionary code is the smallest win because both
engines spend that time in the same shared runtime helpers. Rerun
`bench.py` to reproduce locally.

## The basics

### Variables and math

```
set price to 10                 # or:  price = 10
set tax to price multiplied by 0.08
add 5 to price                  # or:  price += 5
subtract 2 from price           # or:  price -= 2
print price
```

Math, in words or symbols — use whichever you like:

| words                          | symbols  |
| ------------------------------ | -------- |
| `plus`                         | `+`      |
| `minus`                        | `-`      |
| `multiplied by`                | `*`      |
| `divided by`                   | `/`      |
| `remainder of A divided by B`  | `A % B`  |
| —                              | `A // B` (divide, round down) |
| —                              | `A ^ B` (power), `N squared`  |

Plus: `square root of`, `absolute value of`, `round`, `floor of`,
`middle of A and B` (whole-number midpoint — handy for binary search),
`bigger of A and B`, `smaller of A and B`,
`negative 5` or `-5`, `random from 1 to 100`.

Parentheses group things, just like in math class: `set m to (low + high) / 2`.

### Printing and text

```
set name to "Ada"
print "Hello, [name]!"          # square brackets insert a variable
print uppercase of name
print letters of name           # [A, d, a]
print the first 2 of name       # "Ad"
print name at 1                 # "A"  (positions start at 1)
set parts to split "a,b,c" by ","
print join parts with " - "
print replace "l" with "w" in "hello"   # "hewwo"
print trim of "  hi  "                  # "hi"
print count of "s" in "mississippi"     # 4
print items 2 to 4 of "plainly"         # "lai"
```

### Lists

```
set nums to list of 3 and 1 and 2      # or:  set nums to [3, 1, 2]
set nums to numbers from 1 to 10       # a ready-made counting list
add 5 to nums                   # append
remove 1 from nums              # delete a value
sort nums                       # smallest first
sort nums backwards             # biggest first
sort pairs by it[2]             # sort by any expression of 'it'
reverse nums

print nums at 2                 # or:  print nums[2]   (positions start at 1)
print item 2 of nums            # same thing, different words
set item 2 of nums to 99        # or:  nums[2] = 99
print position of 99 in nums    # where is it? (0 means not there)

print count of nums
print count of 2 in nums        # how many times 2 appears
print items 2 to 4 of nums      # slice by positions
print sum of nums
print biggest in nums
print smallest in nums
print average of nums
print first of nums
print last of nums
print the first 3 of nums       # slice
print the last 2 of nums
```

Rearrange a list in place:

```
swap nums[1] and nums[3]        # works on plain variables too: swap a and b
insert 99 into nums at 2
remove item 2 from nums
remove the last from nums into top      # pop - perfect for a stack
remove the first from nums into front   # dequeue - perfect for a queue
```

Transform or filter a whole list in one line:

```
set doubled to each n in nums as n * 2
set big to only the ones in nums where it is greater than 10
```

### Lookups (key → value tables)

A lookup remembers a value for each key — the tool behind most fast
LeetCode solutions (Python calls it a dictionary).

```
set ages to empty lookup        # or:  set ages to {}
set ages at "amy" to 30         # or:  ages["amy"] = 30
print ages at "amy"             # or:  print ages["amy"]
add 1 to ages at "amy"          # or:  ages["amy"] += 1
remove "amy" from ages

set table to lookup of "x" being 1 and "y" being 2
set table to {"x": 1, "y": 2}   # same thing in symbols
print keys of table             # [x, y]
print values of table           # [1, 2]
print count of table

if ages has "amy" then
    print "found her"
end
```

Counting things — the trick behind many fast solutions — is two lines,
because adding to a missing key starts it at 0:

```
set tally to {}
for each w in split text by " "
    add 1 to tally at w
end
set ranked to keys of tally
sort ranked by tally at it backwards    # most common first
```

### Grids (lists inside lists)

For 2D problems — boards, mazes, matrices — Plain is simpler than Python:

```
set board to grid of 3 by 4 filled with 0    # 3 rows, 4 columns, all 0
board[2][3] = "X"                            # row 2, column 3
print board[2][3]
print count of board                         # how many rows
print count of board[1]                      # how many columns

set tiny to [[1, 2], [3, 4]]                 # write one out directly
set item 1 of item 2 of tiny to 9            # the word way: tiny[2][1] = 9
```

Long lists can be split across lines — newlines inside `[ ]`, `{ }`,
and `( )` don't end the statement.

### Conditions

Words or symbols, your choice:

```
if score is equal to 100 then ... end        # or:  if score == 100 then
if score is not equal to 0 then ... end      # or:  if score != 0 then
if score is greater than 50 then ... end     # or:  if score > 50 then
if score is less than 50 then ... end        # or:  if score < 50 then
if score is at least 90 then ... end         # or:  if score >= 90 then
if score is at most 100 then ... end         # or:  if score <= 100 then
if score is between 1 and 10 then ... end
if n is divisible by 3 then ... end
if n is odd then ... end
if n is even then ... end
if n is positive then ... end
if n is negative then ... end
if bag is empty then ... end
if color is one of ["red", "blue"] then ... end
if "amy" is in ages then ... end
if word contains "ell" then ... end
if word starts with "he" then ... end
if word ends with "lo" then ... end
if seen has n then ... end
if word does not contain "z" then ... end    # also: does not have /
if done then ... end                         #   start with / end with
if not done then ... end
if answer is a number then ... end           # also: is text / is a list /
if answer is not text then ... end           #   is a lookup
```

Combine with `and` / `or` (parentheses welcome), branch with `otherwise`,
and chain checks with `otherwise if` — one single `end` closes the chain:

```
if grade is at least 90 then
    print "A"
otherwise if grade is at least 80 then
    print "B"
otherwise
    print "keep going"
end
```

### Loops

```
repeat 3 times ... end
for each n from 1 to 10 ... end
for each n from 0 to 100 by 5 ... end
for each item in mylist ... end
for each item in mylist going backwards ... end
for every other item in mylist ... end
while total is less than 100 ... end         # or:  while total < 100
forever ... end
```

Inside any loop: `stop` breaks out, `skip` jumps to the next round.

Need to know where you are? Ask for the position (counts 1, 2, 3, ...):

```
for each ch at position i in letters of word
    print "letter [i] is [ch]"
end
```

Comparing neighbors (is it sorted? where are the gaps?) has its own loop:

```
for each pair of x and y in [1, 4, 9]     # visits (1,4) then (4,9)
    print y - x
end
```

**Nested loops in one line** — something even Python can't do this simply.
Join loops with `and`; one `end` closes them all:

```
for each r from 1 to 3 and c from 1 to 3
    print "row [r], column [c]"
end

for each row in board and cell in row       # the inner loop can use
    print cell                               # the outer loop's variable
end
```

In a combined loop, `skip` moves to the next combination and `stop`
leaves the whole thing.

### Functions

```
to greet with someone
    print "Hello, [someone]!"
end

to add_pair with x and y
    give back x plus y
end

call greet with "World"
set total to call add_pair with 3 and 4
set total to add_pair(3, 4)         # symbol style works too
```

Functions can call themselves (recursion):

```
to fact with n
    if n is at most 1 then
        give back 1
    end
    give back n * fact(n - 1)
end
```

And they can give back several values at once — catch them with
`set ... and ...`:

```
to minmax with nums
    give back smallest in nums and biggest in nums
end

set lo and hi to minmax([4, 9, 1])
```

(That unpacking works with any list: `set a and b to [b, a]` swaps.)

### Checking your answers

`expect` is a built-in answer checker — perfect for testing a solution
against a problem's examples:

```
expect two_sum([2, 7, 11, 15], 9) to equal [1, 2]
```

Prints `OK` when right, `FAIL` (with both values) when wrong, and the
program reports failure to the system so it works in test scripts.

### When things might fail

Wrap risky steps in `try`; if anything goes wrong the `otherwise` part
runs, and `error` holds the message:

```
ask answer with "Type a number:"
try
    print 100 / answer
otherwise
    print "That didn't work: [error]"
end
```

### Asking, waiting, files

```
ask favorite                          # read typed input into a variable
ask name with "What is your name?"    # ask with your own prompt
wait 2 seconds
save mylist to "out.txt"
read lines from "data.txt" into rows
print arguments                       # values typed after the program name
put 5 into x                          # another way to say: set x to 5
exit                                  # end the program right away
```

## When something goes wrong

Plain tells you the line and what it thinks you meant:

```
Oops: Line 3: I don't understand 'sett'. Did you mean 'set'?
Oops: Line 7: You haven't set 'totl' yet.
Oops: Line 2: Position 7 is outside the list (it has 3 items).
Oops: Line 4: You can't divide by zero.
```

## Tips

1. **Positions start at 1.** The first item of a list is `item 1` or
   `nums[1]`, like counting in real life.
2. **Use parentheses when math gets long.** Word-builtins like
   `count of` and `floor of` grab only the very next value, so write
   `round of (x / 2)` when you mean the whole thing.
3. **Words that belong to the language** (like `set`, `count`, `item`,
   `list`, `value`) can't be used as variable names. If you hit a
   confusing error, try a more specific name like `my_item` or
   `total_count`.
