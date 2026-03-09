# Security controls for public release

This repository includes multiple controls to reduce the risk of leaking secrets or sensitive data:

- `.gitignore` blocks common local secret files, private keys, cloud credential folders, and export directories.
- `.pre-commit-config.yaml` runs local leak checks before commits when contributors install the hooks.
- `.gitleaks.toml` extends Gitleaks with extra rules for inline connection strings and likely SSNs.
- `scripts/prevent-sensitive-content.ps1` blocks known secret-bearing files and likely data exports.
- `scripts/pii-guard.py` detects likely person data such as names, job titles, addresses, emails, phone numbers, and structured personnel/customer datasets.
- The local PII guard automatically adds detected files to `.gitignore` and removes them from the git index before the commit can proceed.
- `.github/workflows/secret-and-sensitive-scan.yml` enforces scanning in CI for every push and pull request.
- `.github/pull_request_template.md` adds an explicit reviewer checklist.

## PII detection scope

The PII guard is heuristic-based. It is designed to catch common leaks in structured files and obvious free-text patterns, especially where labels such as `first_name`, `job_title`, `address`, `email`, or `phone` are present.

It reduces risk significantly, but it is not a substitute for using synthetic data and human review.

## GitHub settings to enable

Turn on these repository settings before making the repository public:

- Secret scanning
- Push protection
- Dependabot alerts
- Branch protection requiring pull requests and passing checks
- Require review from Code Owners after replacing placeholders in `.github/CODEOWNERS`
- Restricted direct pushes to the default branch

## If a leak is discovered

1. Revoke or rotate the credential immediately.
2. Remove the data from the repository and its history.
3. Assess whether external reporting or notification is required.
4. Tighten the relevant ignore, hook, or workflow rule so it cannot reoccur the same way.

Do not open public issues containing leaked values.
