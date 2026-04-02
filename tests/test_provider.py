"""End-to-end tests for scripts/provider.py."""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "provider.py"
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"


def run_script(*args):
    cmd = [str(VENV_PYTHON), str(SCRIPT), *args]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))


# ── E2E: call_api (promptfoo provider interface) ───────────────────────

class TestCallApi:
    """Test the promptfoo provider call_api function."""

    def test_returns_file_content(self, tmp_path):
        """call_api reads a file and returns its content."""
        output_file = tmp_path / "output.txt"
        output_file.write_text("Hello from the output file!")

        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import provider

        result = provider.call_api(str(output_file), {}, {})
        assert result["output"] == "Hello from the output file!"

    def test_handles_file_uri_prefix(self, tmp_path):
        """call_api strips file:// prefix from the prompt."""
        output_file = tmp_path / "output.txt"
        output_file.write_text("Content via file URI")

        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import provider

        result = provider.call_api(f"file://{output_file}", {}, {})
        assert result["output"] == "Content via file URI"

    def test_returns_error_for_missing_file(self, tmp_path):
        """call_api returns an error dict for nonexistent files."""
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import provider

        result = provider.call_api(str(tmp_path / "nonexistent.txt"), {}, {})
        assert "error" in result
        assert "not found" in result["error"]


# ── E2E: direct execution (legacy main) ────────────────────────────────

class TestDirectExecution:
    """Test running provider.py directly from the command line."""

    def test_prints_file_content(self, tmp_path):
        """Running provider.py with a file path prints its contents."""
        output_file = tmp_path / "output.txt"
        output_file.write_text("CLI output content")

        result = run_script(str(output_file))
        assert result.returncode == 0
        assert result.stdout.strip() == "CLI output content"

    def test_exits_with_error_on_missing_file(self, tmp_path):
        """Running provider.py with a missing file exits with code 1."""
        result = run_script(str(tmp_path / "nope.txt"))
        assert result.returncode == 1
        assert "not found" in result.stderr

    def test_exits_with_error_on_no_args(self):
        """Running provider.py with no arguments exits with code 1."""
        result = run_script()
        assert result.returncode == 1
        assert "no prompt argument" in result.stderr

    def test_handles_file_uri_via_cli(self, tmp_path):
        """Running provider.py with file:// prefix works."""
        output_file = tmp_path / "output.txt"
        output_file.write_text("file URI CLI test")

        result = run_script(f"file://{output_file}")
        assert result.returncode == 0
        assert result.stdout.strip() == "file URI CLI test"


# ── E2E: reads real example submission ─────────────────────────────────

class TestRealSubmission:
    """Test reading the actual example-team output.txt."""

    def test_reads_example_output(self):
        """Provider can read the real example-team output.txt."""
        output_path = REPO_ROOT / "submissions" / "example-team" / "submissions" / "001" / "output.txt"
        if not output_path.exists():
            pytest.skip("example-team output.txt not found")

        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import provider

        result = provider.call_api(str(output_path), {}, {})
        assert result["output"]
        assert "node-glob" in result["output"].lower() or "Requirements" in result["output"]
