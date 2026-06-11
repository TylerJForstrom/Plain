/* Web worker: loads Pyodide (Python in WebAssembly) once, then runs Plain
   programs through the real interpreter (plain.py). Everything happens in
   the visitor's browser — no server, no cost. */

importScripts("https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js");

const ready = (async () => {
  const py = await loadPyodide();
  const src = await (await fetch("plain.py")).text();
  py.FS.writeFile("plain.py", src);
  py.runPython(`
import builtins, sys
sys.setrecursionlimit(6000)

def _no_input(prompt=""):
    raise RuntimeError(
        "The playground can't pause to ask for typed input. "
        "Use 'set' to give the variable a value instead.")
builtins.input = _no_input

import plain

def _run_plain(src, trace):
    plain.TRACE["on"] = bool(trace)
    plain.TRACE["src"] = src.splitlines()
    try:
        ast = plain.parse(plain.tokenize(src))
        if trace:
            plain.run(ast, {})        # trace narration walks the tree
        else:
            plain.run_bytecode(ast, {})   # default engine: the bytecode VM
    except SyntaxError as e:
        print("Oops: " + str(e))
    except plain.PlainRuntimeError as e:
        print("Oops: " + str(e))
    except (NameError, RuntimeError) as e:
        print("Oops: " + str(e))
    except plain.ReturnValue:
        print("Oops: 'give back' only works inside a function.")
    except RecursionError:
        print("Oops: Too much recursion - a function kept calling itself forever.")
    except SystemExit:
        pass

def _disasm_plain(src):
    try:
        return plain.disassemble_source(src)
    except SyntaxError as e:
        return "Oops: " + str(e)

import json

_dbg = None

def _debug_start(src):
    global _dbg
    try:
        _dbg = plain.Stepper(src)
        return json.dumps({"ok": True})
    except SyntaxError as e:
        _dbg = None
        return json.dumps({"ok": False, "error": "Oops: " + str(e)})

def _debug_step():
    return json.dumps(_dbg.step() if _dbg else {"done": True})

def _debug_continue():
    return json.dumps(_dbg.run_to_end() if _dbg else {"done": True})

def _debug_drop():
    global _dbg
    _dbg = None
`);
  return py;
})();

ready.then(
  () => postMessage({ type: "ready" }),
  (err) => postMessage({ type: "boot-error", text: String(err) })
);

const KNOWN = ["run", "debug-start", "debug-step", "debug-continue", "debug-stop"];

onmessage = async (e) => {
  const t = e.data.type;
  if (!KNOWN.includes(t)) return;
  let py;
  try {
    py = await ready;
  } catch {
    return; // boot-error already reported
  }
  py.setStdout({ batched: (txt) => postMessage({ type: "out", text: txt }) });
  py.setStderr({ batched: (txt) => postMessage({ type: "out", text: txt }) });
  try {
    if (t === "run") {
      if (e.data.bytecode) {
        const disasm = py.globals.get("_disasm_plain");
        postMessage({ type: "disasm-out", text: disasm(e.data.code) });
        disasm.destroy();
      }
      const runner = py.globals.get("_run_plain");
      runner(e.data.code, !!e.data.trace);
      runner.destroy();
      postMessage({ type: "done" });
      return;
    }
    if (t === "debug-stop") {
      const drop = py.globals.get("_debug_drop");
      drop();
      drop.destroy();
      return;
    }
    if (t === "debug-start") {
      const start = py.globals.get("_debug_start");
      const res = JSON.parse(start(e.data.code));
      start.destroy();
      postMessage({ type: "debug-started", ok: res.ok, error: res.error || null });
      return;
    }
    const fn = py.globals.get(t === "debug-step" ? "_debug_step" : "_debug_continue");
    const state = JSON.parse(fn());
    fn.destroy();
    postMessage({ type: "debug-state", state });
  } catch (err) {
    postMessage({ type: "out", text: "Oops: something went wrong inside the engine.\n" + String(err) });
    if (t === "run") postMessage({ type: "done" });
    else postMessage({ type: "debug-state", state: { done: true } });
  }
};
