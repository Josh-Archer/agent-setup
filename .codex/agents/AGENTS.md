# Codex Agents

These project agents are the repository-specific layer for `C:\code\home`.
They should stay aligned in intent with the parallel definitions under:

- `.claude/agents/`
- `.gemini/agents/`
- `.github/agents/`
- `C:\Users\Josh\.codex\agents\` for generic home-level Codex agents

Project agents should carry repo-specific constraints, scripts, and paths.
Global agents should stay generic and reusable across repositories.

## Canonical Role Map
- `architecture`: high-level structure and GitOps design
- `development`: implementation, maintenance, and local tooling
- `documentation`: runbooks, guides, and operational notes
- `docs-scribe`: lightweight README and usage-doc maintenance
- `debugger`: bug isolation, discrepancy analysis, and root-cause identification
- `manager`: orchestration, planning, and handoffs
- `product-development`: requirements, rollout plans, and release readiness
- `testing`: CI-readiness and validation execution
- `gitops-architect`: manifest planning and ArgoCD alignment
- `security-auditor`: diff and configuration risk review
- `validation-runner`: focused validation and environment setup
- `junior`: fast, low-risk support work and boilerplate

## Role: Architecture
- **Model:** gpt-5.4
- **Goal:** Review architecture and GitOps design choices at a high level.

## Role: Development
- **Model:** gpt-5.4-mini
- **Goal:** Execute local tooling, maintenance, and implementation workflows.

## Role: Documentation
- **Model:** gpt-5.4
- **Goal:** Maintain runbooks, guides, and operational notes.

## Role: Docs Scribe
- **Model:** gpt-5-mini
- **Goal:** Maintain README and usage documentation for scripts and workflows.

## Role: Debugger
- **Model:** gpt-5.4
- **Goal:** Find bugs, mismatches with docs, and root causes before proposing fixes.

## Role: Manager
- **Model:** gpt-5.4
- **Goal:** Orchestrate complex requests across the right agents and skills.

## Role: Product Development
- **Model:** gpt-5.4
- **Goal:** Translate product requirements into safe rollout plans.

## Role: Testing
- **Model:** gpt-5.4-mini
- **Goal:** Run repo testing and validation workflows for CI readiness.

## Role: GitOps Architect
- **Model:** gpt-5.4
- **Goal:** Plan manifest-driven changes and ensure ArgoCD alignment.

## Role: Security Auditor
- **Model:** o2-preview
- **Goal:** Review diffs for security issues, unsafe scripts, and configuration drift.

## Role: Validation Runner
- **Model:** gpt-5.3-codex-spark
- **Goal:** Execute Codex validation and environment setup workflows.

## Role: Junior
- **Model:** gpt-5.3-codex-spark
- **Goal:** Documentation, unit test boilerplate, and repetitive low-risk support work.
