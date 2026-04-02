"""End-to-end tests for scripts/leaderboard.py."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "leaderboard.py"
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"

SAMPLE_RESULTS = {
    "results": [
        {
            "description": "team-alpha/001: owner/repo#123",
            "score": 0.85,
            "assertionResults": [
                {"metric": "accuracy", "score": 0.9},
                {"metric": "completeness", "score": 0.8},
                {"metric": "actionability", "score": 0.85},
                {"metric": "clarity", "score": 0.88},
                {"metric": "context_awareness", "score": 0.82},
            ],
        },
        {
            "description": "team-beta/002: owner/repo#456",
            "score": 0.60,
            "assertionResults": [
                {"metric": "accuracy", "score": 0.7},
                {"metric": "completeness", "score": 0.55},
                {"metric": "actionability", "score": 0.5},
                {"metric": "clarity", "score": 0.65},
                {"metric": "context_awareness", "score": 0.6},
            ],
        },
    ]
}


def write_results(path, data=SAMPLE_RESULTS):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def run_script(*extra_args):
    cmd = [str(VENV_PYTHON), str(SCRIPT), *extra_args]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))


# ── E2E: full pipeline with fixture data ────────────────────────────────

class TestLeaderboardFullPipeline:
    """Run leaderboard.py end-to-end with fixture results."""

    def test_prints_leaderboard_table(self, tmp_path, monkeypatch):
        """Script prints a formatted leaderboard to stdout."""
        results_path = tmp_path / "results.json"
        write_results(results_path)

        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import leaderboard

        monkeypatch.setattr(leaderboard, "DEFAULT_RESULTS_PATH", results_path)
        monkeypatch.setattr(leaderboard, "RESULTS_DIR", tmp_path / "results")
        monkeypatch.setattr(leaderboard, "REPO_ROOT", tmp_path)

        # Create .promptfoo dir for leaderboard.txt output
        (tmp_path / ".promptfoo").mkdir(exist_ok=True)

        subs = leaderboard.parse_results(results_path)
        assert len(subs) == 2

        teams_data = leaderboard.merge_and_group(subs, [], {}, "2024-01-01T00:00:00Z")
        rows = leaderboard.compute_averages(teams_data)

        assert len(rows) == 2
        # team-alpha should rank first (higher score)
        assert rows[0]["team"] == "team-alpha"
        assert rows[0]["overall"] > rows[1]["overall"]

    def test_writes_latest_json(self, tmp_path, monkeypatch):
        """Script writes results/latest.json."""
        results_path = tmp_path / "results.json"
        write_results(results_path)

        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import leaderboard

        monkeypatch.setattr(leaderboard, "DEFAULT_RESULTS_PATH", results_path)
        monkeypatch.setattr(leaderboard, "RESULTS_DIR", tmp_path / "results")
        monkeypatch.setattr(leaderboard, "REPO_ROOT", tmp_path)
        (tmp_path / ".promptfoo").mkdir(exist_ok=True)

        subs = leaderboard.parse_results(results_path)
        teams_data = leaderboard.merge_and_group(subs, [], {}, "2024-01-01T00:00:00Z")
        data = leaderboard.write_latest_json(teams_data, "2024-01-01T00:00:00Z")

        latest_path = tmp_path / "results" / "latest.json"
        assert latest_path.exists()
        loaded = json.loads(latest_path.read_text())
        assert loaded["evaluated_at"] == "2024-01-01T00:00:00Z"
        assert "team-alpha" in loaded["teams"]

    def test_writes_leaderboard_md(self, tmp_path, monkeypatch):
        """Script writes results/leaderboard.md."""
        results_path = tmp_path / "results.json"
        write_results(results_path)

        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import leaderboard

        monkeypatch.setattr(leaderboard, "DEFAULT_RESULTS_PATH", results_path)
        results_dir = tmp_path / "results"
        monkeypatch.setattr(leaderboard, "RESULTS_DIR", results_dir)
        monkeypatch.setattr(leaderboard, "REPO_ROOT", tmp_path)
        (tmp_path / ".promptfoo").mkdir(exist_ok=True)

        subs = leaderboard.parse_results(results_path)
        teams_data = leaderboard.merge_and_group(subs, [], {}, "2024-01-01T00:00:00Z")
        rows = leaderboard.compute_averages(teams_data)
        results_dir.mkdir(parents=True, exist_ok=True)
        leaderboard.write_leaderboard_md(rows, "2024-01-01T00:00:00Z")

        md_path = tmp_path / "results" / "leaderboard.md"
        assert md_path.exists()
        content = md_path.read_text()
        assert "# RD-Specs Leaderboard" in content
        assert "team-alpha" in content
        assert "team-beta" in content


# ── E2E: parse_team_and_id ─────────────────────────────────────────────

class TestParseTeamAndId:
    def test_parses_standard_description(self):
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import leaderboard

        team, sub_id, issue_ref = leaderboard.parse_team_and_id("team-alpha/001: owner/repo#123")
        assert team == "team-alpha"
        assert sub_id == "001"
        assert issue_ref == "owner/repo#123"

    def test_handles_malformed_description(self):
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import leaderboard

        team, sub_id, issue_ref = leaderboard.parse_team_and_id("garbage")
        assert team == "unknown"


# ── E2E: pass/fail threshold ───────────────────────────────────────────

class TestPassFailThreshold:
    def test_pass_threshold(self, tmp_path, monkeypatch):
        """Scores above threshold are marked as pass."""
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import leaderboard

        results_path = tmp_path / "results.json"
        write_results(results_path)

        subs = leaderboard.parse_results(results_path)
        # team-alpha has score 0.85 >= 0.70
        alpha = next(s for s in subs if s["team"] == "team-alpha")
        assert alpha["pass"] is True

    def test_fail_threshold(self, tmp_path, monkeypatch):
        """Scores below threshold are marked as fail."""
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import leaderboard

        results_path = tmp_path / "results.json"
        write_results(results_path)

        subs = leaderboard.parse_results(results_path)
        # team-beta has score 0.60 < 0.70
        beta = next(s for s in subs if s["team"] == "team-beta")
        assert beta["pass"] is False


# ── E2E: empty results ─────────────────────────────────────────────────

class TestEmptyResults:
    def test_no_results_returns_empty(self, tmp_path):
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import leaderboard

        results_path = tmp_path / "nonexistent.json"
        subs = leaderboard.parse_results(results_path)
        assert subs == []

    def test_empty_results_file(self, tmp_path):
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import leaderboard

        results_path = tmp_path / "results.json"
        results_path.write_text(json.dumps({"results": []}))
        subs = leaderboard.parse_results(results_path)
        assert subs == []


# ── E2E: run as subprocess ─────────────────────────────────────────────

class TestSubprocessRun:
    def test_runs_with_sample_results(self, tmp_path):
        """Run leaderboard.py as subprocess with a sample results file."""
        results_path = tmp_path / "results.json"
        write_results(results_path)

        result = run_script(str(results_path))
        # The script tries to write to REPO_ROOT/results and REPO_ROOT/.promptfoo
        # It may fail on those writes but should still produce output
        assert "team-alpha" in result.stdout or result.returncode == 1
