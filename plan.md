# RD-Specs Promptfoo — Project Plan

## Overview

A promptfoo-based **competition framework** where contestant teams build multi-agent systems that analyze real GitHub issues and produce requirements specifications. Teams run their own agent pipelines externally and **submit the outputs** to this repo. The framework fetches the referenced issues and grades each submission using `llm-rubric` model-graded assertions.

## Architecture

```
  ┌─────────────────────────────────────────────────┐
  │         Team runs their own agents              │
  │  (outside this repo)                            │
  │                                                 │
  │  GitHub Issue ──► Agent 1: Reverse Engineer     │
  │                          │                      │
  │                          ▼                      │
  │                  Agent 2: Requirements Writer   │
  │                          │                      │
  │                          ▼                      │
  │                  Agent 3: Requirements Reviewer │
  │                          │                      │
  │                          ▼                      │
  │                  Final Requirements (output.txt) │
  └──────────────────────┬──────────────────────────┘
                         │
                         ▼  Team submits to this repo:
                submissions/<team>/submissions/<id>/
                  ├── metadata.yaml    (which issue, agent config)
                  ├── prompts/         (the prompts used)
                  └── output.txt       (final requirements)
                         │
                         ▼
              ┌──────────────────────┐
              │  This repo (judge)   │
              │                      │
              │  1. Read metadata    │
              │  2. Fetch issue      │
              │  3. llm-rubric grade │
              │  4. Aggregate scores │
              └──────────────────────┘
                         │
                         ▼
                    Team Score
```

## Key Components

### 1. Submission Format (teams submit outputs, framework judges them)

Each team creates a directory under `submissions/<team-name>/` containing one or more submissions. Each submission is a numbered folder with the output of their agent pipeline for a specific issue.

```
submissions/
└── team-alpha/
    ├── team.yaml                      # Team metadata (name, members)
    └── submissions/
        ├── 001/                       # First submission
        │   ├── metadata.yaml          # Which issue, agent config used
        │   ├── prompts/               # The 3 agent prompts used
        │   │   ├── reverse-engineer.txt
        │   │   ├── requirements-writer.txt
        │   │   └── requirements-reviewer.txt
        │   └── output.txt             # Final requirements document
        ├── 002/                       # Second submission (different issue)
        │   ├── metadata.yaml
        │   ├── prompts/
        │   │   ├── reverse-engineer.txt
        │   │   ├── requirements-writer.txt
        │   │   └── requirements-reviewer.txt
        │   └── output.txt
        └── ...                        # As many as they want
```

**`metadata.yaml`** — structured metadata for each submission:
```yaml
issue:
  owner: isaacs                        # GitHub repo owner
  repo: node-glob                      # GitHub repo name
  number: 637                          # Issue number
agents:
  reverse-engineer:
    model: gpt-4o                      # Model used
    provider: openai                   # Provider
  requirements-writer:
    model: gpt-4o
    provider: openai
  requirements-reviewer:
    model: gpt-4o
    provider: openai
submitted_at: 2025-11-20T14:30:00Z     # When the submission was created
notes: ""                              # Optional free-text notes
```

**`team.yaml`** — team-level info:
```yaml
name: Team Alpha
members:
  - Jane Doe
  - John Smith
contact: team-alpha@example.com
```

### 2. Issue Fetcher (`scripts/fetch_issues.py`)
- Reads all `metadata.yaml` files from submissions to discover which issues are referenced
- Queries GitHub API to fetch issue data (title, body, comments, labels)
- Caches results in `issues/cache/` for 24 hours
- Also supports a curated `issues/registry.json` for pre-fetching

### 3. Promptfoo Provider (`scripts/provider.py`)
- Python provider that reads `output.txt` files for promptfoo
- The "prompt" rendered by promptfoo is simply the path to the output file
- Returns the file contents as the model output for grading

### 4. Test Case Builder (`scripts/build_testcases.py`)
- Generates `promptfooconfig.yaml` from submissions and cached issues
- Creates one test case per submission
- Configures 5 llm-rubric assertions (one per scoring dimension)
- Uses template variables to inject issue context into grading prompts
- When running in GitHub Actions for a pull request, also posts the generated `promptfooconfig.yaml` into a PR comment for easy review

### 5. Promptfoo Config (`promptfooconfig.yaml`)
- Generated by `build_testcases.py`
- Uses Python provider to read submitted output.txt files
- Constructs test cases pairing outputs with their referenced issues
- Configures llm-rubric assertions for grading across 5 dimensions
- PR comment has two modes:
  - **Real PR mode** (GitHub Actions): posts/updates the generated YAML as a bot comment on the pull request so reviewers can inspect it without opening artifacts
  - **Local simulation mode** (`act`): when `ACT=true` is set (injected automatically by `act`), the comment body is written to `.promptfoo/pr-comment.md` instead of calling the GitHub API — no network call is made

### 4. Grading Rubric
Each submission is graded on:
- **Accuracy** (0-1): Does the response correctly identify the core problem?
- **Completeness** (0-1): Does it cover all relevant details from the issue and comments?
- **Actionability** (0-1): Does it suggest concrete next steps?
- **Clarity** (0-1): Is the analysis well-structured and easy to follow?
- **Context awareness** (0-1): Does it demonstrate understanding of the broader ecosystem?

## Workflow

1. **Teams build agents**: Teams design and run their own 3-agent pipelines externally
2. **Teams submit**: Teams create a directory under `submissions/<team-name>/` with their outputs and metadata
3. **Judge fetches**: `python scripts/fetch_issues.py` reads all submission metadata and fetches the referenced GitHub issues
4. **Judge builds**: `python scripts/build_testcases.py` generates `promptfooconfig.yaml` from submissions and cached issues, then:
   - On a real pull request (GitHub Actions): posts/updates the YAML as a bot comment on the PR
   - Under `act` (`ACT=true`): writes the comment body to `.promptfoo/pr-comment.md` for local inspection
5. **Judge evaluates**: `promptfoo eval` runs llm-rubric grading on all submissions
6. **Report**: `python scripts/leaderboard.py` generates a comparative leaderboard across all teams and submissions

**Or run all at once:**
```bash
npm run judge
```

## Example Issue (node-glob #637)

**Title:** "yesterday version 10.5.0 has vulnerabilities"
**Problem:** Security vulnerability published with incorrect version range (`>= 10.3.7, <= 11.0.3` instead of `>=10.3.7 <10.5.0 || >=11.0.0 <11.1.0`)
**Resolution:** Advisory database PR was merged to correct the range; related issues opened for v9 compatibility
**Side effects:** nyc, globby broke when forced to upgrade due to API changes between major versions

A good analysis should identify:
- The incorrect vulnerability range
- The actual vulnerable vs safe versions
- Downstream breakage from forced upgrades
- The advisory database fix
- The v9 follow-up issue (#639)

## Tech Stack

- **Runtime**: Python 3.12+, Node.js 18+
- **Evaluation**: promptfoo (latest)
- **Grading model**: Configurable (default: openai:gpt-4o)
- **Issue source**: GitHub REST API
- **Config format**: YAML

## File Structure

```
rd-specs-promptfoo/
├── plan.md                    # This file
├── strategy.md                # Dynamic issue retrieval strategy
├── README.md                  # Contestant instructions
├── promptfooconfig.yaml       # Generated by build_testcases.py
├── requirements.txt           # Python dependencies
├── package.json               # Node.js dependencies (promptfoo)
├── .github/
│   └── workflows/
│       └── judge.yml          # GitHub Actions workflow
├── scripts/
│   ├── fetch_issues.py        # Fetch issues referenced in submissions
│   ├── provider.py            # Promptfoo Python provider (reads output.txt)
│   ├── build_testcases.py     # Build promptfoo config from submissions
│   └── leaderboard.py         # Generate scoring report
├── submissions/               # Team submissions (committed to repo)
│   └── _example/              # Example submission showing expected format
│       ├── team.yaml
│       └── submissions/
│           └── 001/
│               ├── metadata.yaml
│               ├── prompts/
│               │   ├── reverse-engineer.txt
│               │   ├── requirements-writer.txt
│               │   └── requirements-reviewer.txt
│               └── output.txt
├── rubrics/
│   └── issue-analysis.txt     # The grading rubric documentation
└── issues/
    ├── registry.json          # Curated list of repos + issue numbers
    └── cache/                 # Fetched issue data (gitignored)
```

## Scoring

Each test case produces 5 sub-scores (Accuracy, Completeness, Actionability, Clarity, Context). The final team score is the weighted average:

| Dimension   | Weight |
|-------------|--------|
| Accuracy    | 0.30   |
| Completeness| 0.25   |
| Actionability| 0.20  |
| Clarity     | 0.15   |
| Context     | 0.10   |

Overall pass threshold: 0.7 (70%)

## Timeline

1. Framework setup (this repo)
2. Issue curation and fetching
3. Team onboarding (share README)
4. Submission window
5. Evaluation and leaderboard
