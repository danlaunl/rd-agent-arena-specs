#!/usr/bin/env python3
"""Build promptfoo test cases from team submissions.

Reads all submission directories, pairs each output.txt with its cached
GitHub issue, and generates a promptfooconfig.yaml for evaluation.

Usage:
    python scripts/build_testcases.py

Requires: fetch_issues.py has been run to populate issues/cache/
"""

import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SUBMISSIONS_DIR = REPO_ROOT / "submissions"
CACHE_DIR = REPO_ROOT / "issues" / "cache"
CONFIG_PATH = REPO_ROOT / "promptfooconfig.yaml"
PROMPTFOO_DIR = REPO_ROOT / ".promptfoo"
PR_COMMENT_MARKER = "<!-- promptfooconfig.yaml -->"


def discover_submissions():
    """Walk submissions/ and collect all valid submission directories."""
    results = []
    if not SUBMISSIONS_DIR.exists():
        return results

    for team_dir in sorted(SUBMISSIONS_DIR.iterdir()):
        if not team_dir.is_dir() or team_dir.name.startswith("_"):
            continue
        subs_dir = team_dir / "submissions"
        if not subs_dir.exists():
            continue
        for sub_dir in sorted(subs_dir.iterdir()):
            if not sub_dir.is_dir():
                continue
            meta_path = sub_dir / "metadata.yaml"
            output_path = sub_dir / "output.txt"
            if not meta_path.exists() or not output_path.exists():
                continue
            with open(meta_path) as f:
                meta = yaml.safe_load(f)
            results.append(
                {
                    "team": team_dir.name,
                    "submission_id": sub_dir.name,
                    "metadata": meta,
                    "output_path": str(output_path.relative_to(REPO_ROOT)),
                }
            )
    return results


def load_cached_issue(owner, repo, number):
    """Load a cached GitHub issue. Returns dict or raises FileNotFoundError."""
    cache_key = f"{owner}_{repo}_{number}.json"
    cache_path = CACHE_DIR / cache_key
    if not cache_path.exists():
        raise FileNotFoundError(
            f"Issue not in cache: {owner}/{repo}#{number}. "
            f"Run 'python scripts/fetch_issues.py' first."
        )
    with open(cache_path) as f:
        return json.load(f)


def format_comments(comments):
    """Format issue comments into a readable string."""
    if not comments:
        return "(no comments)"
    parts = []
    for c in comments:
        parts.append(f"@{c['author']} ({c['created_at']}):\n{c['body']}")
    return "\n\n---\n\n".join(parts)


def build_test_case(sub):
    """Build a single promptfoo test case from a submission."""
    issue_ref = sub["metadata"]["issue"]
    issue = load_cached_issue(issue_ref["owner"], issue_ref["repo"], issue_ref["number"])
    comments_text = format_comments(issue["comments"])

    return {
        "description": (
            f"{sub['team']}/{sub['submission_id']}: "
            f"{issue['owner']}/{issue['repo']}#{issue['number']}"
        ),
        "vars": {
            "output_path": sub["output_path"],
            "issue_title": issue["title"],
            "issue_body": issue["body"] or "(no body)",
            "issue_comments": comments_text,
            "repo_name": f"{issue['owner']}/{issue['repo']}",
            "issue_labels": ", ".join(issue["labels"]) or "(none)",
        },
        "assert": build_assertions(),
    }


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


def build_assertions():
    """Return the 5 llm-rubric assertions for grading dimensions."""
    return [
        {
            "type": "llm-rubric",
            "metric": "accuracy",
            "weight": 0.30,
            "threshold": 0.0,  # allow partial scores
            "value": (
                "Grade ONLY the ACCURACY of this requirements document.\n\n"
                "GitHub Issue:\n"
                "TITLE: {{issue_title}}\n"
                "BODY: {{issue_body}}\n"
                "COMMENTS: {{issue_comments}}\n\n"
                "Score 0.0 to 1.0 on whether the requirements correctly identify "
                "the core problem, affected components, and factual details from the issue. "
                "Return JSON with 'pass', 'score', and 'reason' keys."
            ),
        },
        {
            "type": "llm-rubric",
            "metric": "completeness",
            "weight": 0.25,
            "threshold": 0.0,
            "value": (
                "Grade ONLY the COMPLETENESS of this requirements document.\n\n"
                "GitHub Issue:\n"
                "TITLE: {{issue_title}}\n"
                "BODY: {{issue_body}}\n"
                "COMMENTS: {{issue_comments}}\n\n"
                "Score 0.0 to 1.0 on whether ALL relevant details from the issue "
                "and comments are captured. Significant omissions lower the score. "
                "Return JSON with 'pass', 'score', and 'reason' keys."
            ),
        },
        {
            "type": "llm-rubric",
            "metric": "actionability",
            "weight": 0.20,
            "threshold": 0.0,
            "value": (
                "Grade ONLY the ACTIONABILITY of this requirements document.\n\n"
                "Score 0.0 to 1.0 on whether a developer could pick up these requirements "
                "and implement them. Are acceptance criteria clear? Are technical details sufficient? "
                "Is there ambiguity that would block implementation? "
                "Return JSON with 'pass', 'score', and 'reason' keys."
            ),
        },
        {
            "type": "llm-rubric",
            "metric": "clarity",
            "weight": 0.15,
            "threshold": 0.0,
            "value": (
                "Grade ONLY the CLARITY of this requirements document.\n\n"
                "Score 0.0 to 1.0 on structure, readability, and lack of ambiguity. "
                "Is it well-organized? Are there contradictions or vague statements? "
                "Would a developer understand it without clarification? "
                "Return JSON with 'pass', 'score', and 'reason' keys."
            ),
        },
        {
            "type": "llm-rubric",
            "metric": "context_awareness",
            "weight": 0.10,
            "threshold": 0.0,
            "value": (
                "Grade ONLY the CONTEXT AWARENESS of this requirements document.\n\n"
                "GitHub Issue:\n"
                "TITLE: {{issue_title}}\n"
                "BODY: {{issue_body}}\n"
                "COMMENTS: {{issue_comments}}\n\n"
                "Score 0.0 to 1.0 on whether the document demonstrates understanding of "
                "the broader ecosystem, identifies edge cases, and considers downstream impacts. "
                "Return JSON with 'pass', 'score', and 'reason' keys."
            ),
        },
    ]


def get_grading_provider():
    """Determine the grading provider config from environment variables.

    Returns either a string like 'anthropic:messages:claude-3-5-sonnet-latest' or a dict with id and config
    for providers that need custom base URLs (e.g. Anthropic-compatible gateways).
    """
    env = _load_dotenv()
    model = env.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
    base_url = env.get("ANTHROPIC_BASE_URL")
    provider_id = f"anthropic:messages:{model}"
    if base_url:
        return {
            "id": provider_id,
            "config": {
                "apiBaseUrl": base_url,
            },
        }
    return provider_id


def build_promptfoo_config(test_cases):
    """Generate the complete promptfooconfig.yaml structure."""
    return {
        "description": "RD-Specs Competition: Judge Team Submissions",
        "providers": [
            {
                "id": "python:scripts/provider.py",
                "label": "Team Submissions",
            }
        ],
        "prompts": ["{{output_path}}"],
        "tests": test_cases,
        "defaultTest": {
            "options": {
                "provider": get_grading_provider(),
            },
        },
        "envFile": ".env",
        "outputPath": ".promptfoo/results.json",
    }


def serialize_promptfoo_config(config):
    """Serialize the promptfoo config to YAML using stable formatting."""
    return yaml.safe_dump(config, sort_keys=False, default_flow_style=False, width=1000)


def write_promptfoo_config(config):
    """Write promptfooconfig.yaml and return the serialized YAML text."""
    yaml_text = serialize_promptfoo_config(config)
    with open(CONFIG_PATH, "w") as f:
        f.write(yaml_text)
    return yaml_text


def build_pr_comment_body(config_yaml, test_case_count, skipped_count):
    """Build a PR comment body that contains the generated config."""
    lines = [
        PR_COMMENT_MARKER,
        "## promptfooconfig.yaml",
        "",
        "The generated promptfoo config is below for review.",
        "",
        f"- Test cases: {test_case_count}",
        f"- Skipped submissions: {skipped_count}",
        "",
        "```yaml",
        config_yaml.rstrip(),
        "```",
    ]
    return "\n".join(lines)


def get_pull_request_number():
    """Return the PR number when running inside a pull_request GitHub Actions event."""
    if os.environ.get("GITHUB_EVENT_NAME") != "pull_request":
        return None

    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        return None

    try:
        with open(event_path) as f:
            event = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    pull_request = event.get("pull_request") or {}
    return pull_request.get("number")


def github_api_request(method, url, token, payload=None):
    """Send a GitHub API request and return parsed JSON when present."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "rd-specs-promptfoo",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(url, data=data, headers=headers, method=method)
    with urlopen(req) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body) if body else None


def post_or_update_pr_comment(body):
    """Create or update the PR comment containing the generated config.

    When running under act (ACT=true), writes the comment body to
    .promptfoo/pr-comment.md instead of calling the GitHub API.
    """
    # --- Local simulation mode (act sets ACT=true automatically) ---
    if os.environ.get("ACT"):
        PROMPTFOO_DIR.mkdir(exist_ok=True)
        out_path = PROMPTFOO_DIR / "pr-comment.md"
        out_path.write_text(body)
        return "simulated"

    # --- Real PR mode: post/update via GitHub API ---
    token = os.environ.get("PAT_GITHUB")
    repo = os.environ.get("GITHUB_REPOSITORY")
    pr_number = get_pull_request_number()

    if not token or not repo or not pr_number:
        return False

    owner, repo_name = repo.split("/", 1)
    comments_url = (
        f"https://api.github.com/repos/{owner}/{repo_name}"
        f"/issues/{pr_number}/comments"
    )

    try:
        comments = github_api_request("GET", comments_url, token) or []
        existing = next(
            (
                comment
                for comment in comments
                if comment.get("user", {}).get("type") == "Bot"
                and comment.get("body", "").startswith(PR_COMMENT_MARKER)
            ),
            None,
        )

        if existing:
            comment_url = f"{comments_url}/{existing['id']}"
            github_api_request("PATCH", comment_url, token, {"body": body})
        else:
            github_api_request("POST", comments_url, token, {"body": body})
        return True
    except (HTTPError, URLError, json.JSONDecodeError) as e:
        print(f"Warning: could not publish PR comment: {e}", file=sys.stderr)
        return False


def main():
    submissions = discover_submissions()
    if not submissions:
        print("No submissions found in submissions/")
        return 1

    print(f"Found {len(submissions)} submission(s)\n")

    test_cases = []
    skipped = 0
    for sub in submissions:
        try:
            tc = build_test_case(sub)
            test_cases.append(tc)
            print(f"  {tc['description']}")
        except FileNotFoundError as e:
            print(f"  SKIP {sub['team']}/{sub['submission_id']}: {e}")
            skipped += 1

    if not test_cases:
        print("\nNo valid test cases. Make sure fetch_issues.py has been run.")
        return 1

    config = build_promptfoo_config(test_cases)
    config_yaml = write_promptfoo_config(config)
    comment_body = build_pr_comment_body(config_yaml, len(test_cases), skipped)
    posted = post_or_update_pr_comment(comment_body)

    print(f"\nGenerated {CONFIG_PATH} with {len(test_cases)} test case(s)")
    if skipped:
        print(f"  (skipped {skipped} submission(s) with missing cached issues)")
    if posted == "simulated":
        print("  [act] Simulated PR comment written to .promptfoo/pr-comment.md")
    elif posted:
        print("  (posted promptfooconfig.yaml to the pull request comment)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
