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
        plain.run(plain.parse(plain.tokenize(src)), {})
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
`);
  return py;
})();

ready.then(
  () => postMessage({ type: "ready" }),
  (err) => postMessage({ type: "boot-error", text: String(err) })
);

onmessage = async (e) => {
  if (e.data.type !== "run") return;
  let py;
  try {
    py = await ready;
  } catch {
    return; // boot-error already reported
  }
  py.setStdout({ batched: (t) => postMessage({ type: "out", text: t }) });
  py.setStderr({ batched: (t) => postMessage({ type: "out", text: t }) });
  try {
    const runner = py.globals.get("_run_plain");
    runner(e.data.code, !!e.data.trace);
    runner.destroy();
  } catch (err) {
    postMessage({ type: "out", text: "Oops: something went wrong inside the engine.\n" + String(err) });
  }
  postMessage({ type: "done" });
};
