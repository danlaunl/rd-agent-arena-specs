#!/usr/bin/env python3
"""Promptfoo Python provider that returns a submitted output file.

In our setup the "prompt" rendered by promptfoo is simply the path to the
team's output.txt file. This provider reads that file and returns its
contents as the model output, so promptfoo can run llm-rubric assertions
against it.

Usage (configured in promptfooconfig.yaml):
    providers:
      - python:scripts/provider.py
"""

import sys
from pathlib import Path


def call_api(prompt, options, context):
    """Promptfoo provider API - returns the content of the output file.

    Args:
        prompt: The path to the team's output.txt file
        options: Additional options (not used)
        context: Additional context (not used)

    Returns:
        dict with response text
    """
    output_path = prompt.strip()

    # Strip file:// prefix if present
    if output_path.startswith("file://"):
        output_path = output_path[7:]

    p = Path(output_path)
    if not p.exists():
        return {
            "error": f"output file not found: {output_path}",
            "output": f"ERROR: File not found: {output_path}"
        }

    content = p.read_text()
    return {
        "output": content
    }


# Legacy main() for direct execution
def main():
    if len(sys.argv) < 2:
        print("ERROR: provider.py received no prompt argument", file=sys.stderr)
        sys.exit(1)

    output_path = sys.argv[1].strip()

    # Strip file:// prefix if present
    if output_path.startswith("file://"):
        output_path = output_path[7:]

    p = Path(output_path)
    if not p.exists():
        print(f"ERROR: output file not found: {output_path}", file=sys.stderr)
        sys.exit(1)

    print(p.read_text())


if __name__ == "__main__":
    main()
