# Plain

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

## Running Plain

You need Python installed. Then:

```
python plain.py program.plain     # run a file
python plain.py                   # interactive mode (type code, see results)
python plain.py tests.plain       # run the language's own test suite
```

The `examples/` folder has solved LeetCode problems to learn from:
two_sum, binary_search, fizzbuzz, palindrome, valid_anagram,
contains_duplicate, max_subarray, and climbing_stairs.

## The basics

### Variables and math

```
set price to 10
set tax to price multiplied by 0.08
add 5 to price
subtract 2 from price
print price
```

Math words: `plus`, `minus`, `multiplied by`, `divided by`,
`remainder of A divided by B`, `square root of`, `absolute value of`,
`round`, `floor of`, `middle of A and B` (whole-number midpoint),
`negative 5`, `random from 1 to 100`.

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
```

### Lists

```
set nums to list of 3 and 1 and 2
add 5 to nums                   # append
remove 1 from nums              # delete a value
sort nums                       # smallest first
sort nums backwards             # biggest first
reverse nums

print nums at 2                 # read position 2 (positions start at 1)
print item 2 of nums            # same thing, different words
set item 2 of nums to 99        # replace position 2
print position of 99 in nums    # where is it? (0 means not there)

print count of nums
print sum of nums
print biggest in nums
print smallest in nums
print average of nums
print first of nums
print last of nums
print the first 3 of nums       # slice
print the last 2 of nums
```

Transform or filter a whole list in one line:

```
set doubled to each n in nums as n multiplied by 2
set big to only the ones in nums where it is greater than 10
```

### Lookups (key → value tables)

A lookup remembers a value for each key — the tool behind most fast
LeetCode solutions (Python calls it a dictionary).

```
set ages to empty lookup
set ages at "amy" to 30
print ages at "amy"
remove "amy" from ages

set table to lookup of "x" being 1 and "y" being 2
print keys of table             # [x, y]
print values of table           # [1, 2]
print count of table

if ages has "amy" then
    print "found her"
end
```

### Conditions

```
if score is equal to 100 then ... end
if score is not equal to 0 then ... end
if score is greater than 50 then ... end
if score is less than 50 then ... end
if score is at least 90 then ... end          # >=
if score is at most 100 then ... end          # <=
if score is between 1 and 10 then ... end
if n is divisible by 3 then ... end
if n is positive then ... end
if n is negative then ... end
if bag is empty then ... end
if color is one of list of "red" and "blue" then ... end
if "amy" is in ages then ... end
if word contains "ell" then ... end
if word starts with "he" then ... end
if word ends with "lo" then ... end
if ages has "amy" then ... end
```

Combine with `and` / `or`, branch with `otherwise`, and chain checks
with `otherwise if` (one single `end` closes the whole chain):

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
while total is less than 100 ... end
forever ... end
```

Inside any loop: `stop` breaks out, `skip` jumps to the next round.

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
```

Functions can call themselves (recursion):

```
to fact with n
    if n is at most 1 then
        give back 1
    end
    set m to n minus 1
    give back n multiplied by call fact with m
end
```

### Checking your answers

`expect` is a built-in answer checker — perfect for testing a solution
against a problem's examples:

```
expect call two_sum with nums and 9 to equal list of 1 and 2
```

Prints `OK` when right, `FAIL` (with both values) when wrong.

### Asking, waiting, files

```
ask favorite                          # read typed input into a variable
wait 2 seconds
save mylist to "out.txt"
read lines from "data.txt" into rows
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

## Three habits that keep Plain plain

1. **One step per line.** Plain has no parentheses, so don't stack math
   into one line. Instead of guessing how `round of x divided by 2`
   groups, write `set half to x divided by 2` then `round half`.
   Word-builtins like `count of` and `floor of` grab only the very next
   value.
2. **Put lists in variables before calling functions.** Write
   `set nums to list of 1 and 2` then `call f with nums and 9` — if you
   inline the list, the `and`s blur together.
3. **Positions start at 1.** The first item of a list is `item 1`,
   like counting in real life.

Words that belong to the language (like `set`, `count`, `item`, `list`,
`value`) can't be used as variable names — if you hit a confusing error,
try a more specific name like `my_item` or `total_count`.
