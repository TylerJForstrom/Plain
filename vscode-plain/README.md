# Plain Language for VS Code

Syntax highlighting for `.plain` files: keywords, strings with `[variable]`
interpolation, numbers, comments, operators, and function names.

## Install (no tools needed)

Copy this folder into your VS Code extensions directory and restart VS Code.

**Windows (PowerShell):**

```powershell
Copy-Item -Recurse vscode-plain "$env:USERPROFILE\.vscode\extensions\plain-language-0.1.0"
```

**macOS / Linux:**

```bash
cp -r vscode-plain ~/.vscode/extensions/plain-language-0.1.0
```

Then open any `.plain` file — the language shows up as "Plain" in the
status bar.

## Editing the colors

The grammar lives in `syntaxes/plain.tmLanguage.json`. Each pattern maps
part of the language to a standard scope name (comments, strings,
keywords, ...) that your VS Code color theme already knows how to paint.
