# Repository Agent Guidelines

These instructions apply to the source tree from this directory downward. A
more deeply nested `AGENTS.md` is more specific and takes precedence for the
files in its directory. Before changing a directory, locate and read the
nearest applicable instructions.

This repository is a large Chromium-based browser source tree. Keep changes
focused, preserve the existing architecture, and use the repository's build
and test tools instead of inventing parallel workflows.

## General rules

- Keep comments to a strict minimum. Add one only when it explains a
  non-obvious decision, contract, or invariant. Preserve existing comments
  unless they are directly related to the change.
- Do not add emoji to source code, documentation, commit messages, or tooling
  output.
- Do not mix unrelated cleanup, formatting, renaming, or dependency updates
  into a focused change.
- Do not edit generated output or vendored code when the corresponding source
  or generator can be changed instead.
- Do not weaken sandboxing, site isolation, permissions, certificate checks,
  privacy protections, or security boundaries as a shortcut. Privacy and
  security changes need explicit requirements and focused regression tests.
- Keep shared infrastructure and documentation product-neutral while the final
  browser name is still undecided.
- If an unrelated, clearly scoped issue is found, mention it as a possible
  follow-up rather than expanding the current patch.

## Source-tree orientation

Use the directory's local documentation and `BUILD.gn` files as the source of
truth. The following map is a starting point, not a replacement for reading
the code that owns a behavior.

- `base/`, `build/`, `build_overrides/`, `buildtools/`: platform abstractions,
  build configuration, toolchain integration, and build helpers.
- `cc/`, `gpu/`, `skia/`, and `ui/` (including `ui/views/`): compositing, graphics, rendering,
  and user-interface layers.
- `content/`, `blink/`-related code under `third_party/`, `ipc/`, and `mojo/`:
  browser/renderer coordination, web platform integration, IPC, and services.
- `net/`, `services/network/`, `url/`, `crypto/`, and `storage/`: networking,
  URL handling, cryptography, storage, and related service boundaries.
- `chrome/`, `components/`, `extensions/`, `apps/`, and `headless/`: browser
  product code, reusable features, extension APIs, packaged applications, and
  headless targets.
- `android_webview/`, `ash/`, `chromeos/`, `clank/`, `ios/`, `ios_internal/`,
  `fuchsia_web/`, `chromecast/`, and `remoting/`: platform and product
  integrations with additional build and test requirements.
- `testing/`: test infrastructure and shared test utilities. Prefer a focused
  existing harness over adding a new one.
- `third_party/`: imported dependencies. Follow their local instructions and
  license requirements; avoid drive-by changes.
- `tools/`: developer tools and test runners. The repository CLI is exposed by
  the root `mach` and `mach.bat` launchers and implemented in
  `tools/browser_cli.py`.
- `docs/`: repository documentation. Keep command examples synchronized with
  the CLI and the supported platform toolchain.
- `agents/`: local agent skills and workflow material. Read a skill's
  `SKILL.md` before using it.
- `out/<Config>/`: generated GN files, build products, logs, and intermediates.
  Never edit or commit this directory.

When a component has a local `README`, `DEVELOPMENT`, `CONTRIBUTING`,
`AGENTS.md`, or similar guide, read it before making changes there. Nested
instructions may define a different test target, formatting command, or
generated-file policy.

## Toolchain and environment

The expected development environment consists of Git, Chromium's
`depot_tools`, a platform compiler/SDK, and the Python runtime supplied by
`depot_tools`. The most important commands are `gclient`, `gn`, `autoninja`,
and `vpython3`.

On Windows, check the tools from PowerShell with `where.exe` or
`Get-Command`; `where` by itself is a PowerShell alias and is not the Windows
executable lookup command. For example:

```powershell
where.exe gclient
where.exe gn
where.exe autoninja
where.exe vpython3
python --version
```

The repository CLI provides a stable entry point for common tasks. Use
`mach.bat` on Windows and `./mach` on Unix-like systems. Running `python mach`
is a fallback when the launcher is not executable.

```text
mach doctor
mach bootstrap --check
mach bootstrap --sync
mach config --out out/Default --args="is_debug=true is_component_build=true"
mach build --out out/Default chrome
mach test --auto --out out/Default -- --run-changed
mach test --out out/Default --target base_unittests
mach run --out out/Default -- --user-data-dir=out/Default/user-data
mach doc --no-serve --no-open
mach python --virtualenv tools -- -c "print('ready')"
mach format --check
mach gn desc out/Default //chrome
mach clean --out out/Default
```

The `mach` commands have deliberately small responsibilities:

- `doctor` reports the source root and required tools without changing the
  checkout.
- `bootstrap --check` performs diagnostics. `bootstrap --sync` explicitly
  runs dependency synchronization through `gclient`; synchronization can
  update hooks and third-party dependencies, so use it intentionally.
- `config` runs `gn gen` and creates the selected output directory. Set the
  required GN arguments here rather than hand-editing generated files.
- `build` delegates to `autoninja` after configuration exists.
- `test --auto` delegates test selection to `tools/autotest/main.py`.
  Without `--auto`, it builds and runs a GoogleTest target.
- `doc --no-serve --no-open` validates Markdown encoding. Plain `doc` serves
  the documentation through `tools/md_browser`; it does not replace a full
  documentation build system.
- `python --virtualenv NAME` creates a named environment under
  `out/mach-venvs/` and runs the requested Python command inside it.
- `format --check` checks modified C and C++ files with `clang-format`.
  Without `--check`, it formats them in place.
- `gn` is a thin escape hatch for GN commands such as `desc`, `refs`, and
  `args`.
- `clean` removes generated GN files for one output directory through GN. It
  does not delete source files or arbitrary directories.

For a first-time setup, follow the platform-specific instructions in
[`docs/get_the_code.md`](docs/get_the_code.md) and the official build guide
for the host OS. On Windows, the compiler environment and SDK must be
available before invoking `gn gen` or `autoninja`.

## Searching and understanding code

Prefer narrow, source-aware searches. Start from the owning directory and
expand only when the dependency relationship requires it.

```powershell
rg --files -g 'AGENTS.md' -g '!out/**'
rg -n "SymbolName|RelevantText" chrome\browser content\browser tools
git ls-files "components/**/BUILD.gn"
```

Guidelines for navigation:

- Use `rg` with explicit directories and exclusions. Do not blindly scan the
  whole checkout, `out/`, or all of `third_party/`.
- For C++, Rust, Java, TypeScript, JavaScript, and Python, search for the
  declaration, call site, test, and build target together. Use the narrowest
  likely path first.
- Use `BUILD.gn`, `DEPS`, `.gclient`, and nearby documentation to understand
  ownership and dependencies before changing an include or target.
- Use GN to inspect dependency relationships instead of guessing:

  ```text
  mach gn desc out/Default //chrome deps --tree
  mach gn refs out/Default //components/example:target
  ```

- Treat generated bindings, protocol files, mojom output, and generated
  resource files as outputs. Find and update their generator or source input.
- When following a symbol across process boundaries, identify the owning
  service, IPC/Mojo interface, thread, and lifetime before editing code.

## Coding and formatting

Match the conventions of the surrounding directory and the language-specific
guide it references.

- C++ and Objective-C++ must follow Chromium's style and ownership rules.
  Run the repository formatter on changed C/C++ files and do not hand-format
  generated output.
- GN files should be formatted with `gn format` when a local guide does not
  specify a more focused command.
- Rust code should use the repository's pinned `rustfmt` configuration.
- Java, Kotlin, JavaScript, TypeScript, HTML, and CSS changes should use the
  formatter and lint commands documented by their owning directory.
- Python tooling should remain compatible with the repository's supported
  interpreter and follow nearby Chromium Python conventions.
- Keep public APIs, command-line switches, preferences, histograms, and
  serialized data changes backward-compatible unless the task explicitly
  includes a migration.
- Update tests and documentation when a command, public behavior, preference,
  protocol, or user-visible privacy setting changes.

## Building and testing

Run the smallest useful checks first, then broaden verification according to
the risk of the change.

1. Check the working tree and read the relevant local instructions.
2. Identify the owning GN target and the narrowest relevant test target.
3. Format and lint only the changed files where possible.
4. Build the affected target with `mach build` or `autoninja`.
5. Run the focused test, then a broader suite when the change crosses process,
   platform, networking, storage, security, or UI boundaries.

Examples include:

```text
mach build --out out/Default base_unittests
mach test --out out/Default --target base_unittests -- --gtest_filter=Namespace.TestName
mach test --auto --out out/Default -- --run-changed
mach run --out out/Default -- --headless --user-data-dir=out/Default/headless-user-data
```

For changes limited to documentation, scripts, or front-end resources, do not
run a full native build unless the owning instructions require it. For C++,
Rust, Java, or generated bindings, compile the relevant target because source
checks alone are not sufficient.

When running a slow command such as a large build or test suite, never pipe its
output through `head`, `tail`, `grep`, or similar filters. Preserve the full
log and inspect it afterward:

```powershell
New-Item -ItemType Directory -Force artifacts | Out-Null
mach test --auto --out out/Default *> artifacts\test.log
Get-Content artifacts\test.log -Tail 120
```

Use headless execution where the test supports it. Record the exact command,
output directory, relevant filters, and any environmental limitation in the
handoff.

For changes to the local CLI itself, run at least:

```text
python -m unittest tools.browser_cli_test
python -m py_compile tools/browser_cli.py tools/browser_cli_test.py
mach --help
mach doc --no-serve --no-open
```

## Local agent skills

The repository includes focused skills under `agents/skills`. Use one only
when it matches the task, and read its complete `SKILL.md` first. Useful
examples include:

- `chromium-docs` for source documentation and code-link conventions.
- `chromium-code-link-formatting` for stable source references.
- `gn-deps-debugging` for GN dependency and target analysis.
- `multi-agent-engineering-workflow` for work that is intentionally split
  across agents.
- `multi-agent-tdd-implementation` for test-first implementation work.
- `multi-agent-code-review` for a structured review pass.
- `remove-unused-includes` for include cleanup with dependency validation.
- `webui-lit-migration` for the specific WebUI migration it documents.

Skills are not a substitute for directory-specific instructions. If a skill
needs to be linked into a local agent environment, follow
`agents/skills/README.md` and use its setup script rather than copying skill
files manually. Do not invent or invoke tooling that is not available in this
checkout or explicitly configured for the task.

## Git and change management

Before editing, run `git status --short --branch` and preserve unrelated user
changes. Before committing, review the complete diff and check for accidental
generated files:

```text
git status --short
git diff --check
git diff --stat
git diff
```

Do not use destructive commands such as `git reset --hard`, broad deletion, or
history rewriting unless the user explicitly requests that exact operation.
Do not discard, reformat, or overwrite work that is not part of the task.

Use short, imperative commit subjects that describe the repository change.
For this project, do not use `fix:`, `feat:`, or references to another browser
project in commit subjects. Do not claim a change is complete until the file,
verification, commit, and requested remote operation have all been confirmed.

Code review and remote publication are separate actions. Prepare a reviewable
commit with the configured project identity, and push only when the user has
explicitly requested publication. Never submit a change to an external review
system without explicit approval.

## Handoff expectations

Every completed change should report:

- the files and behavior changed;
- the focused tests, formatters, or checks that were run;
- any checks that could not run and why;
- the commit identifier and remote branch when a commit or push was requested.

If verification is blocked by a missing SDK, compiler, `depot_tools` command,
or platform service, state the exact missing prerequisite and leave the source
tree in a recoverable state.
