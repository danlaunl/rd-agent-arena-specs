# RD-Specs Competition: From GitHub Issues to Requirements

Build a multi-agent system that analyzes real GitHub issues and produces high-quality requirements specifications. Run your agents yourself, then submit the outputs for scoring.

## Your Task

Design a **3-agent pipeline** that takes a GitHub issue as input and outputs a polished requirements document. Your agents must work together to:

1. **Reverse-engineer** the issue — understand the underlying problem, affected code, and context
2. **Write requirements** — draft formal specifications from the analysis
3. **Review and refine** — validate the requirements for completeness and correctness

You run your own agents using any tools and models you choose. When you're happy with the results, submit the outputs to this repo for scoring.

## Agent Roles

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
agents:
  reverse-engineer:
    model: gpt-4o
    provider: openai
  requirements-writer:
    model: gpt-4o
    provider: openai
  requirements-reviewer:
    model: gpt-4o
    provider: openai
submitted_at: 2025-11-20T14:30:00Z
notes: ""
```

#### `prompts/reverse-engineer.txt` — the prompt you gave Agent 1
#### `prompts/requirements-writer.txt` — the prompt you gave Agent 2
#### `prompts/requirements-reviewer.txt` — the prompt you gave Agent 3

Feel free to add more directories / files under "prompts" or under "001" with the
skills you gave your agents, and other relevant link files. (tools, SKILL.md, etc)

#### `output.txt` — the final requirements document from Agent 3

This is the file that gets scored. It should contain the reviewed, final requirements your pipeline produced for the issue referenced in `metadata.yaml`. **No manual edits allowed** — this must be the raw output of your agent pipeline.

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

## Rules

1. You may use any LLM provider and model you choose (OpenAI, Anthropic, local, etc.) — you run your own agents
2. You must use exactly 3 agents: reverse engineer, requirements writer, requirements reviewer
3. Submit only files within your `submissions/<team-name>/` directory
4. `output.txt` must be the exact final output of your 3-agent pipeline — no manual edits allowed
5. Prompts must not hard-code specific issue content — they should be general-purpose
6. You may submit outputs for multiple issues to improve your average score
7. Number your submission folders sequentially (001, 002, 003, ...)

## Example Issue

Here's a sample issue your agents might analyze:

> **node-glob #637:** "yesterday version 10.5.0 has vulnerabilities"
>
> A security vulnerability was published with an incorrect version range (`>= 10.3.7, <= 11.0.3` instead of `>=10.3.7 <10.5.0 || >=11.0.0 <11.1.0`). The advisory database PR was merged to correct the range. Downstream packages (nyc, globby) broke when users force-upgraded due to API changes between major versions.

A winning submission would produce requirements covering:
- Correct identification of the incorrect vulnerability range
- The actual vulnerable vs. safe versions
- Downstream breakage from forced upgrades
- The advisory database fix process
- Follow-up actions (e.g., v9 patch in #639)

## Questions?

Open an issue in this repo or contact the competition organizers.
