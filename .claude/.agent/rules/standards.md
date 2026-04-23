---
trigger: always_on
---

# Agent Developer Guide (Antigravity Edition)
---
activation: always-on
---
## General Principles
- **ArgoCD Priority**: All deployments MUST go through ArgoCD. No manual `kubectl` edits.
- **Modularity**: Components must be logical and isolated (e.g., `grok-servaar/dns-system`).
- **Idempotency**: All scripts must be safe to run multiple times.
- **Node Onboarding**: Use Tailscale-first scripts (`scripts/setup-remote-node.sh` or `scripts/migrate_node_to_tailscale.sh`).

## Python Development
- **Style**: PEP 8 with mandatory type hints.
- **Config**: Use `os.getenv` for secrets; strictly no hardcoded strings.

## Kubernetes Verification
- Before submitting a manifest change, use the argocd pod and the argocd command on it the validate the sync statuses. If it is breaking before your commit, alert the user to intervene. 