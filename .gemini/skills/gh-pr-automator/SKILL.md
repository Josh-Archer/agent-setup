---
name: gh-pr-automator
description: Automated PR review, remediation, and merge workflow using GitHub CLI. Use when you need to process open pull requests and coordinate group sign-off from specialists.
---
# GitHub PR Automator Skill

This skill automates the lifecycle of a Pull Request, from review to production validation.

## Workflow

1.  **List PRs**: Use `gh pr list` to identify open PRs requiring review.
2.  **Review & Checkout**: Use `gh pr checkout <number>` to switch to the PR branch. Analyze the diff and codebase.
3.  **Remediate**: If issues (lint, build, logic) are found, apply surgical fixes. Commit changes directly to the PR branch if authorized.
4.  **Group Sign-off**: Call the following sub-agents to validate the PR. Merge is ONLY permitted if all three provide a positive sign-off.
    -   **security-auditor**: `/agents call security-auditor "Review the security impact of this PR: <diff>"`
    -   **gitops-architect**: `/agents call gitops-architect "Validate ArgoCD and manifest alignment for this PR."`
    -   **tester**: `/agents call tester "Verify logic and generate/run unit tests for this change."`
5.  **Merge**: Once all agents approve, use `gh pr merge --merge --auto` to finalize.
6.  **Production Validation**: After merge, switch back to `main`, pull the changes, and use the **tester** agent to run production smoke tests.

## Tools
- `gh` CLI (installed on host)
- Specialized sub-agents (`security-auditor`, `gitops-architect`, `tester`)