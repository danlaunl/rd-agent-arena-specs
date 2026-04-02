# Dynamic Issue Retrieval Strategy

## Goal

Fetch real GitHub issues at evaluation time so the competition tests against fresh, varied data rather than a static hardcoded set.

## Approach

### 1. Curated Issue Registry

A `issues/registry.json` file defines the pool of issues to draw from:

```json
{
  "repos": [
    {
      "owner": "isaacs",
      "repo": "node-glob",
      "issues": [637, 483, 529]
    },
    {
      "owner": "expressjs",
      "repo": "express",
      "issues": [5671, 4972]
    }
  ],
  "selection": {
    "difficulty": ["easy", "medium", "hard"],
    "types": ["bug", "feature", "support", "security"]
  }
}
```

Maintainers curate this list. Issues are chosen for:
- Clear descriptions with enough context
- Meaningful comment threads
- Varied types (bugs, features, security, support)
- Range of difficulty

### 2. Fetch Pipeline

```
registry.json ──► fetch-issues.js ──► issues/cache/*.json
                                          │
                                          ▼
                                   build-testcases.js
                                          │
                                          ▼
                                   promptfoo test cases (YAML/JSON)
```

**`fetch-issues.js`**:
- Reads the registry
- Calls GitHub REST API for each issue (title, body, labels, comments)
- Handles rate limits (authenticated: 5000/hr, unauthenticated: 60/hr)
- Caches results in `issues/cache/` with TTL
- Outputs normalized JSON per issue

**`build-testcases.js`**:
- Reads cached issue JSON
- Generates promptfoo test case format:
  ```yaml
  tests:
    - description: "node-glob #637: version 10.5.0 vulnerabilities"
      vars:
        issue_title: "yesterday version 10.5.0 has vulnerabilities"
        issue_body: "..."
        issue_comments: "..."
        repo_name: "isaacs/node-glob"
        issue_labels: ""
        issue_url: "https://github.com/isaacs/node-glob/issues/637"
  ```

### 3. Rate Limit & Auth Strategy

| Scenario | Approach |
|----------|----------|
| CI/CD pipeline | Use `GITHUB_TOKEN` env var for authenticated API access |
| Local dev | Fall back to unauthenticated (60 req/hr) with caching |
| Offline | Use pre-cached issues in `issues/cache/` |
| Demo/contest day | Pre-fetch all issues to cache before the event |

### 4. Fallback & Resilience

- If an issue fetch fails (404, rate limit), skip it and log a warning
- Cache has a 24-hour TTL; stale cache is used if refetch fails
- Minimum viable set: at least 5 issues must be available to run an eval
- A `issues/fallback/` directory ships with 3-5 pre-fetched issues for zero-setup demos

### 5. Issue Selection Criteria

When curating the registry, prefer issues that:

1. **Have clear problem statements** — teams should be able to identify the core issue
2. **Include comments** — tests the agents' ability to synthesize discussion
3. **Are representative** — bugs, features, security, support, breaking changes
4. **Have resolution context** — closed issues where the outcome is known (useful for grading)
5. **Vary in complexity** — some issues are straightforward bugs, others require understanding ecosystem context

### 6. Contest-Day Flow

1. **Pre-event**: Maintain fetches registry with all issue IDs
2. **T-24h**: Run `fetch-issues.js` to cache everything
3. **T-0**: Teams submit their agent configs
4. **Evaluation**: `build-testcases.js` generates tests from cache, promptfoo runs eval
5. **Scoring**: llm-rubric grades each team's output

### 7. Adding New Issues

To add a new issue to the pool:
1. Add the owner/repo/number to `issues/registry.json`
2. Run `npm run fetch-issues` to cache it
3. Optionally tag it with difficulty and type metadata
