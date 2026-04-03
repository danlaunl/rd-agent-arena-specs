# RD-Specs Competition: From GitHub Issues to Requirements

Build a multi-agent system that analyzes real GitHub issues and produces high-quality requirements specifications. Run your agents yourself, then submit the outputs for scoring.

## Your Task

Create a **3-agent system** that takes a GitHub issue as input (preferably without the comments(?)) and outputs a polished requirements document. Your agents must work together to:

1. **Reverse-engineer** the issue from code — understand the underlying problem, affected code, and context
2. **Write requirements** — draft formal specifications from the analysis
3. **Review and refine** — validate the requirements for completeness and correctness

Run [custom agents](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/create-custom-agents). When the results seem like they are ok, and aren't getting better without a different approach, submit the outputs to this repo for scoring.

## EXAMPLE Agent Roles

### Agent 1: Reverse Engineer
- **Input:** Raw GitHub issue (title, body, comments, metadata)
- **Goal:** Identify the core problem, trace root causes, surface implicit requirements and constraints
- **Output:** Structured analysis document

### Agent 2: Requirements Writer
- **Input:** Reverse Engineer's analysis + original issue
- **Goal:** Transform the analysis into formal requirements with user stories, acceptance criteria, and technical specifications
- **Output:** Requirements document draft

### Agent 3: Requirements Reviewer
- **Input:** Requirements draft + original issue + Reverse Engineer analysis
- **Goal:** Validate accuracy, check completeness, improve clarity, identify edge cases
- **Output:** Final reviewed requirements document (this is what you submit)

## How to Submit

### 1. Create your team directory

```bash
mkdir -p submissions/your-team-name/submissions
```

### 2. Add team info

Create `submissions/your-team-name/team.yaml`:

```yaml
name: Your Team Name
members:
  - Alice
  - Bob
contact: your-team@example.com
```

### 3. Add one or more submissions

Each submission is a numbered folder representing your agents' output for **one** GitHub issue. You can submit as many as you want.

```bash
mkdir -p submissions/your-team-name/submissions/001/prompts
```

Each submission folder must contain:

#### `metadata.yaml` — which issue your agents analyzed
```yaml
issue:
  owner: isaacs
  repo: node-glob
  number: 637
notes: ""
```

#### `prompts/reverse-engineer.txt` — the prompt you gave Agent 1
#### `prompts/requirements-writer.txt` — the prompt you gave Agent 2
#### `prompts/requirements-reviewer.txt` — the prompt you gave Agent 3

Feel free to add more directories / files under "prompts" or under "001" with the
skills you gave your agents, and other relevant link files. (tools, SKILL.md, etc)

#### `output.txt` — the final requirements document from Agent 3

This is the file that gets scored. It should contain the reviewed, final requirements your pipeline produced for the issue referenced in `metadata.yaml`. **No manual edits allowed (??)** — this must be the raw output of your agent pipeline.

### 4. Example directory structure

```
submissions/
└── your-team-name/
    ├── team.yaml
    └── submissions/
        ├── 001/                          # First issue
        │   ├── metadata.yaml             # e.g., node-glob #637
        │   ├── prompts/
        │   │   ├── reverse-engineer.txt
        │   │   ├── requirements-writer.txt
        │   │   └── requirements-reviewer.txt
        │   └── output.txt
        ├── 002/                          # Second issue
        │   ├── metadata.yaml             # e.g., express #5671
        │   ├── prompts/
        │   │   ├── reverse-engineer.txt
        │   │   ├── requirements-writer.txt
        │   │   └── requirements-reviewer.txt
        │   └── output.txt
        └── 003/                          # Third issue, etc.
            ├── metadata.yaml
            ├── prompts/
            │   ├── reverse-engineer.txt
            │   ├── requirements-writer.txt
            │   └── requirements-reviewer.txt
            └── output.txt
```

See `submissions/_example/` for a complete worked example.

### 5. Submit a PR

Fork this repo, add your `submissions/<team-name>/` directory, and open a pull request. The competition judges will run the scoring framework against your submissions.

## Scoring

Your `output.txt` files are graded by an LLM judge across 5 dimensions:

| Dimension | Weight | What it measures |
|-----------|--------|-----------------|
| **Accuracy** | 30% | Does the output correctly identify the core problem and details? |
| **Completeness** | 25% | Are all relevant details from the issue and comments captured? |
| **Actionability** | 20% | Could a developer pick up the requirements and implement them? |
| **Clarity** | 15% | Is the document well-structured and unambiguous? |
| **Context Awareness** | 10% | Does it show understanding of the broader ecosystem and edge cases? |

**Pass threshold:** 70% weighted average

Your final team score is the average across all your submissions.

## Suggested Rules

3. Submit only files within your `submissions/<team-name>/` directory
4. `output.txt` the exact final output of your 3-agent system? do we want manual edits allowed?
5. Prompts must not hard-code specific issue content — they should be general-purpose
7. Number your submission folders sequentially (001, 002, 003, ...)
8. only give agents access to the issue body, and not the subsequent comments? 

## Example Issue

Here's a [sample issue](https://github.com/isaacs/node-glob/issues/637) your agents might analyze:

> **node-glob #637:** "yesterday version 10.5.0 has vulnerabilities"

```json
{
  "vulnerabilities": {
    "glob": {
      "name": "glob",
      "severity": "high",
      "isDirect": false,
      "via": [
        {
          "source": 1109809,
          "name": "glob",
          "dependency": "glob",
          "title": "glob CLI: Command injection via -c/--cmd executes matches with shell:true",
          "url": "https://github.com/advisories/GHSA-5j98-mcp5-4vw2",
          "severity": "high",
          "cwe": [
            "CWE-78"
          ],
          "cvss": {
            "score": 7.5,
            "vectorString": "CVSS:3.1/AV:N/AC:H/PR:L/UI:N/S:U/C:H/I:H/A:H"
          },
          "range": ">=10.3.7 <=11.0.3"
        }
      ],
      "effects": [],
      "range": "10.3.7 - 11.0.3",
      "nodes": [
        "node_modules/glob"
      ],
      "fixAvailable": true
    }
  }
}
```

A winning submission might produce requirements, maybe without access to the issue comments,  covering:
- Correct identification of the incorrect vulnerability range
- The actual vulnerable vs. safe versions
- Downstream breakage from forced upgrades
- The advisory database fix process
- Follow-up actions 

