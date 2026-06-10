/* The complete Plain language reference. Each entry powers the searchable
   docs AND the docs assistant chatbot. `kw` holds extra search words. */
const DOCS = [

/* ---------------- Basics ---------------- */
{ cat: "Basics", title: "Variables",
  syntax: "set price to 10\nprice = 10\nput 10 into price",
  desc: "Create or change a variable. All three forms do the same thing — words or symbols, your choice. Variables hold numbers, text, lists, or lookups.",
  example: 'set name to "Ada"\nset age to 36\nage = age + 1\nprint "[name] is [age]"',
  kw: "assign create variable store value declare equals make" },

{ cat: "Basics", title: "Printing & putting variables in text",
  syntax: 'print VALUE\nsay VALUE\nprint "Hello, [name]!"',
  desc: "print (or say) writes a line to the output. Inside quotes, square brackets insert a variable's value into the text.",
  example: 'set score to 97\nprint "You scored [score] points!"',
  kw: "output display show write console log text interpolation say string format" },

{ cat: "Basics", title: "Comments",
  syntax: "# anything after a hash sign is ignored",
  desc: "Start a line (or the end of a line) with # to leave a note for humans. Plain skips it completely.",
  example: "# This counts to three\nfor each n from 1 to 3\n    print n   # one number per line\nend",
  kw: "comment note ignore hash remark documentation" },

{ cat: "Basics", title: "Adding and subtracting in place",
  syntax: "add 5 to total\nsubtract 2 from total\ntotal += 5\ntotal -= 2",
  desc: "Change a number without retyping it. add also works on lists (it appends) and on lookup keys (a missing key starts at 0 — great for counting).",
  example: "set total to 10\nadd 5 to total\ntotal -= 3\nprint total",
  kw: "increment decrement increase decrease accumulate plus equals counter" },

{ cat: "Basics", title: "Checking answers with expect",
  syntax: "expect VALUE to equal VALUE",
  desc: "A built-in answer checker. Prints OK when the two values match and FAIL (showing both) when they don't. Perfect for testing a solution against a problem's examples.",
  example: "expect 2 + 2 to equal 4\nexpect join [\"a\", \"b\"] with \"-\" to equal \"a-b\"",
  kw: "test assert verify check answer expect ok fail unit testing" },

{ cat: "Basics", title: "Explain mode (trace)",
  syntax: "python plain.py program.plain --trace",
  desc: "Narrates every line as it runs and shows variables changing — watch a loop accumulate step by step. In this playground, tick \"Explain each step\" next to the Run button.",
  example: "set total to 0\nfor each n in [1, 2, 3]\n    add n to total\nend",
  kw: "trace debug explain step learn watch narrate walkthrough" },

/* ---------------- Math ---------------- */
{ cat: "Math", title: "Arithmetic",
  syntax: "a plus b        a + b\na minus b       a - b\na multiplied by b   a * b\na divided by b      a / b",
  desc: "Words and symbols both work, and you can mix them. Parentheses group things just like in math class: (2 + 3) * 4.",
  example: "set subtotal to 40\nset tax to subtotal * 0.08\nprint subtotal + tax",
  kw: "add subtract multiply divide plus minus times calculation operator parentheses brackets" },

{ cat: "Math", title: "Remainder & whole-number division",
  syntax: "remainder of A divided by B\nA % B\nA // B",
  desc: "remainder (or %) gives what's left over after dividing — the key to even/odd checks and wrap-around problems. // divides and rounds down to a whole number.",
  example: "expect remainder of 10 divided by 3 to equal 1\nexpect 10 % 3 to equal 1\nexpect 7 // 2 to equal 3",
  kw: "modulo mod remainder integer division floor divide leftover percent" },

{ cat: "Math", title: "Powers & squares",
  syntax: "A ^ B\nN squared\nsquare root of N",
  desc: "Raise numbers to a power with ^, square them with the word squared, and undo it with square root of.",
  example: "expect 2 ^ 10 to equal 1024\nexpect 5 squared to equal 25\nexpect square root of 81 to equal 9",
  kw: "exponent power square root sqrt raise" },

{ cat: "Math", title: "Rounding",
  syntax: "round N\nfloor of N\nabsolute value of N",
  desc: "round goes to the nearest whole number (halves round up, like school math). floor of always rounds down. absolute value of drops the minus sign.",
  example: "expect round 4.6 to equal 5\nexpect floor of 4.9 to equal 4\nexpect absolute value of -7 to equal 7",
  kw: "round floor ceiling truncate absolute abs nearest decimal" },

{ cat: "Math", title: "middle, bigger & smaller of two",
  syntax: "middle of A and B\nbigger of A and B\nsmaller of A and B",
  desc: "middle gives the whole-number midpoint (made for binary search). bigger and smaller pick between two values — like max and min for exactly two things.",
  example: "expect middle of 1 and 10 to equal 5\nexpect bigger of 3 and 7 to equal 7\nexpect smaller of -2 and -5 to equal -5",
  kw: "max min maximum minimum midpoint middle average two compare binary search" },

{ cat: "Math", title: "Random numbers & picks",
  syntax: "random from 1 to 100\nrandom in LIST",
  desc: "Get a random whole number in a range, or pick a random item from a list.",
  example: 'set roll to random from 1 to 6\nprint "You rolled [roll]"',
  kw: "random dice chance pick choose shuffle luck generate" },

{ cat: "Math", title: "Turning text into a number",
  syntax: 'value of TEXT',
  desc: "Converts text like \"42\" into the number 42 so you can do math with it. Pairs well with ask, which reads typed input.",
  example: 'set answer to value of "42"\nexpect answer + 1 to equal 43',
  kw: "convert parse number text string int float cast input" },

/* ---------------- Text ---------------- */
{ cat: "Text", title: "Letters & length",
  syntax: "letters of TEXT\ncount of TEXT\nTEXT at N",
  desc: "letters of breaks text into a list of characters. count of measures its length. Positions start at 1, so \"cat\" at 1 is \"c\".",
  example: 'set word to "plain"\nexpect count of word to equal 5\nexpect word at 1 to equal "p"\nprint letters of word',
  kw: "characters chars string length size letter index split apart" },

{ cat: "Text", title: "Uppercase, lowercase & trim",
  syntax: "uppercase of TEXT\nlowercase of TEXT\ntrim of TEXT",
  desc: "Change the case of text, or strip the spaces off both ends with trim.",
  example: 'expect uppercase of "hi" to equal "HI"\nexpect trim of "  hi  " to equal "hi"',
  kw: "capital upper lower case strip whitespace spaces clean" },

{ cat: "Text", title: "Split & join",
  syntax: 'split TEXT by SEPARATOR\njoin LIST with SEPARATOR',
  desc: "split chops text into a list wherever the separator appears. join glues a list back into one piece of text.",
  example: 'set parts to split "red,green,blue" by ","\nexpect count of parts to equal 3\nexpect join parts with " | " to equal "red | green | blue"',
  kw: "split join csv comma separate combine glue parse words" },

{ cat: "Text", title: "Replace",
  syntax: 'replace OLD with NEW in TEXT',
  desc: "Swaps every appearance of one piece of text for another. Also works on lists, replacing matching items.",
  example: 'expect replace "l" with "w" in "hello" to equal "hewwo"\nexpect replace 2 with 9 in [1, 2, 3] to equal [1, 9, 3]',
  kw: "replace substitute swap change find and replace" },

{ cat: "Text", title: "Counting appearances",
  syntax: "count of X in TEXT\ncount of X in LIST",
  desc: "How many times does something appear? Works on text (counting a smaller piece of text) and lists (counting matching items).",
  example: 'expect count of "s" in "mississippi" to equal 4\nexpect count of 2 in [1, 2, 2, 3] to equal 2',
  kw: "count occurrences appearances frequency how many times tally" },

{ cat: "Text", title: "Slicing text & lists",
  syntax: "the first N of X\nthe last N of X\nitems A to B of X",
  desc: "Grab a piece: the first 3 of, the last 2 of, or a middle stretch with items 2 to 4 of. All three work on text and lists alike.",
  example: 'expect the first 3 of "plainly" to equal "pla"\nexpect items 2 to 4 of [10, 20, 30, 40, 50] to equal [20, 30, 40]',
  kw: "slice substring portion part first last middle range cut section" },

/* ---------------- Lists ---------------- */
{ cat: "Lists", title: "Making lists",
  syntax: 'set nums to [3, 1, 2]\nset nums to list of 3 and 1 and 2\nset nums to empty list   # or []\nset nums to numbers from 1 to 10',
  desc: "A list holds values in order. Write one with brackets or words; numbers from builds a ready-made counting list (by 2 steps it, 10 to 1 counts down). Lists can nest: [[1, 2], [3, 4]].",
  example: "set nums to numbers from 2 to 10 by 2\nprint nums\nexpect sum of nums to equal 30",
  kw: "list array create make collection sequence range numbers brackets nested" },

{ cat: "Lists", title: "Reading & changing positions",
  syntax: "nums[2]        nums at 2        item 2 of nums\nnums[2] = 9    set item 2 of nums to 9",
  desc: "Positions start at 1, like counting in real life. Read any position three ways; assign with = or words. Deep positions work too: board[2][3].",
  example: "set nums to [10, 20, 30]\nexpect nums[2] to equal 20\nnums[2] = 99\nexpect nums to equal [10, 99, 30]",
  kw: "index access element item position get set bracket subscript first" },

{ cat: "Lists", title: "Adding & removing items",
  syntax: "add X to LIST\nremove X from LIST\ninsert X into LIST at N\nremove item N from LIST",
  desc: "add appends to the end. remove X deletes the first matching value; remove item N deletes by position. insert squeezes a value in at a position.",
  example: "set names to [\"amy\", \"bob\"]\nadd \"carl\" to names\nremove \"bob\" from names\ninsert \"zoe\" into names at 1\nprint names",
  kw: "append push delete remove insert pop element add item" },

{ cat: "Lists", title: "Stacks & queues",
  syntax: "remove the last from LIST into VAR\nremove the first from LIST into VAR",
  desc: "remove the last ... into pops the top of a stack into a variable. remove the first ... into takes from the front of a queue. The into part is optional if you just want it gone.",
  example: 'set pile to ["a", "b", "c"]\nremove the last from pile into top\nexpect top to equal "c"\nexpect pile to equal ["a", "b"]',
  kw: "stack queue pop push dequeue lifo fifo top front last first" },

{ cat: "Lists", title: "Sorting & reversing",
  syntax: "sort LIST\nsort LIST backwards\nsort LIST by EXPRESSION\nreverse LIST",
  desc: "sort puts the smallest first (backwards for biggest first). sort ... by orders by any expression of it — each item in turn: sort pairs by it[2], sort words by count of it.",
  example: 'set words to ["bee", "a", "spider"]\nsort words by count of it\nexpect words to equal ["a", "bee", "spider"]',
  kw: "sort order arrange ascending descending reverse key custom rank" },

{ cat: "Lists", title: "List math: sum, count, biggest…",
  syntax: "count of LIST\nsum of LIST\naverage of LIST\nbiggest in LIST\nsmallest in LIST\nfirst of LIST\nlast of LIST",
  desc: "One-word answers about a whole list. count of also works on text and lookups.",
  example: "set nums to [4, 1, 7]\nexpect sum of nums to equal 12\nexpect biggest in nums to equal 7\nexpect average of nums to equal 4",
  kw: "sum total count length max min maximum minimum average mean aggregate biggest smallest" },

{ cat: "Lists", title: "Finding things",
  syntax: "position of X in LIST\nif LIST contains X then\nif X is in LIST then\nif X is one of LIST then",
  desc: "position of tells you where something lives (1-based; 0 means not there). contains / is in / is one of answer yes-or-no. position of also finds text inside text.",
  example: 'set nums to [5, 8, 2]\nexpect position of 8 in nums to equal 2\nif nums contains 2 then\n    print "found it"\nend',
  kw: "find search locate index of contains includes membership exists position where" },

{ cat: "Lists", title: "Transform & filter (map and filter)",
  syntax: "each X in LIST as EXPRESSION\nonly the ones in LIST where CONDITION",
  desc: "Build a new list in one line. The first transforms every item; the second keeps only items passing a test (use it for the current item).",
  example: "set nums to [1, 2, 3, 4]\nset doubled to each n in nums as n * 2\nset big to only the ones in nums where it is greater than 2\nprint doubled\nprint big",
  kw: "map filter transform select comprehension apply every keep where" },

{ cat: "Lists", title: "Swap two values",
  syntax: "swap A and B\nswap nums[i] and nums[j]",
  desc: "Exchange two values in one line — plain variables or list positions. The heart of in-place array tricks like two-pointer reversal.",
  example: "set nums to [1, 2, 3]\nswap nums[1] and nums[3]\nexpect nums to equal [3, 2, 1]",
  kw: "swap exchange switch trade two pointer in place" },

{ cat: "Lists", title: "Several values at once",
  syntax: "set lo and hi to LIST\ngive back A and B",
  desc: "Unpack a list into several names in one line. Functions can give back several values the same way. set a and b to [b, a] is another way to swap.",
  example: "to minmax with nums\n    give back smallest in nums and biggest in nums\nend\nset lo and hi to minmax([4, 9, 1])\nexpect lo to equal 1\nexpect hi to equal 9",
  kw: "unpack destructure multiple return tuple two values assign both" },

/* ---------------- Lookups ---------------- */
{ cat: "Lookups", title: "Making lookups (key → value tables)",
  syntax: 'set ages to {}\nset ages to empty lookup\nset ages to {"amy": 30, "bob": 25}',
  desc: "A lookup remembers a value for every key — Python calls it a dictionary. It's the tool behind most fast solutions: checking \"have I seen this before?\" is instant.",
  example: 'set ages to {"amy": 30}\nages["bob"] = 25\nexpect count of ages to equal 2',
  kw: "dictionary map hash table key value object store lookup dict" },

{ cat: "Lookups", title: "Reading & writing keys",
  syntax: 'ages["amy"]        ages at "amy"\nages["amy"] = 30   set ages at "amy" to 30',
  desc: "Read or write any key with brackets or words. Reading a key that isn't there is an error — check first with has.",
  example: 'set scores to {}\nset scores at "level1" to 90\nexpect scores["level1"] to equal 90',
  kw: "get set key value read write access assign bracket" },

{ cat: "Lookups", title: "Does it have a key?",
  syntax: 'if LOOKUP has KEY then\nif KEY is in LOOKUP then\nif LOOKUP does not have KEY then',
  desc: "Check for a key before reading it. has is the natural phrasing for the classic \"have we seen this?\" pattern.",
  example: 'set seen to {}\nseen["x"] = true\nif seen has "x" then\n    print "already seen x"\nend',
  kw: "has contains key exists check membership in seen" },

{ cat: "Lookups", title: "Counting things (the tally pattern)",
  syntax: "add 1 to tally at KEY",
  desc: "Adding to a key that isn't there yet starts it at 0 — so counting how often each thing appears is just two lines. Rank the results with sort ... by.",
  example: 'set tally to {}\nfor each w in split "a b a c a" by " "\n    add 1 to tally at w\nend\nexpect tally["a"] to equal 3\nset ranked to keys of tally\nsort ranked by tally at it backwards\nexpect first of ranked to equal "a"',
  kw: "count tally frequency histogram occurrences word count top most common rank" },

{ cat: "Lookups", title: "Keys, values & removing",
  syntax: "keys of LOOKUP\nvalues of LOOKUP\nremove KEY from LOOKUP\ncount of LOOKUP",
  desc: "Get all the keys or all the values as lists (loop over them with for each), count the entries, or remove one by key.",
  example: 'set ages to {"amy": 30, "bob": 25}\nfor each name in keys of ages\n    print name\nend\nremove "bob" from ages\nexpect count of ages to equal 1',
  kw: "keys values iterate loop delete remove entries pairs" },

/* ---------------- Grids ---------------- */
{ cat: "Grids", title: "Grids (2D boards & matrices)",
  syntax: "set board to grid of 3 by 4 filled with 0\nset board to [[1, 2], [3, 4]]",
  desc: "grid of builds a board of rows and columns in one line — no tricks needed. Read and write cells with board[row][column]; rows and columns start at 1.",
  example: 'set board to grid of 2 by 3 filled with "."\nboard[1][2] = "X"\nprint board',
  kw: "grid matrix 2d board two dimensional rows columns nested table maze game" },

{ cat: "Grids", title: "Walking a grid",
  syntax: "for each r from 1 to count of board and c from 1 to count of board[r]\nfor each row in board and cell in row",
  desc: "Visit every cell with one combined loop — the second part can use the first part's variable. One end closes the whole thing.",
  example: "set board to [[1, 2], [3, 4]]\nset total to 0\nfor each row in board and cell in row\n    total += cell\nend\nexpect total to equal 10",
  kw: "iterate grid nested loop cells visit traverse 2d matrix every cell" },

/* ---------------- Conditions ---------------- */
{ cat: "Conditions", title: "If, otherwise & chains",
  syntax: "if CONDITION then\n    ...\notherwise if CONDITION then\n    ...\notherwise\n    ...\nend",
  desc: "Run code only when a condition holds. Chain checks with otherwise if; one single end closes the whole chain.",
  example: 'set grade to 85\nif grade is at least 90 then\n    print "A"\notherwise if grade is at least 80 then\n    print "B"\notherwise\n    print "keep going"\nend',
  kw: "if else elif branch condition decision otherwise then chain" },

{ cat: "Conditions", title: "Comparing values",
  syntax: "is equal to        ==  (or =)\nis not equal to    !=\nis greater than    >\nis less than       <\nis at least        >=\nis at most         <=",
  desc: "Every comparison has a word form and a symbol form — they're interchangeable.",
  example: 'set x to 7\nif x >= 5 and x is not equal to 6 then\n    print "x works"\nend',
  kw: "compare equal greater less than at least most comparison operator more fewer" },

{ cat: "Conditions", title: "Number checks",
  syntax: "is between A and B\nis divisible by N\nis odd / is even\nis positive / is negative",
  desc: "Plain-English checks for the most common number questions. All of them can be negated: is not even.",
  example: "for each n from 1 to 10\n    if n is even and n is divisible by 3 then\n        print n\n    end\nend",
  kw: "between divisible odd even positive negative range multiple parity" },

{ cat: "Conditions", title: "Text & list checks",
  syntax: "X contains Y\nX starts with Y\nX ends with Y\nX has KEY\nX does not contain Y",
  desc: "Yes-or-no questions about text, lists, and lookups. Negate any of them with does not.",
  example: 'set word to "hello"\nif word starts with "he" and word does not contain "z" then\n    print "looks good"\nend',
  kw: "contains starts ends with substring prefix suffix includes has negation not" },

{ cat: "Conditions", title: "Combining: and, or, not",
  syntax: "COND and COND\nCOND or COND\nnot COND\nif done then ...",
  desc: "Join conditions with and / or, flip one with not, and group with parentheses. A true/false variable works as a condition all by itself.",
  example: "set done to false\nif not done then\n    print \"still working\"\nend",
  kw: "and or not boolean logic combine true false group parentheses" },

{ cat: "Conditions", title: "Type checks",
  syntax: "is a number\nis text\nis a list\nis a lookup",
  desc: "Ask what kind of value something is — handy after reading input, since typed answers can be text or numbers.",
  example: 'set answer to value of "42"\nif answer is a number then\n    print answer * 2\nend',
  kw: "type check number text string list lookup kind is a typeof" },

/* ---------------- Loops ---------------- */
{ cat: "Loops", title: "Repeat & counting loops",
  syntax: "repeat N times ... end\nfor each n from 1 to 10 ... end\nfor each n from 0 to 100 by 5 ... end",
  desc: "repeat runs a block a fixed number of times. for each ... from counts through numbers (by sets the step; counting down works too).",
  example: "for each n from 5 to 1\n    print n\nend\nprint \"Liftoff!\"",
  kw: "loop repeat times range count for iterate step countdown" },

{ cat: "Loops", title: "Looping over a list",
  syntax: "for each item in LIST ... end\nfor each ch at position i in LIST\nfor each item in LIST going backwards\nfor every other item in LIST",
  desc: "Visit each item in turn. Add at position i to know where you are (counts 1, 2, 3…). Text works too — you'll get each letter.",
  example: 'for each ch at position i in letters of "hi!"\n    print "[i]: [ch]"\nend',
  kw: "foreach iterate loop list items index position enumerate backwards reverse each" },

{ cat: "Loops", title: "Neighbor pairs",
  syntax: "for each pair of x and y in LIST ... end",
  desc: "Visits neighbors together: (1st, 2nd), then (2nd, 3rd), and so on. Perfect for is-it-sorted checks and gap measurements.",
  example: "set gaps to []\nfor each pair of a and b in [1, 4, 9]\n    add b - a to gaps\nend\nexpect gaps to equal [3, 5]",
  kw: "pairs adjacent neighbors consecutive sliding window two sorted gaps" },

{ cat: "Loops", title: "Nested loops in one line",
  syntax: "for each r from 1 to 3 and c from 1 to 3 ... end",
  desc: "Join several loops with and — one end closes them all, and the later parts can use the earlier variables. skip moves to the next combination; stop leaves the whole thing.",
  example: 'for each a from 1 to 3 and b from 1 to 3\n    if a < b then\n        print "[a]-[b]"\n    end\nend',
  kw: "nested loop combined double inner outer combinations cross every pair" },

{ cat: "Loops", title: "While, forever, stop & skip",
  syntax: "while CONDITION ... end\nforever ... end\nstop\nskip",
  desc: "while keeps going as long as the condition holds. Inside any loop, stop breaks out completely and skip jumps to the next round.",
  example: "set n to 1\nwhile n < 100\n    n = n * 2\nend\nexpect n to equal 128",
  kw: "while loop forever infinite break continue stop skip until condition" },

/* ---------------- Functions ---------------- */
{ cat: "Functions", title: "Defining & calling functions",
  syntax: "to NAME with A and B\n    ...\n    give back VALUE\nend\n\ncall NAME with X and Y\nNAME(X, Y)",
  desc: "A function is a named recipe. Define it with to ... with, hand back a result with give back, and call it either way — words or parentheses.",
  example: 'to double with n\n    give back n * 2\nend\nexpect double(21) to equal 42\nexpect call double with 21 to equal 42',
  kw: "function define call return parameters arguments method procedure reuse give back" },

{ cat: "Functions", title: "Recursion (a function calling itself)",
  syntax: "to NAME with n\n    if ... then\n        give back ...   # the simple case\n    end\n    give back ... NAME(...) ...\nend",
  desc: "A function may call itself on a smaller piece of the problem. Always handle the simple case first so it knows when to stop.",
  example: "to fact with n\n    if n is at most 1 then\n        give back 1\n    end\n    give back n * fact(n - 1)\nend\nexpect fact(5) to equal 120",
  kw: "recursion recursive self call factorial fibonacci divide conquer base case" },

/* ---------------- Errors & input ---------------- */
{ cat: "Errors & input", title: "try / otherwise (when things might fail)",
  syntax: "try\n    ...\notherwise\n    ...\nend",
  desc: "If anything in the try part goes wrong, the otherwise part runs instead — and a variable named error holds the message. The program keeps going.",
  example: 'set nums to [1, 2]\ntry\n    print nums[99]\notherwise\n    print "That didn\'t work: [error]"\nend',
  kw: "error handling try catch exception fail crash rescue otherwise problem" },

{ cat: "Errors & input", title: "Asking for input",
  syntax: 'ask name\nask name with "What is your name?"',
  desc: "Reads typed input into a variable (numbers arrive as numbers). Note: the browser playground can't pause for typed input — use set instead while you're here.",
  example: '# In the terminal version:\n# ask age with "How old are you?"\nset age to 25\nprint "You are [age]"',
  kw: "input ask read user typed prompt question keyboard" },

{ cat: "Errors & input", title: "Files & the command line",
  syntax: 'save LIST to "out.txt"\nread lines from "data.txt" into rows\nprint arguments\nexit',
  desc: "Running Plain from the terminal, you can save values to a file, read a file line by line, grab values typed after the program name (arguments), and end early with exit.",
  example: 'set rows to ["line one", "line two"]\nsave rows to "out.txt"\nread lines from "out.txt" into loaded\nprint loaded',
  kw: "file save read write load lines arguments command line exit quit" },

{ cat: "Errors & input", title: "Reading error messages",
  syntax: "Oops: Line 3: I don't understand 'sett'. Did you mean 'set'?",
  desc: "Every error names the line it happened on and says what went wrong in plain words — typos get a \"did you mean\" hint, out-of-range positions say how big the list really is, and mixing text with math explains the fix.",
  example: "# Try running this to see a friendly error:\nset nums to [1, 2, 3]\nprint nums[7]",
  kw: "error message line number typo hint oops debug mistake wrong" },
];
