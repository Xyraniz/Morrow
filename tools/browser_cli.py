#!/usr/bin/env python3
"""Repository development CLI."""

from __future__ import annotations

import argparse
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0"
FORMAT_EXTENSIONS = {
    ".cc",
    ".cpp",
    ".cxx",
    ".h",
    ".hh",
    ".hpp",
    ".hxx",
    ".m",
    ".mm",
}


def _display(command: Sequence[str]) -> str:
    return shlex.join(str(part) for part in command)


def _run(command: Sequence[str], *, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    if not capture_output:
        print(f"$ {_display(command)}")
    return subprocess.run(
        [str(part) for part in command],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=capture_output,
    )


def _tool_candidates(name: str) -> Iterable[Path | str]:
    yield name
    if os.name == "nt" and not Path(name).suffix:
        yield f"{name}.bat"
        yield f"{name}.cmd"
        yield f"{name}.exe"

    depot_tools = os.environ.get("DEPOT_TOOLS")
    roots = []
    if depot_tools:
        roots.append(Path(depot_tools))
    roots.extend((ROOT / "third_party" / "depot_tools", ROOT / "depot_tools"))
    for root in roots:
        for candidate in (name, f"{name}.bat", f"{name}.cmd", f"{name}.exe"):
            yield root / candidate


def _find_tool(name: str) -> str | None:
    for candidate in _tool_candidates(name):
        if isinstance(candidate, Path):
            if candidate.is_file():
                return str(candidate)
            continue
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def _require_tool(name: str, purpose: str) -> str | None:
    tool = _find_tool(name)
    if tool:
        return tool
    print(
        f"Required tool '{name}' was not found while trying to {purpose}. "
        "Install depot_tools and put it at the front of PATH, then run "
        "'mach doctor'.",
        file=sys.stderr,
    )
    return None


def _output_dir(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def _passthrough_args(values: Sequence[str]) -> list[str]:
    return list(values[1:] if values and values[0] == "--" else values)


def _relative_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def _check_source_tree() -> bool:
    if not (ROOT / ".gn").is_file() or not (ROOT / "DEPS").is_file():
        print(
            "This command must be run from the browser source root containing "
            "'.gn' and 'DEPS'.",
            file=sys.stderr,
        )
        return False
    return True


def _cmd_doctor(_: argparse.Namespace) -> int:
    if not _check_source_tree():
        return 2

    required = ("git", "gclient", "gn", "autoninja")
    optional = ("clang-format",)
    print(f"Source root: {ROOT}")
    print(f"Host: {platform.system()} {platform.machine()}")
    print(f"Python: {sys.executable}")

    missing_required = []
    for name in required:
        tool = _find_tool(name)
        status = tool or "missing"
        print(f"{'[ok]' if tool else '[missing]'} {name}: {status}")
        if not tool:
            missing_required.append(name)
    for name in optional:
        tool = _find_tool(name)
        print(f"{'[ok]' if tool else '[optional]'} {name}: {tool or 'not found'}")

    if missing_required:
        print(
            "Missing required tools: " + ", ".join(missing_required),
            file=sys.stderr,
        )
        return 1
    return 0


def _cmd_bootstrap(args: argparse.Namespace) -> int:
    if not _check_source_tree():
        return 2

    if args.check and not args.sync:
        return _cmd_doctor(args)

    gclient = _require_tool("gclient", "synchronize dependencies")
    if not gclient:
        return 1
    command = [gclient, "sync"]
    if args.reset:
        command.append("--reset")
    if args.nohooks:
        command.append("--nohooks")
    return _run(command).returncode


def _cmd_config(args: argparse.Namespace) -> int:
    if not _check_source_tree():
        return 2
    gn = _require_tool("gn", "generate build files")
    if not gn:
        return 1
    output = _output_dir(args.out)
    command = [gn, "gen", output]
    if args.args is not None:
        command.append(f"--args={args.args}")
    if args.ide:
        command.append(f"--ide={args.ide}")
    if args.export_compile_commands:
        command.append("--export-compile-commands")
    return _run(command).returncode


def _require_output_dir(value: str) -> Path | None:
    output = _output_dir(value)
    if not output.is_dir():
        print(
            f"Build directory does not exist: {output}. Run 'mach config --out {value}' first.",
            file=sys.stderr,
        )
        return None
    return output


def _cmd_build(args: argparse.Namespace) -> int:
    if not _check_source_tree():
        return 2
    output = _require_output_dir(args.out)
    if not output:
        return 2
    autoninja = _require_tool("autoninja", "build targets")
    if not autoninja:
        return 1
    command = [autoninja, "-C", output]
    if args.jobs:
        command.append(f"-j{args.jobs}")
    if args.verbose:
        command.append("-v")
    command.extend(args.targets or ["chrome"])
    return _run(command).returncode


def _test_binary(output: Path, target: str) -> Path:
    candidate = output / target
    if os.name == "nt":
        executable = candidate.with_suffix(".exe")
        if executable.is_file():
            return executable
    return candidate


def _cmd_test(args: argparse.Namespace) -> int:
    if not _check_source_tree():
        return 2
    output = _require_output_dir(args.out)
    if not output:
        return 2
    target = args.target
    if args.auto:
        vpython = _require_tool("vpython3", "run automatic tests")
        if not vpython:
            return 1
        command = [
            vpython,
            ROOT / "tools" / "autotest" / "main.py",
            "-C",
            output,
            *_passthrough_args(args.test_args),
        ]
        return _run(command).returncode
    if not args.no_build:
        autoninja = _require_tool("autoninja", "build the test target")
        if not autoninja:
            return 1
        result = _run([autoninja, "-C", output, target])
        if result.returncode:
            return result.returncode

    binary = _test_binary(output, target)
    if not binary.is_file():
        print(
            f"Test executable was not found: {binary}. Build target '{target}' first.",
            file=sys.stderr,
        )
        return 2
    command = [binary]
    if args.gtest_filter:
        command.append(f"--gtest_filter={args.gtest_filter}")
    command.extend(_passthrough_args(args.test_args))
    return _run(command).returncode


def _default_browser_binary(output: Path) -> Path | None:
    candidates = []
    if platform.system() == "Darwin":
        candidates.extend(
            (
                output / "Chromium.app" / "Contents" / "MacOS" / "Chromium",
                output / "chrome" / "Chromium.app" / "Contents" / "MacOS" / "Chromium",
            )
        )
    elif os.name == "nt":
        candidates.extend((output / "chrome.exe", output / "chrome"))
    else:
        candidates.extend((output / "chrome", output / "chromium"))
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def _cmd_run(args: argparse.Namespace) -> int:
    if not _check_source_tree():
        return 2
    output = _require_output_dir(args.out)
    if not output:
        return 2
    binary = _relative_path(args.binary) if args.binary else _default_browser_binary(output)
    if not binary or not binary.is_file():
        print(
            "Browser executable was not found. Run 'mach build chrome' or pass "
            "'--binary PATH'.",
            file=sys.stderr,
        )
        return 2
    return _run([binary, *_passthrough_args(args.browser_args)]).returncode


def _git_paths(command: Sequence[str]) -> list[Path]:
    result = _run(command, capture_output=True)
    if result.returncode:
        return []
    return [_relative_path(line) for line in result.stdout.splitlines() if line]


def _format_candidates(explicit: Sequence[str]) -> list[Path]:
    if explicit:
        paths = [_relative_path(value) for value in explicit]
    else:
        paths = _git_paths(("git", "diff", "HEAD", "--name-only", "--diff-filter=ACMR"))
        paths.extend(_git_paths(("git", "ls-files", "--others", "--exclude-standard")))

    result = []
    seen = set()
    for path in paths:
        try:
            relative = path.resolve().relative_to(ROOT.resolve())
        except ValueError:
            continue
        if relative.suffix.lower() not in FORMAT_EXTENSIONS or not path.is_file():
            continue
        key = os.path.normcase(str(path.resolve()))
        if key not in seen:
            result.append(path)
            seen.add(key)
    return result


def _cmd_format(args: argparse.Namespace) -> int:
    if not _check_source_tree():
        return 2
    clang_format = _require_tool("clang-format", "format C and C++ files")
    if not clang_format:
        return 1
    paths = _format_candidates(args.paths)
    if not paths:
        print("No modified C or C++ files were found.")
        return 0

    flag = ["--dry-run", "--Werror"] if args.check else ["-i"]
    for index in range(0, len(paths), 50):
        result = _run([clang_format, *flag, *paths[index : index + 50]])
        if result.returncode:
            return result.returncode
    return 0


def _cmd_gn(args: argparse.Namespace) -> int:
    if not _check_source_tree():
        return 2
    gn = _require_tool("gn", "run a GN command")
    if not gn:
        return 1
    if not args.gn_args:
        print("Usage: mach gn <GN command> [arguments]", file=sys.stderr)
        return 2
    return _run([gn, *args.gn_args]).returncode


def _cmd_clean(args: argparse.Namespace) -> int:
    if not _check_source_tree():
        return 2
    gn = _require_tool("gn", "clean a build directory")
    if not gn:
        return 1
    output = _output_dir(args.out)
    if not output.is_dir():
        print(f"Build directory does not exist: {output}", file=sys.stderr)
        return 2
    return _run([gn, "clean", output]).returncode


def _docs_root(value: str) -> Path | None:
    directory = _relative_path(value)
    if not directory.is_dir():
        print(f"Documentation directory does not exist: {directory}", file=sys.stderr)
        return None
    return directory


def _validate_docs(directory: Path) -> int:
    documents = sorted(directory.rglob("*.md"))
    if not documents:
        print(f"No Markdown documents found in {directory}", file=sys.stderr)
        return 2
    for document in documents:
        try:
            document.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            print(f"Invalid UTF-8 in {document}: {error}", file=sys.stderr)
            return 1
    print(f"Validated {len(documents)} Markdown documents in {directory}")
    return 0


def _cmd_doc(args: argparse.Namespace) -> int:
    if not _check_source_tree():
        return 2
    directory = _docs_root(args.directory)
    if not directory:
        return 2
    if args.no_serve:
        return _validate_docs(directory)

    vpython = _require_tool("vpython3", "serve documentation")
    if not vpython:
        return 1
    command = [
        vpython,
        ROOT / "tools" / "md_browser" / "md_browser.py",
        "--directory",
        directory,
    ]
    if not args.no_open:
        command.append(str(ROOT / "docs" / "README.md"))
    return _run(command).returncode


def _python_interpreter(virtualenv: str | None) -> Path | str | None:
    if not virtualenv:
        return _find_tool("vpython3") or sys.executable
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", virtualenv):
        print("Virtualenv names may contain letters, digits, '.', '_' and '-'.", file=sys.stderr)
        return None
    environment = ROOT / "out" / "mach-venvs" / virtualenv
    interpreter = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not interpreter.is_file():
        environment.parent.mkdir(parents=True, exist_ok=True)
        result = _run([sys.executable, "-m", "venv", environment])
        if result.returncode:
            return None
    return interpreter


def _cmd_python(args: argparse.Namespace) -> int:
    interpreter = _python_interpreter(args.virtualenv)
    if not interpreter:
        return 2
    return _run([interpreter, *_passthrough_args(args.python_args)]).returncode


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mach",
        description="Development commands for the browser source tree.",
    )
    parser.add_argument("--version", action="version", version=VERSION)
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    doctor = subparsers.add_parser("doctor", help="check the local toolchain")
    doctor.set_defaults(handler=_cmd_doctor)

    bootstrap = subparsers.add_parser("bootstrap", help="check or synchronize dependencies")
    bootstrap.add_argument("--sync", action="store_true", help="explicitly run gclient sync")
    bootstrap.add_argument("--check", action="store_true", help="only check the local toolchain")
    bootstrap.add_argument("--reset", action="store_true", help="reset dependencies during sync")
    bootstrap.add_argument("--nohooks", action="store_true", help="skip hooks during sync")
    bootstrap.set_defaults(handler=_cmd_bootstrap)

    config = subparsers.add_parser("config", help="generate GN build files")
    config.add_argument("--out", default="out/Default", help="build directory")
    config.add_argument("--args", help="GN args string")
    config.add_argument("--ide", help="generate IDE files for an IDE supported by GN")
    config.add_argument(
        "--export-compile-commands",
        action="store_true",
        help="export compile_commands.json",
    )
    config.set_defaults(handler=_cmd_config)

    build = subparsers.add_parser("build", help="build one or more targets")
    build.add_argument("targets", nargs="*", help="GN targets, default: chrome")
    build.add_argument("--out", default="out/Default", help="build directory")
    build.add_argument("-j", "--jobs", type=int, help="maximum parallel jobs")
    build.add_argument("-v", "--verbose", action="store_true", help="show compiler commands")
    build.set_defaults(handler=_cmd_build)

    test = subparsers.add_parser("test", help="build and run a GoogleTest target")
    test.add_argument("--auto", action="store_true", help="resolve and run tests with tools/autotest")
    test.add_argument("--target", default="unit_tests", help="test target, default: unit_tests")
    test.add_argument("--out", default="out/Default", help="build directory")
    test.add_argument("--gtest-filter", help="GoogleTest filter")
    test.add_argument("--no-build", action="store_true", help="run the existing executable")
    test.add_argument("test_args", nargs=argparse.REMAINDER, help="arguments after '--'")
    test.set_defaults(handler=_cmd_test)

    run = subparsers.add_parser("run", help="run the built browser")
    run.add_argument("--out", default="out/Default", help="build directory")
    run.add_argument("--binary", help="browser executable path")
    run.add_argument("browser_args", nargs=argparse.REMAINDER, help="arguments after '--'")
    run.set_defaults(handler=_cmd_run)

    doc = subparsers.add_parser("doc", help="validate or serve Markdown documentation")
    doc.add_argument("--directory", default="docs", help="documentation directory")
    doc.add_argument("--no-serve", action="store_true", help="validate documents without starting a server")
    doc.add_argument("--no-open", action="store_true", help="serve without opening a browser")
    doc.set_defaults(handler=_cmd_doc)

    python = subparsers.add_parser("python", help="run Python with the repository environment")
    python.add_argument("--virtualenv", help="named virtual environment under out/mach-venvs")
    python.add_argument("python_args", nargs=argparse.REMAINDER, help="arguments passed to Python")
    python.set_defaults(handler=_cmd_python)

    format_parser = subparsers.add_parser("format", help="format modified C and C++ files")
    format_parser.add_argument("--check", action="store_true", help="check without editing")
    format_parser.add_argument("paths", nargs="*", help="files to format")
    format_parser.set_defaults(handler=_cmd_format)

    gn = subparsers.add_parser("gn", help="run a GN command")
    gn.add_argument("gn_args", nargs=argparse.REMAINDER, help="arguments passed to GN")
    gn.set_defaults(handler=_cmd_gn)

    clean = subparsers.add_parser("clean", help="remove generated build files")
    clean.add_argument("--out", default="out/Default", help="build directory")
    clean.set_defaults(handler=_cmd_clean)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
