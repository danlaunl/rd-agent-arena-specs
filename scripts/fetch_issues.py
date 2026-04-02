#!/usr/bin/env python3
"""Fetch GitHub issues referenced in team submissions.

Walks the submissions/ directory, discovers all metadata.yaml files,
extracts unique issue references, and fetches issue data from the
GitHub API. Results are cached in issues/cache/ for 24 hours.

Usage:
    python scripts/fetch_issues.py

Environment:
    PAT_GITHUB  Optional. Authenticated requests get 5000/hr vs 60/hr.
"""

import json
import os
import sys
import time
from pathlib import Path

import yaml
import urllib.request
import urllib.error

REPO_ROOT = Path(__file__).resolve().parent.parent
SUBMISSIONS_DIR = REPO_ROOT / "submissions"
CACHE_DIR = REPO_ROOT / "issues" / "cache"
CACHE_TTL_SECONDS = 86400  # 24 hours


def discover_submissions():
    """Walk submissions/ and collect all metadata.yaml paths."""
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
            if not meta_path.exists():
                continue
            with open(meta_path) as f:
                meta = yaml.safe_load(f)
            results.append(
                {
                    "team": team_dir.name,
                    "submission_id": sub_dir.name,
                    "metadata": meta,
                }
            )
    return results


def unique_issue_refs(submissions):
    """Extract deduplicated (owner, repo, number) tuples."""
    refs = set()
    for sub in submissions:
        issue = sub["metadata"]["issue"]
        refs.add((issue["owner"], issue["repo"], issue["number"]))
    return refs


def cache_path(owner, repo, number):
    return CACHE_DIR / f"{owner}_{repo}_{number}.json"


def read_cache(path):
    """Return cached data if it exists and is younger than CACHE_TTL_SECONDS."""
    if not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if age > CACHE_TTL_SECONDS:
        return None
    with open(path) as f:
        return json.load(f)


def write_cache(path, data):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def github_api_get(url, token=None):
    """Make an authenticated GitHub API request. Returns parsed JSON."""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "rd-specs-promptfoo",
    }
    if token:
        headers["Authorization"] = f"token {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} {e.reason}: {url}", file=sys.stderr)
        return None


def fetch_issue(owner, repo, number, token=None):
    """Fetch issue + comments from GitHub. Returns normalized dict."""
    cp = cache_path(owner, repo, number)
    cached = read_cache(cp)
    if cached is not None:
        return cached

    issue_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{number}"
    issue_data = github_api_get(issue_url, token)
    if issue_data is None:
        return None

    # Issue body can be None
    issue_data["body"] = issue_data.get("body") or ""

    # Fetch comments (paginated)
    comments = []
    page = 1
    while True:
        comments_url = (
            f"https://api.github.com/repos/{owner}/{repo}/issues/{number}"
            f"/comments?per_page=100&page={page}"
        )
        page_data = github_api_get(comments_url, token)
        if not page_data:
            break
        for c in page_data:
            comments.append(
                {
                    "author": c["user"]["login"],
                    "created_at": c["created_at"],
                    "body": c.get("body") or "",
                }
            )
        if len(page_data) < 100:
            break
        page += 1

    result = {
        "owner": owner,
        "repo": repo,
        "number": number,
        "title": issue_data.get("title", ""),
        "body": issue_data["body"],
        "state": issue_data.get("state", ""),
        "labels": [label["name"] for label in issue_data.get("labels", [])],
        "author": issue_data.get("user", {}).get("login", ""),
        "created_at": issue_data.get("created_at", ""),
        "comments": comments,
    }

    write_cache(cp, result)
    return result


def main():
    token = os.environ.get("PAT_GITHUB")

    submissions = discover_submissions()
    if not submissions:
        print("No submissions found in submissions/")
        return 0

    teams = {s["team"] for s in submissions}
    print(f"Found {len(submissions)} submissions from {len(teams)} team(s)")

    refs = unique_issue_refs(submissions)
    print(f"Need to fetch {len(refs)} unique issue(s)\n")

    ok, fail = 0, 0
    for owner, repo, number in sorted(refs):
        print(f"  {owner}/{repo}#{number} ... ", end="", flush=True)
        data = fetch_issue(owner, repo, number, token)
        if data:
            print(f"OK ({len(data['comments'])} comments)")
            ok += 1
        else:
            print("FAILED")
            fail += 1
        time.sleep(0.5)  # gentle rate limiting

    print(f"\nDone: {ok} fetched, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
