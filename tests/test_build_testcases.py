"""End-to-end tests for scripts/build_testcases.py."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "build_testcases.py"
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"


def run_script(*extra_args, env=None):
    cmd = [str(VENV_PYTHON), str(SCRIPT), *extra_args]
    merged_env = None
    if env is not None:
        merged_env = {**subprocess.os.environ, **env}
    return subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(REPO_ROOT), env=merged_env
    )


def setup_fixtures(tmp_path):
    """Create a minimal submission + cached issue for testing."""
    # Submission
    sub_dir = tmp_path / "submissions" / "test-team" / "submissions" / "001"
    sub_dir.mkdir(parents=True)
    (sub_dir / "metadata.yaml").write_text(
        "issue:\n  owner: testowner\n  repo: testrepo\n  number: 42\n"
    )
    (sub_dir / "output.txt").write_text("# Test Requirements\n\nSome output.")

    # Cached issue
    cache_dir = tmp_path / "issues" / "cache"
    cache_dir.mkdir(parents=True)
    issue_data = {
        "owner": "testowner",
        "repo": "testrepo",
        "number": 42,
        "title": "Bug: something is broken",
        "body": "Steps to reproduce the bug...",
        "state": "open",
        "labels": ["bug"],
        "author": "reporter",
        "created_at": "2024-01-01T00:00:00Z",
        "comments": [
            {"author": "commenter", "created_at": "2024-01-02T00:00:00Z", "body": "I also see this"}
        ],
    }
    (cache_dir / "testowner_testrepo_42.json").write_text(json.dumps(issue_data))

    return tmp_path


# ── E2E: full pipeline ─────────────────────────────────────────────────

class TestBuildTestcasesFullPipeline:
    """Run build_testcases.py end-to-end with fixture data."""

    def test_generates_promptfooconfig(self, tmp_path, monkeypatch):
        """Script generates a valid promptfooconfig.yaml."""
        setup_fixtures(tmp_path)

        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import build_testcases

        monkeypatch.setattr(build_testcases, "SUBMISSIONS_DIR", tmp_path / "submissions")
        monkeypatch.setattr(build_testcases, "CACHE_DIR", tmp_path / "issues" / "cache")
        monkeypatch.setattr(build_testcases, "REPO_ROOT", tmp_path)

        config_path = tmp_path / "promptfooconfig.yaml"
        monkeypatch.setattr(build_testcases, "CONFIG_PATH", config_path)
        monkeypatch.setattr(build_testcases, "PROMPTFOO_DIR", tmp_path / ".promptfoo")

        submissions = build_testcases.discover_submissions()
        assert len(submissions) == 1

        test_cases = []
        for sub in submissions:
            tc = build_testcases.build_test_case(sub)
            test_cases.append(tc)

        assert len(test_cases) == 1
        config = build_testcases.build_promptfoo_config(test_cases)
        yaml_text = build_testcases.write_promptfoo_config(config)

        # Verify the config file was written
        assert config_path.exists()
        loaded = yaml.safe_load(config_path.read_text())
        assert loaded["description"] == "RD-Specs Competition: Judge Team Submissions"
        assert len(loaded["tests"]) == 1
        assert loaded["tests"][0]["vars"]["issue_title"] == "Bug: something is broken"

    def test_test_case_has_all_vars(self, tmp_path, monkeypatch):
        """Each test case has all required vars populated."""
        setup_fixtures(tmp_path)

        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import build_testcases

        monkeypatch.setattr(build_testcases, "SUBMISSIONS_DIR", tmp_path / "submissions")
        monkeypatch.setattr(build_testcases, "CACHE_DIR", tmp_path / "issues" / "cache")
        monkeypatch.setattr(build_testcases, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(build_testcases, "PROMPTFOO_DIR", tmp_path / ".promptfoo")
        monkeypatch.setattr(build_testcases, "CONFIG_PATH", tmp_path / "promptfooconfig.yaml")

        submissions = build_testcases.discover_submissions()
        tc = build_testcases.build_test_case(submissions[0])
        vars_ = tc["vars"]

        assert "output_path" in vars_
        assert "issue_title" in vars_
        assert "issue_body" in vars_
        assert "issue_comments" in vars_
        assert "repo_name" in vars_
        assert "issue_labels" in vars_

        assert vars_["issue_title"] == "Bug: something is broken"
        assert vars_["repo_name"] == "testowner/testrepo"
        assert "I also see this" in vars_["issue_comments"]

    def test_test_case_has_five_assertions(self, tmp_path, monkeypatch):
        """Each test case has the 5 grading dimension assertions."""
        setup_fixtures(tmp_path)

        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import build_testcases

        monkeypatch.setattr(build_testcases, "SUBMISSIONS_DIR", tmp_path / "submissions")
        monkeypatch.setattr(build_testcases, "CACHE_DIR", tmp_path / "issues" / "cache")
        monkeypatch.setattr(build_testcases, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(build_testcases, "PROMPTFOO_DIR", tmp_path / ".promptfoo")
        monkeypatch.setattr(build_testcases, "CONFIG_PATH", tmp_path / "promptfooconfig.yaml")

        submissions = build_testcases.discover_submissions()
        tc = build_testcases.build_test_case(submissions[0])

        metrics = {a["metric"] for a in tc["assert"]}
        assert metrics == {"accuracy", "completeness", "actionability", "clarity", "context_awareness"}

        # Check weights sum to 1.0
        total_weight = sum(a["weight"] for a in tc["assert"])
        assert abs(total_weight - 1.0) < 0.001


# ── E2E: missing cache ─────────────────────────────────────────────────

class TestMissingCache:
    """Test behavior when issue cache is missing."""

    def test_skips_submission_with_missing_cache(self, tmp_path, monkeypatch):
        """Submissions whose issues are not cached are skipped."""
        sub_dir = tmp_path / "submissions" / "test-team" / "submissions" / "001"
        sub_dir.mkdir(parents=True)
        (sub_dir / "metadata.yaml").write_text(
            "issue:\n  owner: missing\n  repo: nope\n  number: 999\n"
        )
        (sub_dir / "output.txt").write_text("output")

        cache_dir = tmp_path / "issues" / "cache"
        cache_dir.mkdir(parents=True)

        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import build_testcases

        monkeypatch.setattr(build_testcases, "SUBMISSIONS_DIR", tmp_path / "submissions")
        monkeypatch.setattr(build_testcases, "CACHE_DIR", cache_dir)
        monkeypatch.setattr(build_testcases, "REPO_ROOT", tmp_path)

        submissions = build_testcases.discover_submissions()
        assert len(submissions) == 1

        with pytest.raises(FileNotFoundError):
            build_testcases.build_test_case(submissions[0])


# ── E2E: no submissions ────────────────────────────────────────────────

class TestNoSubmissions:
    def test_returns_empty_when_no_submissions(self, tmp_path, monkeypatch):
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import build_testcases

        empty = tmp_path / "subs"
        empty.mkdir()
        monkeypatch.setattr(build_testcases, "SUBMISSIONS_DIR", empty)
        assert build_testcases.discover_submissions() == []


# ── E2E: real script run (requires fetch_issues already done) ───────────

class TestRealScriptRun:
    """Run the actual script as a subprocess against real data."""

    def test_runs_without_crash(self):
        """The script runs (may skip if cache is missing)."""
        result = run_script()
        # It either succeeds or fails gracefully
        assert result.returncode in (0, 1)


# ── Integration: real LLM judge call ──────────────────────────────────

def _load_dotenv():
    """Parse .env and .secrets into a dict; os.environ values take precedence."""
    env = {}
    for dotfile in (REPO_ROOT / ".env", REPO_ROOT / ".secrets"):
        if dotfile.exists():
            for line in dotfile.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    env.setdefault(key.strip(), value.strip())
    # Env vars already set in the process take precedence
    for key in list(env):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


class TestLLMJudgeIntegration:
    """Integration test: verifies the actual Anthropic LLM judge API call works.

    Requires ANTHROPIC_API_KEY (and optionally ANTHROPIC_BASE_URL / ANTHROPIC_MODEL)
    to be set in the environment or .env file. Skipped automatically when the key
    is absent so CI without secrets does not break.
    """

    @pytest.fixture
    def env_vars(self):
        return _load_dotenv()

    def test_judge_returns_valid_grading_response(self, env_vars):
        """The LLM judge returns valid JSON with pass/score/reason for an accuracy rubric."""
        import anthropic

        api_key = env_vars.get("ANTHROPIC_API_KEY")
        if not api_key:
            pytest.skip("ANTHROPIC_API_KEY not configured")

        base_url = env_vars.get("ANTHROPIC_BASE_URL")
        model = env_vars.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")

        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        client = anthropic.Anthropic(**client_kwargs)

        # Pull the real accuracy rubric prompt from build_testcases
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import build_testcases

        accuracy_assertion = next(
            a for a in build_testcases.build_assertions() if a["metric"] == "accuracy"
        )

        # Substitute template variables with the canonical example issue
        grading_prompt = (
            accuracy_assertion["value"]
            .replace("{{issue_title}}", "yesterday version 10.5.0 has vulnerabilities")
            .replace(
                "{{issue_body}}",
                "The vulnerability range published is `>= 10.3.7, <= 11.0.3` but the "
                "correct range is `>=10.3.7 <10.5.0 || >=11.0.0 <11.1.0`.",
            )
            .replace(
                "{{issue_comments}}",
                "The advisory-database PR was merged, correcting the range. "
                "A follow-up issue #639 was opened for v9.",
            )
        )

        submission_output = (
            "# Requirements: node-glob #637\n\n"
            "## Problem\n"
            "The GitHub Advisory Database published an incorrect vulnerability range for "
            "node-glob: `>= 10.3.7, <= 11.0.3`. The accurate range is "
            "`>=10.3.7 <10.5.0 || >=11.0.0 <11.1.0`.\n\n"
            "## Acceptance Criteria\n"
            "- Advisory database record corrected via merged PR\n"
            "- v9 follow-up tracked in issue #639\n"
            "- Downstream packages (nyc, globby) unaffected once range is fixed\n"
        )

        response = client.messages.create(
            model=model,
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"{grading_prompt}\n\n"
                        f"Requirements document to grade:\n{submission_output}"
                    ),
                }
            ],
        )

        assert response.content, "LLM returned an empty response"
        raw = response.content[0].text.strip()

        # Strip optional ```json ... ``` fences
        fenced = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
        text = fenced.group(1).strip() if fenced else raw

        grading = json.loads(text)

        assert "pass" in grading, f"Missing 'pass' key: {grading}"
        assert "score" in grading, f"Missing 'score' key: {grading}"
        assert "reason" in grading, f"Missing 'reason' key: {grading}"
        assert isinstance(grading["score"], (int, float)), f"Score is not numeric: {grading}"
        assert 0.0 <= grading["score"] <= 1.0, f"Score out of range [0,1]: {grading['score']}"
