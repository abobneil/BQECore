# Contributing

This repository is intended to remain safe for public distribution.

## Required data handling rules

- Never commit production data, customer exports, employee information, support dumps, or database backups.
- Never commit secrets, API keys, passwords, certificates, SSH keys, or inline connection strings.
- Use synthetic or fully sanitized fixtures only.
- Store runtime secrets in a secret manager or local environment variables, not in the repository.
- When adding a new config file, commit a sample such as `.env.example`, not the real secret-bearing file.

## Local guardrails

Install the pre-commit hooks so the same checks run before your commits:

```powershell
python -m pip install pre-commit
pre-commit install
```

Run the checks manually at any time:

```powershell
pre-commit run --all-files
```

The local PII guard will block likely people-data files and, when it detects them in staged changes, it will:

- add the offending file path to `.gitignore`
- remove the file from the git index so it cannot be committed accidentally
- fail the commit until the file is sanitized or removed

## Pull requests

Every pull request must pass the leak-detection workflow and satisfy the checklist in `.github/pull_request_template.md`.
