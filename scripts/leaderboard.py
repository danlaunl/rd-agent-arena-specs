#!/usr/bin/env python3
"""Generate a leaderboard from promptfoo evaluation results.

Reads the eval results JSON from promptfoo, aggregates scores by team
and dimension, and prints a formatted leaderboard.

Usage:
    python scripts/leaderboard.py [results.json]

If no path is provided, reads .promptfoo/results.json.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESULTS_PATH = REPO_ROOT / ".promptfoo" / "results.json"
RESULTS_DIR = REPO_ROOT / "results"

WEIGHTS = {
    "accuracy": 0.30,
    "completeness": 0.25,
    "actionability": 0.20,
    "clarity": 0.15,
    "context_awareness": 0.10,
}
PASS_THRESHOLD = 0.70


def parse_team_and_id(desc):
    """Extract (team, sub_id, issue_ref) from description.
    Description format: 'team-alpha/001: owner/repo#123'
    """
    try:
        team_sub, issue_ref = desc.split(": ", 1)
        team, sub_id = team_sub.split("/", 1)
        return team, sub_id, issue_ref
    except (ValueError, AttributeError):
        return "unknown", "unknown", desc


def parse_results(results_path):
    """Parse promptfoo eval results. Returns list of submission dicts.

    Handles both legacy format (data["results"] is a list) and v3 format
    (data["results"] is a dict with "results" and "tests" keys).
    """
    if not results_path.exists():
        return []

    with open(results_path) as f:
        data = json.load(f)

    raw_results = data.get("results", [])

    # Detect v3 format: results is a dict with nested "results" and "tests"
    if isinstance(raw_results, dict):
        tests = raw_results.get("tests", [])
        results_list = raw_results.get("results", [])
    else:
        # Legacy format: results is a list of dicts with description/assertionResults
        tests = raw_results
        results_list = raw_results

    subs = []
    for idx, result in enumerate(results_list):
        # Get description: try testCase.description (v3), then tests array, then result itself
        desc = ""
        tc = result.get("testCase")
        if tc and isinstance(tc, dict):
            desc = tc.get("description", "")
        elif idx < len(tests):
            desc = tests[idx].get("description", "")
        else:
            desc = result.get("description", "")

        team, sub_id, issue_ref = parse_team_and_id(desc)

        scores = {k: 0.0 for k in WEIGHTS}

        # v3 format: scores in gradingResult.namedScores
        grading = result.get("gradingResult", {})
        named_scores = grading.get("namedScores", {})
        for k in WEIGHTS:
            if k in named_scores:
                scores[k] = named_scores[k]

        # Legacy fallback: collect from assertionResults
        if not named_scores:
            for assertion in result.get("assertionResults", []):
                metric = assertion.get("metric", "")
                score = assertion.get("score", 0.0)
                if metric in scores:
                    scores[metric] = score

        # Use gradingResult.score (already weighted by promptfoo)
        weighted_total = grading.get("score", result.get("score", 0.0))

        subs.append(
            {
                "team": team,
                "sub_id": sub_id,
                "issue": issue_ref,
                "scores": scores,
                "weighted_total": weighted_total,
                "pass": weighted_total >= PASS_THRESHOLD,
            }
        )

    return subs


def load_skipped():
    """Load cached submissions that were skipped in building test cases."""
    p = REPO_ROOT / ".promptfoo" / "skipped.json"
    if not p.exists():
        return []
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return []


def load_submission_hashes():
    """Load the sha256 map for all submissions."""
    p = REPO_ROOT / ".promptfoo" / "submission_hashes.json"
    if not p.exists():
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def merge_and_group(new_subs, skipped, hashes, now_iso):
    """Merge new and skipped results, update sha256, group by team."""
    teams = {}

    def get_team_obj(name):
        if name not in teams:
            teams[name] = {"team_average": 0.0, "submissions": {}}
        return teams[name]

    # Process new evaluations
    for sub in new_subs:
        team_obj = get_team_obj(sub["team"])
        key = f"{sub['team']}/{sub['sub_id']}"
        team_obj["submissions"][sub["sub_id"]] = {
            "issue": sub["issue"],
            "scores": sub["scores"],
            "weighted_total": sub["weighted_total"],
            "pass": sub["pass"],
            "evaluated_at": now_iso,
            "output_sha256": hashes.get(key, ""),
        }

    # Process skipped evaluations (copy from latest)
    for skip in skipped:
        team_obj = get_team_obj(skip["team"])
        sub_id = skip["submission_id"]
        latest_entry = skip.get("from_latest")
        if latest_entry:
            key = f"{skip['team']}/{sub_id}"
            latest_entry["output_sha256"] = hashes.get(key, "")
            team_obj["submissions"][sub_id] = latest_entry

    return teams


def compute_averages(teams):
    """Calculate per-team overall averages and return sorted list."""
    rows = []
    for team, data in teams.items():
        subs = data["submissions"].values()
        if not subs:
            continue

        count = len(subs)
        overall = sum(s["weighted_total"] for s in subs) / count
        data["team_average"] = overall

        dim_avgs = {k: 0.0 for k in WEIGHTS}
        for sub in subs:
            for k in WEIGHTS:
                dim_avgs[k] += sub["scores"].get(k, 0.0)

        for k in WEIGHTS:
            dim_avgs[k] /= count

        rows.append(
            {
                "team": team,
                "submissions": count,
                "overall": overall,
                **dim_avgs,
            }
        )

    # Sort descending by overall
    rows.sort(key=lambda x: x["overall"], reverse=True)
    return rows


def write_latest_json(teams, now_iso):
    """Write the canonical latest results to results/latest.json."""
    data = {
        "evaluated_at": now_iso,
        "teams": teams,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "latest.json", "w") as f:
        json.dump(data, f, indent=2)
    return data


def write_history_json(data, now_iso):
    """Snapshot a results history file."""
    history_dir = RESULTS_DIR / "history"
    history_dir.mkdir(exist_ok=True)
    ts = now_iso.replace(":", "-").replace("Z", "")
    with open(history_dir / f"{ts}.json", "w") as f:
        json.dump(data, f, indent=2)


def write_leaderboard_md(rows, now_iso):
    """Generate a markdown version of the leaderboard."""
    lines = [
        "# RD-Specs Leaderboard",
        f"*Last Evaluation: {now_iso}*",
        "",
        "| Rank | Team | Subs | Overall | Accuracy | Complete | Action | Clarity | Context |",
        "|------|------|------|---------|----------|----------|--------|---------|---------|",
    ]
    for i, r in enumerate(rows, 1):
        pass_icon = "✅" if r["overall"] >= PASS_THRESHOLD else "❌"
        lines.append(
            f"| #{i} | {r['team']} | {r['submissions']} | "
            f"**{r['overall']:.3f}** {pass_icon} | "
            f"{r['accuracy']:.3f} | {r['completeness']:.3f} | {r['actionability']:.3f} | "
            f"{r['clarity']:.3f} | {r['context_awareness']:.3f} |"
        )
    lines.append("")
    lines.append(f"*Pass threshold: {PASS_THRESHOLD}*")

    with open(RESULTS_DIR / "leaderboard.md", "w") as f:
        f.write("\n".join(lines))


def print_leaderboard(teams):
    """Print a formatted leaderboard table."""
    print("\n" + "=" * 100)
    print("LEADERBOARD".center(100))
    print("=" * 100)

    header = (
        f"{'Rank':<6} {'Team':<22} {'Subs':<6} "
        f"{'Overall':<10} {'Accuracy':<10} {'Complete':<10} "
        f"{'Action':<10} {'Clarity':<10} {'Context':<10}"
    )
    print(header)
    print("-" * len(header))

    for i, t in enumerate(teams, 1):
        rank = f"#{i}"
        line = (
            f"{rank:<6} {t['team']:<22} {t['submissions']:<6} "
            f"{t['overall']:<10.3f} "
            f"{t['accuracy']:<10.3f} "
            f"{t['completeness']:<10.3f} "
            f"{t['actionability']:<10.3f} "
            f"{t['clarity']:<10.3f} "
            f"{t['context_awareness']:<10.3f}"
        )
        print(line)

    # Print average row
    if teams:
        avg_overall = sum(t["overall"] for t in teams) / len(teams)
        dim_avgs = {
            "accuracy": sum(t["accuracy"] for t in teams) / len(teams),
            "completeness": sum(t["completeness"] for t in teams) / len(teams),
            "actionability": sum(t["actionability"] for t in teams) / len(teams),
            "clarity": sum(t["clarity"] for t in teams) / len(teams),
            "context_awareness": sum(t["context_awareness"] for t in teams)
            / len(teams),
        }
        avg_line = (
            f"{'AVG':<6} {'':<22} {sum(t['submissions'] for t in teams):<6} "
            f"{avg_overall:<10.3f} "
            f"{dim_avgs['accuracy']:<10.3f} "
            f"{dim_avgs['completeness']:<10.3f} "
            f"{dim_avgs['actionability']:<10.3f} "
            f"{dim_avgs['clarity']:<10.3f} "
            f"{dim_avgs['context_awareness']:<10.3f}"
        )
        print("-" * len(header))
        print(avg_line)

    print("=" * 100)


def main():
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if len(sys.argv) > 1:
        results_path = Path(sys.argv[1])
    else:
        results_path = DEFAULT_RESULTS_PATH

    print(f"Reading new results from: {results_path}")

    # Parse and merge
    new_subs = parse_results(results_path)
    skipped = load_skipped()
    hashes = load_submission_hashes()

    if not new_subs and not skipped:
        print("ERROR: No team scores or cached submissions found.", file=sys.stderr)
        return 1

    teams_data = merge_and_group(new_subs, skipped, hashes, now_iso)
    team_rows = compute_averages(teams_data)

    # CLI Report
    print_leaderboard(team_rows)

    # Canonical Log
    latest_data = write_latest_json(teams_data, now_iso)

    # history snapshots only on actual runs
    if new_subs:
        write_history_json(latest_data, now_iso)

    # Markdown version
    write_leaderboard_md(team_rows, now_iso)

    # Artifact compatibility
    output_file = REPO_ROOT / ".promptfoo" / "leaderboard.txt"
    with open(output_file, "w") as f:
        original_stdout = sys.stdout
        sys.stdout = f
        print_leaderboard(team_rows)
        sys.stdout = original_stdout
    print(f"\nResults committed to {RESULTS_DIR}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
