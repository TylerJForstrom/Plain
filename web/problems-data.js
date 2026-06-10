/* Practice problems. Each has a starter (with self-checking expects),
   a hint, a full solution, and a step-by-step explanation. */
const PROBLEMS = [
{
  id: "fizzbuzz",
  title: "FizzBuzz",
  difficulty: "easy",
  blurb: "The classic warm-up: count to 15, with a twist on multiples of 3 and 5.",
  statement: "Count from 1 to 15 and print each number — but print Fizz for multiples of 3, Buzz for multiples of 5, and FizzBuzz for multiples of both.",
  starter: `# Print 1 to 15, but:
#   multiples of 3  -> "Fizz"
#   multiples of 5  -> "Buzz"
#   multiples of 15 -> "FizzBuzz"

for each n from 1 to 15
    # your code here
    print n
end`,
  hint: "Check for 15 first! If you check 3 first, the number 15 will print Fizz before you ever test for FizzBuzz. Use 'is divisible by' and chain the checks with 'otherwise if'.",
  solution: `for each n from 1 to 15
    if n is divisible by 15 then
        print "FizzBuzz"
    otherwise if n is divisible by 3 then
        print "Fizz"
    otherwise if n is divisible by 5 then
        print "Buzz"
    otherwise
        print n
    end
end`,
  explanation: [
    "The loop 'for each n from 1 to 15' counts n through every number, one at a time.",
    "The order of checks is the whole trick. 15 is divisible by 3 AND 5, so we must test 'divisible by 15' first — otherwise the 'divisible by 3' branch would grab it and print Fizz.",
    "'otherwise if' chains the checks so exactly one branch runs, and the final 'otherwise' catches plain numbers. One single 'end' closes the entire chain."
  ]
},
{
  id: "two-sum",
  title: "Two Sum",
  difficulty: "easy",
  blurb: "Find the two numbers that add up to a target — the most famous interview problem.",
  statement: "Given a list of numbers and a target, give back the positions of the two numbers that add up to the target. For [2, 7, 11, 15] and target 9, the answer is [1, 2] because 2 + 7 = 9.",
  starter: `to two_sum with nums and target
    # your code here
    give back []
end

expect two_sum([2, 7, 11, 15], 9) to equal [1, 2]
expect two_sum([3, 2, 4], 6) to equal [2, 3]`,
  hint: "Use a lookup as a memory: as you walk the list, store each number's position. For each number, the partner you NEED is (target minus the number) — check whether the lookup already has it.",
  solution: `to two_sum with nums and target
    set seen to {}
    for each n at position i in nums
        set need to target - n
        if seen has need then
            give back [seen[need], i]
        end
        seen[n] = i
    end
    give back []
end

expect two_sum([2, 7, 11, 15], 9) to equal [1, 2]
expect two_sum([3, 2, 4], 6) to equal [2, 3]`,
  explanation: [
    "'set seen to {}' creates an empty lookup — our memory of every number we've walked past, and where it lives.",
    "'for each n at position i' gives us each number AND its position at the same time.",
    "For each number, the partner that would complete the pair is 'target - n'. Asking 'if seen has need' is instant, no matter how long the list is — that's why this solution is fast.",
    "If the partner isn't there yet, 'seen[n] = i' files the current number away for later. The first time a pair completes, we give both positions back."
  ]
},
{
  id: "palindrome",
  title: "Valid Palindrome",
  difficulty: "easy",
  blurb: "Does a word read the same forwards and backwards?",
  statement: "Write a function that gives back true if a word reads the same forwards and backwards (ignore capital letters). \"Racecar\" is a palindrome; \"hello\" is not.",
  starter: `to is_palindrome with word
    # your code here
    give back false
end

expect is_palindrome("Racecar") to equal true
expect is_palindrome("level") to equal true
expect is_palindrome("hello") to equal false`,
  hint: "Make two lists of letters from the lowercase word. Reverse one of them. If the lists are equal, it's a palindrome.",
  solution: `to is_palindrome with word
    set chars to letters of lowercase of word
    set flipped to letters of lowercase of word
    reverse flipped
    if chars is equal to flipped then
        give back true
    end
    give back false
end

expect is_palindrome("Racecar") to equal true
expect is_palindrome("level") to equal true
expect is_palindrome("hello") to equal false`,
  explanation: [
    "'lowercase of word' makes capital letters irrelevant, so \"Racecar\" works.",
    "'letters of' turns the text into a list of characters we can manipulate.",
    "We build the same list twice and reverse one copy. If forward equals backward, the word is a palindrome — that's the literal definition, written as code."
  ]
},
{
  id: "contains-duplicate",
  title: "Contains Duplicate",
  difficulty: "easy",
  blurb: "Does any number appear more than once?",
  statement: "Give back true if any value appears at least twice in the list, false if every value is unique.",
  starter: `to has_duplicate with nums
    # your code here
    give back false
end

set a to [1, 2, 3, 1]
expect has_duplicate(a) to equal true
set b to [1, 2, 3, 4]
expect has_duplicate(b) to equal false`,
  hint: "Keep a lookup of everything you've seen. If the current number is already a key, you've found a duplicate.",
  solution: `to has_duplicate with nums
    set seen to {}
    for each n in nums
        if seen has n then
            give back true
        end
        seen[n] = true
    end
    give back false
end

set a to [1, 2, 3, 1]
expect has_duplicate(a) to equal true
set b to [1, 2, 3, 4]
expect has_duplicate(b) to equal false`,
  explanation: [
    "The lookup 'seen' acts as a guest list. Before letting each number in, we ask: has this one been here before?",
    "'if seen has n' answers instantly — this is the same trick as Two Sum, and it's the single most reused pattern in coding problems.",
    "The moment we find a repeat we 'give back true' and the function ends immediately. Only after surviving the whole list do we give back false."
  ]
},
{
  id: "best-time",
  title: "Best Time to Buy & Sell",
  difficulty: "easy",
  blurb: "One buy, one sell — what's the biggest possible profit?",
  statement: "Given prices day by day, find the biggest profit from buying on one day and selling on a later day. For [7, 1, 5, 3, 6, 4] the answer is 5 (buy at 1, sell at 6). If no profit is possible, the answer is 0.",
  starter: `to best_profit with prices
    # your code here
    give back 0
end

expect best_profit([7, 1, 5, 3, 6, 4]) to equal 5
expect best_profit([7, 6, 4, 3, 1]) to equal 0`,
  hint: "Walk the prices once, remembering the cheapest price so far. At each day, ask: how much would I make selling right now?",
  solution: `to best_profit with prices
    set cheapest to prices[1]
    set best to 0
    for each price in prices
        if price < cheapest then
            set cheapest to price
        otherwise if price - cheapest > best then
            set best to price - cheapest
        end
    end
    give back best
end

expect best_profit([7, 1, 5, 3, 6, 4]) to equal 5
expect best_profit([7, 6, 4, 3, 1]) to equal 0`,
  explanation: [
    "Two memories: 'cheapest' (the lowest price so far) and 'best' (the biggest profit so far).",
    "Each day is one of two things: a new cheapest price to buy at, or a chance to sell. 'price - cheapest' is today's profit if we sold now.",
    "Because we only ever sell at today's price against an EARLIER cheapest, the buy-before-sell rule is automatic. One pass through the list is all it takes."
  ]
},
{
  id: "valid-parentheses",
  title: "Valid Parentheses",
  difficulty: "easy",
  blurb: "Are the brackets balanced? Your first stack problem.",
  statement: "Given text made of ( ) [ ] { }, decide whether every opener closes in the right order. \"([])\" is valid; \"(]\" and \"([)]\" are not.",
  starter: `to is_valid with text
    # your code here
    give back false
end

expect is_valid("()[]{}") to equal true
expect is_valid("([{}])") to equal true
expect is_valid("(]") to equal false
expect is_valid("(((") to equal false`,
  hint: "Use a list as a pile (a stack): push openers on top. When a closer arrives, the top of the pile must be its matching opener — 'remove the last from pile into top' pops it off so you can check.",
  solution: `to is_valid with text
    set match to {")": "(", "]": "[", "}": "{"}
    set pile to []
    for each ch in letters of text
        if ch is one of ["(", "[", "{"] then
            add ch to pile
        otherwise if match has ch then
            if pile is empty then
                give back false
            end
            remove the last from pile into top
            if top != match[ch] then
                give back false
            end
        end
    end
    if pile is empty then
        give back true
    end
    give back false
end

expect is_valid("()[]{}") to equal true
expect is_valid("([{}])") to equal true
expect is_valid("(]") to equal false
expect is_valid("(((") to equal false`,
  explanation: [
    "The 'match' lookup pairs each closer with the opener it needs: a \")\" needs a \"(\" on top of the pile.",
    "Openers get stacked with 'add ch to pile'. The most recent unclosed opener is always on top — exactly the one the next closer must match.",
    "When a closer arrives, 'remove the last from pile into top' pops the top of the pile, and we check it against the lookup. Wrong opener (or an empty pile) means invalid.",
    "After the loop, the pile must be empty — leftover openers like \"(((\" mean something never got closed."
  ]
},
{
  id: "max-subarray",
  title: "Maximum Subarray",
  difficulty: "medium",
  blurb: "The biggest sum hiding inside a list — Kadane's famous trick.",
  statement: "Find the biggest sum you can get from a run of numbers sitting next to each other. For [-2, 1, -3, 4, -1, 2, 1, -5, 4] the answer is 6, from the run [4, -1, 2, 1].",
  starter: `to max_subarray with nums
    # your code here
    give back 0
end

set a to [-2, 1, -3, 4, -1, 2, 1, -5, 4]
expect max_subarray(a) to equal 6
set b to [-3, -1, -2]
expect max_subarray(b) to equal -1`,
  hint: "Keep a running sum as you walk the list. Whenever it climbs above your best, save it. Whenever it drops below zero, reset it to zero — a negative running start can only hurt whatever comes next.",
  solution: `to max_subarray with nums
    set best to nums[1]
    set current to 0
    for each n in nums
        add n to current
        if current > best then
            set best to current
        end
        if current is negative then
            set current to 0
        end
    end
    give back best
end

set a to [-2, 1, -3, 4, -1, 2, 1, -5, 4]
expect max_subarray(a) to equal 6
set b to [-3, -1, -2]
expect max_subarray(b) to equal -1`,
  explanation: [
    "'current' is the sum of the run we're building right now; 'best' is the best run we've ever seen.",
    "The insight: if the running sum goes negative, it can only drag down whatever comes next — so we abandon it and start fresh at 0. That one idea (Kadane's algorithm) turns a slow problem into a single pass.",
    "Starting 'best' at the first item (not 0) makes all-negative lists work: for [-3, -1, -2] the answer is -1, the least bad single number.",
    "Try the trace checkbox in the playground on this one — watching 'current' rise, fall, and reset makes the trick click."
  ]
},
{
  id: "merge-intervals",
  title: "Merge Intervals",
  difficulty: "medium",
  blurb: "Combine overlapping time spans — powered by sort-by.",
  statement: "Each pair is a start and an end. Merge every pair that overlaps. For [[1,3], [8,10], [2,6], [15,18]] the answer is [[1,6], [8,10], [15,18]] — because [1,3] and [2,6] overlap.",
  starter: `to merge_intervals with intervals
    # your code here
    give back intervals
end

set spans to [[1, 3], [8, 10], [2, 6], [15, 18]]
expect merge_intervals(spans) to equal [[1, 6], [8, 10], [15, 18]]
set spans to [[1, 4], [4, 5]]
expect merge_intervals(spans) to equal [[1, 5]]`,
  hint: "First 'sort intervals by it[1]' so they're in order of start. Then walk through: if a pair starts before the previous one ends, they overlap — stretch the previous pair instead of adding a new one.",
  solution: `to merge_intervals with intervals
    sort intervals by it[1]
    set merged to []
    for each pair in intervals
        if merged is empty then
            add pair to merged
        otherwise
            set previous to last of merged
            if pair[1] is at most previous[2] then
                previous[2] = bigger of previous[2] and pair[2]
            otherwise
                add pair to merged
            end
        end
    end
    give back merged
end

set spans to [[1, 3], [8, 10], [2, 6], [15, 18]]
expect merge_intervals(spans) to equal [[1, 6], [8, 10], [15, 18]]
set spans to [[1, 4], [4, 5]]
expect merge_intervals(spans) to equal [[1, 5]]`,
  explanation: [
    "'sort intervals by it[1]' lines the pairs up by their start value. After sorting, any overlap must be with the pair immediately before — that's what makes a single pass enough.",
    "We build the answer in 'merged'. For each pair, compare its start against the END of the last merged pair ('previous[2]').",
    "Overlap? Stretch the previous pair: its new end is 'bigger of' the two ends (handles a pair swallowed whole, like [2,3] inside [1,6]).",
    "No overlap? The pair starts a new group. Note that touching counts as overlap — [1,4] and [4,5] merge into [1,5] because of 'is at most'."
  ]
}
];
