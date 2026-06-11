/* Plain web demo: playground + practice + docs + docs assistant.
   Fully static — everything runs in the visitor's browser. */
(function () {
"use strict";

/* ========================= Tabs ========================= */
const panels = {
  playground: document.getElementById("tab-playground"),
  practice: document.getElementById("tab-practice"),
  docs: document.getElementById("tab-docs"),
};

function showTab(name) {
  if (!panels[name]) name = "playground";
  for (const [k, el] of Object.entries(panels)) el.classList.toggle("active", k === name);
  document.querySelectorAll(".tab").forEach((t) =>
    t.classList.toggle("active", t.dataset.tab === name));
  if (name === "playground" && editor && editor.refresh) setTimeout(() => editor.refresh(), 0);
}
window.addEventListener("hashchange", () => showTab(location.hash.replace("#", "")));

/* ========================= Editor ========================= */
const DEFAULT_PROGRAM = `# Welcome to Plain - code that reads like English.
# Press Run (or change anything and run again).

set names to ["world", "friend", "coder"]
for each name in names
    print "Hello, [name]!"
end

set nums to numbers from 1 to 10
set evens to only the ones in nums where it is even
print "The even ones: [evens]"
expect sum of evens to equal 30`;

let editor = null;
const host = document.getElementById("editor-host");
if (typeof CodeMirror !== "undefined") {
  editor = CodeMirror(host, {
    value: DEFAULT_PROGRAM,
    mode: "plain-lang",
    lineNumbers: true,
    indentUnit: 4,
    viewportMargin: Infinity,
  });
} else {
  const ta = document.createElement("textarea");
  ta.className = "fallback";
  ta.value = DEFAULT_PROGRAM;
  host.appendChild(ta);
  editor = { getValue: () => ta.value, setValue: (v) => (ta.value = v), refresh: () => {} };
}

/* Problem banner: keeps the selected practice problem visible while coding. */
const problemBanner = document.getElementById("problem-banner");
const bannerPill = document.getElementById("problem-banner-pill");
const bannerTitle = document.getElementById("problem-banner-title");
const bannerStatement = document.getElementById("problem-banner-statement");
const bannerHint = document.getElementById("problem-banner-hint-text");
document.getElementById("problem-banner-close").addEventListener("click", () => {
  problemBanner.hidden = true;
});

function showProblemBanner(p) {
  bannerPill.className = "pill " + p.difficulty;
  bannerPill.textContent = p.difficulty;
  bannerTitle.textContent = p.title;
  bannerStatement.textContent = p.statement;
  bannerHint.textContent = p.hint;
  bannerHint.closest("details").open = false;
  problemBanner.hidden = false;
}

function loadIntoEditor(code, problem) {
  if (problem) showProblemBanner(problem);
  else problemBanner.hidden = true;
  editor.setValue(code);
  location.hash = "playground";
  showTab("playground");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

/* ========================= Examples picker ========================= */
const EXAMPLES = {
  "Hello, Plain": DEFAULT_PROGRAM,
  "FizzBuzz": PROBLEMS.find((p) => p.id === "fizzbuzz").solution,
  "Two Sum (with a lookup)": PROBLEMS.find((p) => p.id === "two-sum").solution,
  "Word counting": `set text to "the cat and the dog and the bird"

set tally to {}
for each w in split text by " "
    add 1 to tally at w
end

set ranked to keys of tally
sort ranked by tally at it backwards

print "Most common words first:"
for each w in ranked
    set n to tally at w
    print "  [w] - [n] time(s)"
end`,
  "Grids (tic-tac-toe board)": `set board to grid of 3 by 3 filled with "."
board[1][1] = "X"
board[2][2] = "X"
board[3][3] = "X"
board[1][3] = "O"

for each row in board
    print join row with " "
end`,
  "Guess the dice (random)": `set roll to random from 1 to 6
print "The die shows [roll]."
if roll is at least 5 then
    print "Lucky!"
otherwise if roll is even then
    print "An even roll."
otherwise
    print "Better luck next time."
end`,
};
const picker = document.getElementById("example-picker");
for (const name of Object.keys(EXAMPLES)) {
  const opt = document.createElement("option");
  opt.value = name;
  opt.textContent = name;
  picker.appendChild(opt);
}
picker.addEventListener("change", () => {
  if (picker.value) loadIntoEditor(EXAMPLES[picker.value]);
  picker.value = "";
});

/* ========================= Runner (web worker) ========================= */
const outputEl = document.getElementById("output");
const runBtn = document.getElementById("run-btn");
const stopBtn = document.getElementById("stop-btn");
const traceCheck = document.getElementById("trace-check");
const bytecodeCheck = document.getElementById("bytecode-check");
let worker = null;
let engineReady = false;
let running = false;
let runTimeout = null;

function appendOutput(text, cls) {
  const span = document.createElement("span");
  if (cls) span.className = cls;
  span.textContent = text;
  outputEl.appendChild(span);
  outputEl.scrollTop = outputEl.scrollHeight;
}

function classifyLine(line) {
  if (line.startsWith("OK: ")) return "out-ok";
  if (line.startsWith("FAIL: ")) return "out-fail";
  if (line.startsWith("Oops: ")) return "out-err";
  if (line.startsWith("[line ") || line.startsWith("          ...")) return "out-trace";
  return null;
}

function bootWorker() {
  engineReady = false;
  runBtn.disabled = true;
  runBtn.textContent = "Loading engine…";
  debugBtn.disabled = true;
  worker = new Worker("runner.js");
  worker.onmessage = (e) => {
    const m = e.data;
    if (m.type === "ready") {
      engineReady = true;
      runBtn.disabled = false;
      runBtn.textContent = "▶ Run";
      debugBtn.disabled = false;
      if (outputEl.querySelector(".out-dim")) {
        outputEl.textContent = "";
        appendOutput("Ready! Press Run.\n", "out-dim");
      }
    } else if (m.type === "boot-error") {
      runBtn.textContent = "Engine failed to load";
      outputEl.textContent = "";
      appendOutput("The Python engine couldn't load (check your connection and refresh).\n" + m.text, "out-err");
    } else if (m.type === "out") {
      for (const line of m.text.split("\n")) {
        appendOutput(line + "\n", classifyLine(line));
      }
    } else if (m.type === "disasm-out") {
      appendOutput(m.text + "\n", "out-trace");
      appendOutput("── output ──\n", "out-dim");
    } else if (m.type === "debug-started") {
      if (m.ok) {
        stepping = true;
        worker.postMessage({ type: "debug-step" });
      } else {
        appendOutput(m.error + "\n", "out-err");
        setDebugUI(false);
      }
    } else if (m.type === "debug-state") {
      showDebugState(m.state);
    } else if (m.type === "done") {
      finishRun();
    }
  };
}

function finishRun() {
  running = false;
  clearTimeout(runTimeout);
  runBtn.hidden = false;
  stopBtn.hidden = true;
  runBtn.disabled = !engineReady;
  debugBtn.disabled = !engineReady;
}

/* ========================= Debugger ========================= */
const debugBtn = document.getElementById("debug-btn");
const debugControls = document.getElementById("debug-controls");
const stepBtn = document.getElementById("step-btn");
const continueBtn = document.getElementById("continue-btn");
const debugStopBtn = document.getElementById("debug-stop-btn");
const debugPanel = document.getElementById("debug-panel");
const debugVars = document.getElementById("debug-vars");
const debugCallstack = document.getElementById("debug-callstack");
const debugBytecode = document.getElementById("debug-bytecode");
let debugging = false;
let stepping = false;       // a step/continue request is in flight
let debugLine = null;       // currently highlighted editor line

function clearDebugLine() {
  if (debugLine !== null && editor.removeLineClass) {
    editor.removeLineClass(debugLine, "background", "debug-line");
  }
  debugLine = null;
}

function setDebugUI(on) {
  debugging = on;
  stepping = false;
  debugControls.hidden = !on;
  debugPanel.hidden = !on;
  runBtn.hidden = on;
  debugBtn.hidden = on;
  if (editor.setOption) editor.setOption("readOnly", on);
  if (!on) clearDebugLine();
}

function showDebugState(s) {
  stepping = false;
  clearTimeout(runTimeout);
  if (s.error) {
    for (const line of s.error.split("\n")) {
      appendOutput(line + "\n", classifyLine(line) || "out-err");
    }
  }
  if (s.done || s.error) {
    if (s.done && !s.error) appendOutput("— program finished —\n", "out-dim");
    setDebugUI(false);
    return;
  }
  if (editor.addLineClass) {
    clearDebugLine();
    debugLine = s.line - 1;
    editor.addLineClass(debugLine, "background", "debug-line");
    editor.scrollIntoView({ line: debugLine, ch: 0 }, 60);
  }
  debugVars.innerHTML = "";
  const names = Object.keys(s.vars);
  if (!names.length) {
    debugVars.innerHTML = '<span class="dv-val out-dim">(nothing set yet)</span>';
  }
  for (const k of names) {
    const n = document.createElement("span");
    n.className = "dv-name";
    n.textContent = k;
    const v = document.createElement("span");
    v.className = "dv-val";
    v.textContent = s.vars[k];
    v.title = s.vars[k];
    debugVars.append(n, v);
  }
  debugCallstack.textContent = s.callstack.join(" → ");
  debugBytecode.textContent = s.bytecode.join("\n");
}

debugBtn.addEventListener("click", () => {
  if (!engineReady || running || debugging) return;
  outputEl.textContent = "";
  setDebugUI(true);
  worker.postMessage({ type: "debug-start", code: editor.getValue() });
});

stepBtn.addEventListener("click", () => {
  if (!debugging || stepping) return;
  stepping = true;
  worker.postMessage({ type: "debug-step" });
});

continueBtn.addEventListener("click", () => {
  if (!debugging || stepping) return;
  stepping = true;
  worker.postMessage({ type: "debug-continue" });
  runTimeout = setTimeout(() => {
    appendOutput("\nStopped after 20 seconds — maybe a loop that never ends?\n", "out-err");
    setDebugUI(false);
    hardStop();
  }, 20000);
});

debugStopBtn.addEventListener("click", () => {
  worker.postMessage({ type: "debug-stop" });
  appendOutput("— debug stopped —\n", "out-dim");
  setDebugUI(false);
});

runBtn.addEventListener("click", () => {
  if (!engineReady || running) return;
  running = true;
  outputEl.textContent = "";
  runBtn.hidden = true;
  stopBtn.hidden = false;
  worker.postMessage({
    type: "run",
    code: editor.getValue(),
    trace: traceCheck.checked,
    bytecode: bytecodeCheck.checked,
  });
  runTimeout = setTimeout(() => {
    appendOutput("\nStopped after 20 seconds — maybe a loop that never ends?\n", "out-err");
    hardStop();
  }, 20000);
});

function hardStop() {
  worker.terminate();
  finishRun();
  bootWorker(); // fresh engine for the next run
}
stopBtn.addEventListener("click", () => {
  appendOutput("\nStopped.\n", "out-err");
  hardStop();
});
document.getElementById("clear-btn").addEventListener("click", () => (outputEl.textContent = ""));
bootWorker();

/* ========================= Practice ========================= */
const listEl = document.getElementById("problem-list");
const detailEl = document.getElementById("problem-detail");

function esc(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function renderProblemList() {
  listEl.innerHTML = "";
  for (const p of PROBLEMS) {
    const card = document.createElement("div");
    card.className = "problem-card";
    card.innerHTML =
      `<span class="pill ${p.difficulty}">${p.difficulty}</span>` +
      `<h3>${esc(p.title)}</h3><p>${esc(p.blurb)}</p>`;
    card.addEventListener("click", () => showProblem(p));
    listEl.appendChild(card);
  }
}

function showProblem(p) {
  listEl.hidden = true;
  detailEl.hidden = false;
  detailEl.innerHTML =
    `<span class="back-link">← All problems</span>` +
    `<span class="pill ${p.difficulty}">${p.difficulty}</span>` +
    `<h2>${esc(p.title)}</h2>` +
    `<p class="statement">${esc(p.statement)}</p>` +
    `<div class="code-block">${esc(p.starter)}</div>` +
    `<div class="detail-actions">` +
    `<button class="btn btn-run" data-act="try">Open starter in playground</button>` +
    `</div>` +
    `<details class="reveal"><summary>Need a hint?</summary><p>${esc(p.hint)}</p></details>` +
    `<details class="reveal"><summary>Show the solution & explanation</summary>` +
    `<div class="code-block">${esc(p.solution)}</div>` +
    `<div class="detail-actions"><button class="btn btn-ghost" data-act="try-solution">Run the solution in the playground</button></div>` +
    `<div class="explanation"><p><strong>How it works:</strong></p><ul>` +
    p.explanation.map((step) => `<li>${esc(step)}</li>`).join("") +
    `</ul></div></details>`;
  detailEl.querySelector(".back-link").addEventListener("click", () => {
    detailEl.hidden = true;
    listEl.hidden = false;
  });
  detailEl.querySelector('[data-act="try"]').addEventListener("click", () => loadIntoEditor(p.starter, p));
  detailEl.querySelector('[data-act="try-solution"]').addEventListener("click", () => loadIntoEditor(p.solution, p));
  window.scrollTo({ top: 0 });
}
renderProblemList();

/* ========================= Docs ========================= */
const docsMain = document.getElementById("docs-main");
const docsNav = document.getElementById("docs-nav");
const docsSearch = document.getElementById("docs-search");

const CATEGORIES = [...new Set(DOCS.map((d) => d.cat))];
DOCS.forEach((d, i) => (d.id = "doc-" + i));

function entryHTML(d) {
  return (
    `<div class="doc-entry" id="${d.id}">` +
    `<h3>${esc(d.title)}</h3>` +
    `<p class="doc-desc">${esc(d.desc)}</p>` +
    `<div class="doc-syntax">${esc(d.syntax)}</div>` +
    `<div class="code-block">${esc(d.example)}</div>` +
    `<button class="doc-try" data-id="${d.id}">▶ Try this in the playground</button>` +
    `</div>`
  );
}

function renderDocs(entries) {
  docsMain.innerHTML = "";
  if (!entries.length) {
    docsMain.innerHTML = `<p class="no-results">No matches — try a different word, or ask the assistant on the right.</p>`;
    return;
  }
  let html = "";
  for (const cat of CATEGORIES) {
    const inCat = entries.filter((d) => d.cat === cat);
    if (!inCat.length) continue;
    html += `<div class="docs-cat">${esc(cat)}</div>`;
    html += inCat.map(entryHTML).join("");
  }
  docsMain.innerHTML = html;
  docsMain.querySelectorAll(".doc-try").forEach((btn) =>
    btn.addEventListener("click", () => {
      const d = DOCS.find((x) => x.id === btn.dataset.id);
      loadIntoEditor("# " + d.title + "\n" + d.example);
    }));
}

function renderNav() {
  docsNav.innerHTML = CATEGORIES.map(
    (c) => `<a href="#docs" data-cat="${esc(c)}">${esc(c)}</a>`).join("");
  docsNav.querySelectorAll("a").forEach((a) =>
    a.addEventListener("click", () => {
      docsSearch.value = "";
      renderDocs(DOCS);
      setTimeout(() => {
        const first = DOCS.find((d) => d.cat === a.dataset.cat);
        if (first) document.getElementById(first.id).scrollIntoView({ behavior: "smooth", block: "start" });
      }, 0);
    }));
}

/* --- search scoring (shared with the chatbot) --- */
function tokenize(q) {
  return q.toLowerCase().replace(/[^a-z0-9\s]/g, " ").split(/\s+/).filter((w) => w.length > 1);
}
const STOP = new Set(["how", "do", "the", "to", "in", "of", "an", "is", "it", "can", "what", "whats",
  "use", "with", "for", "and", "or", "on", "my", "me", "you", "by", "from", "does", "did", "are",
  "make", "making", "create", "write", "get", "work", "works"]);

function scoreEntry(d, words) {
  const title = d.title.toLowerCase();
  const kw = d.kw.toLowerCase();
  const desc = d.desc.toLowerCase();
  const syn = d.syntax.toLowerCase();
  let score = 0;
  for (const w of words) {
    const weight = STOP.has(w) ? 0.2 : 1;
    if (title.includes(w)) score += 5 * weight;
    if (kw.split(/\s+/).some((k) => k === w || k.startsWith(w) || w.startsWith(k) && k.length > 3)) score += 3 * weight;
    else if (kw.includes(w)) score += 2 * weight;
    if (syn.includes(w)) score += 1.5 * weight;
    if (desc.includes(w)) score += 1 * weight;
  }
  return score;
}

function searchDocs(q) {
  const words = tokenize(q);
  if (!words.length) return DOCS;
  return DOCS.map((d) => [scoreEntry(d, words), d])
    .filter(([s]) => s >= 1)
    .sort((a, b) => b[0] - a[0])
    .map(([, d]) => d);
}

docsSearch.addEventListener("input", () => {
  const q = docsSearch.value.trim();
  renderDocs(q ? searchDocs(q) : DOCS);
});

renderNav();
renderDocs(DOCS);

/* ========================= Docs assistant (chatbot) ========================= */
const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");

function addChat(text, who, html) {
  const div = document.createElement("div");
  div.className = "chat-msg " + who;
  if (html) div.innerHTML = html;
  else div.textContent = text;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
  return div;
}

const GREETING = /^(hi|hello|hey|yo|sup|howdy|good (morning|afternoon|evening))\b/i;
const THANKS = /\b(thanks|thank you|thx|ty)\b/i;
const OPENERS = [
  "Good question — here's the part of the docs that covers it:",
  "Found it. This is what you're after:",
  "Here's how Plain does that:",
  "This section of the docs should help:",
];

function botAnswer(q) {
  if (GREETING.test(q.trim()) && tokenize(q).length <= 2) {
    return { html: `Hello! Ask me anything about Plain — for example <em>"how do I count words?"</em> or <em>"what's a lookup?"</em>` };
  }
  if (THANKS.test(q)) {
    return { html: `You're welcome! Ask away if anything else comes up.` };
  }
  const results = searchDocs(q);
  if (!results.length) {
    return { html: `I couldn't find that in the docs. Try other words — for example <em>"sort"</em>, <em>"lookup"</em>, <em>"loop"</em>, <em>"grid"</em>, or <em>"error"</em>. (I only know about the Plain language itself.)` };
  }
  const top = results[0];
  const opener = OPENERS[Math.floor(Math.random() * OPENERS.length)];
  let html =
    `${opener}<br><br><span class="chat-title">${esc(top.title)}</span><br>` +
    `${esc(top.desc)}` +
    `<pre>${esc(top.syntax)}</pre>` +
    `<pre>${esc(top.example)}</pre>`;
  const related = results.slice(1, 3).map((d) => `<em>${esc(d.title)}</em>`);
  if (related.length) html += `Related: ${related.join(" · ")} — search the docs to see them.`;
  return { html, entry: top };
}

chatForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const q = chatInput.value.trim();
  if (!q) return;
  addChat(q, "user");
  chatInput.value = "";
  setTimeout(() => {
    const a = botAnswer(q);
    const div = addChat("", "bot", a.html);
    if (a.entry) {
      const btn = document.createElement("button");
      btn.className = "doc-try";
      btn.textContent = "▶ Try this in the playground";
      btn.addEventListener("click", () => loadIntoEditor("# " + a.entry.title + "\n" + a.entry.example));
      div.appendChild(btn);
    }
  }, 250);
});

/* ========================= boot ========================= */
showTab(location.hash.replace("#", "") || "playground");
})();
