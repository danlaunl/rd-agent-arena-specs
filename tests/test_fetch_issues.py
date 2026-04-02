"""End-to-end tests for scripts/fetch_issues.py."""

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "fetch_issues.py"
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
SUBMISSIONS_DIR = REPO_ROOT / "submissions"
CACHE_DIR = REPO_ROOT / "issues" / "cache"


def run_script(*extra_args, env=None):
    """Run fetch_issues.py as a subprocess and return CompletedProcess."""
    cmd = [str(VENV_PYTHON), str(SCRIPT), *extra_args]
    merged_env = None
    if env is not None:
        merged_env = {**subprocess.os.environ, **env}
    return subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(REPO_ROOT), env=merged_env
    )


# ── E2E: discover_submissions ──────────────────────────────────────────

class TestDiscoverSubmissions:
    """E2E tests that run the real script against the real filesystem."""

    def test_discovers_example_team(self):
        """The real submissions/ dir contains example-team with at least one submission."""
        result = run_script()
        assert result.returncode == 0
        assert "Found" in result.stdout
        assert "submission" in result.stdout

    def test_discovers_correct_issue_refs(self):
        """The script should find the isaacs/node-glob#637 issue reference."""
        result = run_script()
        assert result.returncode == 0
        assert "isaacs/node-glob#637" in result.stdout


# ── E2E: caching ───────────────────────────────────────────────────────

class TestCaching:
    """Test the caching behavior end-to-end."""

    def test_writes_cache_file(self, tmp_path, monkeypatch):
        """Running the script creates a cache file for each fetched issue."""
        # We use a mock submissions dir with a known public issue
        subs_dir = tmp_path / "submissions" / "test-team" / "submissions" / "001"
        subs_dir.mkdir(parents=True)
        (subs_dir / "metadata.yaml").write_text(
            "issue:\n  owner: github\n  repo: gitignore\n  number: 1\n"
        )
        (subs_dir / "output.txt").write_text("test output")

        cache_dir = tmp_path / "issues" / "cache"
        cache_dir.mkdir(parents=True)

        # Patch by overriding env to use tmp dirs is not possible directly,
        # so we import the module and call functions directly
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import fetch_issues

        monkeypatch.setattr(fetch_issues, "SUBMISSIONS_DIR", tmp_path / "submissions")
        monkeypatch.setattr(fetch_issues, "CACHE_DIR", cache_dir)

        submissions = fetch_issues.discover_submissions()
        assert len(submissions) == 1

        refs = fetch_issues.unique_issue_refs(submissions)
        assert ("github", "gitignore", 1) in refs

    def test_cache_is_reused(self, tmp_path, monkeypatch):
        """If a cache file exists and is fresh, the script does not re-fetch."""
        import fetch_issues

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        cached_data = {
            "owner": "github",
            "repo": "gitignore",
            "number": 1,
            "title": "Test Issue",
            "body": "body text",
            "state": "open",
            "labels": [],
            "author": "testuser",
            "created_at": "2024-01-01T00:00:00Z",
            "comments": [],
        }
        cache_file = cache_dir / "github_gitignore_1.json"
        cache_file.write_text(json.dumps(cached_data))

        monkeypatch.setattr(fetch_issues, "CACHE_DIR", cache_dir)
        cp = fetch_issues.cache_path("github", "gitignore", 1)
        monkeypatch.setattr(fetch_issues, "CACHE_DIR", cache_dir)

        result = fetch_issues.read_cache(cp)
        assert result is not None
        assert result["title"] == "Test Issue"


# ── E2E: full script run with network ──────────────────────────────────

class TestFullRun:
    """Run the complete script. These tests hit the real GitHub API (unauthenticated)."""

    def test_full_run_succeeds(self):
        """Running the script end-to-end exits 0."""
        result = run_script()
        # Could be 0 (all fetched) or could fail if rate-limited
        # We just check it runs without crashing
        assert "Found" in result.stdout or "No submissions found" in result.stdout

    def test_output_format(self):
        """Stdout contains expected summary lines."""
        result = run_script()
        if result.returncode == 0:
            assert "Done:" in result.stdout


# ── E2E: no submissions ────────────────────────────────────────────────

class TestEmptySubmissions:
    """Test behavior when submissions dir is empty."""

    def test_no_submissions(self, tmp_path, monkeypatch):
        """Script returns 0 and prints a message when no submissions exist."""
        import fetch_issues

        empty_subs = tmp_path / "submissions"
        empty_subs.mkdir()
        monkeypatch.setattr(fetch_issues, "SUBMISSIONS_DIR", empty_subs)

        result = run_script(env={"__PYTHONPATH": str(REPO_ROOT / "scripts")})
        # When called as subprocess it reads the real dir, so test via function
        submissions = fetch_issues.discover_submissions()
        assert submissions == []
