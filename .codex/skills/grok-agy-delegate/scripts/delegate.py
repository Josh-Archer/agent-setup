#!/usr/bin/env python3
"""Run one of the repo's named agents through Grok Build or Antigravity CLI."""

from __future__ import annotations

import argparse
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_MODELS = {
    "grok": "grok-4.5",
    "agy": "Gemini 3.5 Flash (Medium)",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("grok", "agy"), required=True)
    parser.add_argument("--role", help="Named repo agent, for example debugger")
    parser.add_argument("--model", help="Optional provider-specific model override")
    parser.add_argument("--cwd", default=".", help="Delegated working directory")
    prompt = parser.add_mutually_exclusive_group(required=True)
    prompt.add_argument("--prompt")
    prompt.add_argument("--prompt-file", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-format", choices=("plain", "json", "streaming-json"), default="plain")
    return parser.parse_args()


def build_command(args: argparse.Namespace, prompt: str) -> list[str]:
    executable = shutil.which(args.provider)
    if not executable:
        raise SystemExit(f"{args.provider} CLI not found on PATH")

    model = args.model or DEFAULT_MODELS[args.provider]
    if args.provider == "grok":
        command = [executable, "-p", prompt, "--cwd", args.cwd, "--output-format", args.output_format]
        if args.role:
            command += ["--agent", args.role]
        if model:
            command += ["--model", model]
        return command

    command = [executable, "--print", prompt, "--print-timeout", "10m"]
    if args.role:
        command += ["--agent", args.role]
    if model:
        command += ["--model", model]
    return command


def main() -> int:
    args = parse_args()
    prompt = args.prompt
    if args.prompt_file:
        prompt = args.prompt_file.read_text()
    assert prompt is not None
    command = build_command(args, prompt)

    if args.dry_run:
        print(shlex.join(command))
        return 0

    result = subprocess.run(command, cwd=args.cwd, text=True)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
