#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import io
import os
import re
import subprocess
import sys
from pathlib import Path


TEXT_EXTENSIONS = {
    ".conf",
    ".config",
    ".csv",
    ".cs",
    ".cshtml",
    ".html",
    ".js",
    ".json",
    ".jsonl",
    ".jsx",
    ".md",
    ".ndjson",
    ".props",
    ".ps1",
    ".psm1",
    ".resx",
    ".sql",
    ".targets",
    ".ts",
    ".tsv",
    ".txt",
    ".tsx",
    ".xml",
    ".yaml",
    ".yml",
}

MAX_FILE_SIZE_BYTES = 1_000_000
GITIGNORE_BLOCK_START = "# Auto-blocked by PII guard"
GITIGNORE_BLOCK_END = "# End auto-blocked by PII guard"

SAFE_VALUE_TOKENS = {
    "",
    "<redacted>",
    "<masked>",
    "<example>",
    "example",
    "example value",
    "sample",
    "sample data",
    "synthetic",
    "placeholder",
    "test",
    "fake",
    "n/a",
    "na",
    "null",
    "none",
    "unknown",
}

SAFE_PATH_PREFIXES = (
    ".github/",
)

SAFE_FILE_NAMES = {
    ".gitignore",
    ".gitleaks.toml",
    ".pre-commit-config.yaml",
    "contributing.md",
    "security.md",
}

NAME_LABEL_RE = re.compile(
    r"(?im)^\s*(?:full[_ -]?name|employee[_ -]?name|customer[_ -]?name|contact[_ -]?name|person[_ -]?name|name)\s*[:=,]\s*([A-Z][a-z]+(?:[-'][A-Z]?[a-z]+)?(?:\s+[A-Z][a-z]+(?:[-'][A-Z]?[a-z]+)?){1,3})\s*$"
)
TITLE_LABEL_RE = re.compile(
    r"(?im)^\s*(?:job[_ -]?title|employee[_ -]?title|position|designation|title)\s*[:=,]\s*([A-Za-z][A-Za-z ,&/()-]{2,60})\s*$"
)
ADDRESS_LABEL_RE = re.compile(
    r"(?im)^\s*(?:address|street[_ -]?address|mailing[_ -]?address|home[_ -]?address)\s*[:=,]\s*([^\r\n]+)\s*$"
)
STREET_ADDRESS_RE = re.compile(
    r"(?i)\b\d{1,6}\s+[A-Za-z0-9][A-Za-z0-9.\- ]+\s(?:street|st|avenue|ave|road|rd|lane|ln|drive|dr|boulevard|blvd|court|ct|circle|cir|way|parkway|pkwy|place|pl|terrace|ter)\b"
)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})(?!\w)"
)
SSN_RE = re.compile(r"\b(?!000|666|9\d\d)\d{3}[- ]?(?!00)\d{2}[- ]?(?!0000)\d{4}\b")

SENSITIVE_KEYS = {
    "first_name": "first name field",
    "firstname": "first name field",
    "last_name": "last name field",
    "lastname": "last name field",
    "full_name": "full name field",
    "fullname": "full name field",
    "employee_name": "employee name field",
    "customer_name": "customer name field",
    "contact_name": "contact name field",
    "person_name": "person name field",
    "job_title": "job title field",
    "employee_title": "job title field",
    "position": "job title field",
    "designation": "job title field",
    "address": "address field",
    "address1": "address field",
    "address2": "address field",
    "street": "street field",
    "street_address": "street address field",
    "mailing_address": "mailing address field",
    "home_address": "home address field",
    "city": "city field",
    "state": "state field",
    "province": "province field",
    "postal_code": "postal code field",
    "postcode": "postal code field",
    "zip": "postal code field",
    "zip_code": "postal code field",
    "email": "email field",
    "email_address": "email field",
    "phone": "phone field",
    "phone_number": "phone field",
    "mobile": "phone field",
    "cell": "phone field",
}

LOW_CONFIDENCE_REASONS = {
    "job title label",
    "job title field",
    "city field",
    "state field",
    "province field",
    "postal code field",
}


def run_git(repo_root: Path, args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=check,
        text=True,
        capture_output=True,
    )


def get_repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        text=True,
        capture_output=True,
    )
    return Path(result.stdout.strip())


def get_target_files(repo_root: Path, staged_only: bool) -> list[str]:
    if staged_only:
        result = run_git(repo_root, ["diff", "--cached", "--name-only", "--diff-filter=ACMR"])
    else:
        result = run_git(repo_root, ["ls-files"])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def is_safe_value(value: str) -> bool:
    normalized = value.strip().strip('"\'').lower()
    if not normalized:
        return True
    if normalized in SAFE_VALUE_TOKENS:
        return True
    if "example.com" in normalized or "example.org" in normalized or "example.net" in normalized:
        return True
    if normalized.startswith("xxx") or normalized.startswith("redacted") or normalized.startswith("masked"):
        return True
    return False


def looks_like_text(path: Path) -> bool:
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return False
    if path.stat().st_size > MAX_FILE_SIZE_BYTES:
        return False

    with path.open("rb") as handle:
        sample = handle.read(2048)
    return b"\x00" not in sample


def should_skip_path(relative_path: str) -> bool:
    normalized = relative_path.replace("\\", "/")
    if normalized.startswith(SAFE_PATH_PREFIXES):
        return True
    return Path(normalized).name.lower() in SAFE_FILE_NAMES


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def add_reason(reasons: set[str], reason: str) -> None:
    reasons.add(reason)


def detect_regex_patterns(text: str, reasons: set[str]) -> None:
    for match in NAME_LABEL_RE.finditer(text):
        if not is_safe_value(match.group(1)):
            add_reason(reasons, "labeled person name")
            break

    for match in TITLE_LABEL_RE.finditer(text):
        if not is_safe_value(match.group(1)):
            add_reason(reasons, "job title label")
            break

    for match in ADDRESS_LABEL_RE.finditer(text):
        if not is_safe_value(match.group(1)):
            add_reason(reasons, "labeled address")
            break

    if STREET_ADDRESS_RE.search(text):
        add_reason(reasons, "street address")

    for match in EMAIL_RE.finditer(text):
        if not is_safe_value(match.group(0)):
            add_reason(reasons, "email address")
            break

    for match in PHONE_RE.finditer(text):
        value = match.group(0)
        digits = re.sub(r"\D", "", value)
        if re.search(r"55501\d{2}$", digits):
            continue
        if not is_safe_value(value):
            add_reason(reasons, "phone number")
            break

    if SSN_RE.search(text):
        add_reason(reasons, "social security number")


def detect_key_value_pairs(text: str, reasons: set[str]) -> None:
    key_value_pattern = re.compile(r'(?im)["\']?([A-Za-z][A-Za-z0-9_ -]{1,40})["\']?\s*[:=]\s*["\']?([^\r\n,}{]{1,120})')
    for match in key_value_pattern.finditer(text):
        key = normalize_key(match.group(1))
        value = match.group(2).strip()
        if key not in SENSITIVE_KEYS:
            continue
        if is_safe_value(value):
            continue
        add_reason(reasons, SENSITIVE_KEYS[key])


def detect_csv_headers(path: Path, text: str, reasons: set[str]) -> None:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        rows = list(reader)
    except csv.Error:
        return

    if not rows:
        return

    header = [normalize_key(column) for column in rows[0]]
    matching = [SENSITIVE_KEYS[key] for key in header if key in SENSITIVE_KEYS]
    if len(set(matching)) < 2:
        return

    sample_rows = rows[1:4]
    if not sample_rows:
        return

    add_reason(reasons, f"sensitive dataset columns: {', '.join(sorted(set(matching))[:4])}")


def classify_reasons(reasons: set[str]) -> bool:
    if not reasons:
        return False

    strong_reasons = [reason for reason in reasons if reason not in LOW_CONFIDENCE_REASONS]
    weak_reasons = [reason for reason in reasons if reason in LOW_CONFIDENCE_REASONS]

    if strong_reasons:
        return True
    return len(weak_reasons) >= 2


def detect_file_pii(path: Path) -> list[str]:
    if not looks_like_text(path):
        return []

    text = read_text(path)
    reasons: set[str] = set()

    detect_regex_patterns(text, reasons)
    detect_key_value_pairs(text, reasons)

    if path.suffix.lower() in {".csv", ".tsv"}:
        detect_csv_headers(path, text, reasons)

    if not classify_reasons(reasons):
        return []

    return sorted(reasons)


def update_gitignore(repo_root: Path, relative_paths: list[str]) -> bool:
    gitignore_path = repo_root / ".gitignore"
    existing_lines: list[str] = []
    if gitignore_path.exists():
        existing_lines = gitignore_path.read_text(encoding="utf-8", errors="ignore").splitlines()

    tracked_entries = {
        line.strip()
        for line in existing_lines
        if line.strip() and not line.strip().startswith("#")
    }

    new_entries = [path for path in relative_paths if path not in tracked_entries]
    if not new_entries:
        return False

    start_index = next((index for index, line in enumerate(existing_lines) if line == GITIGNORE_BLOCK_START), None)
    end_index = next((index for index, line in enumerate(existing_lines) if line == GITIGNORE_BLOCK_END), None)

    managed_entries: list[str] = []
    if start_index is not None and end_index is not None and end_index > start_index:
        managed_entries = [
            line.strip()
            for line in existing_lines[start_index + 1 : end_index]
            if line.strip() and not line.strip().startswith("#")
        ]

    merged_entries = sorted(set(managed_entries + new_entries))
    managed_block = [GITIGNORE_BLOCK_START, *merged_entries, GITIGNORE_BLOCK_END]

    if start_index is not None and end_index is not None and end_index > start_index:
        updated_lines = existing_lines[:start_index] + managed_block + existing_lines[end_index + 1 :]
    else:
        updated_lines = existing_lines[:]
        if updated_lines and updated_lines[-1] != "":
            updated_lines.append("")
        updated_lines.extend(managed_block)

    gitignore_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
    return True


def untrack_detected_files(repo_root: Path, relative_paths: list[str]) -> None:
    for relative_path in relative_paths:
        subprocess.run(
            ["git", "rm", "--cached", "--quiet", "--", relative_path],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )


def stage_gitignore(repo_root: Path) -> None:
    subprocess.run(["git", "add", ".gitignore"], cwd=repo_root, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect likely PII content in repository files.")
    parser.add_argument("--staged-only", action="store_true", help="Inspect only staged files.")
    parser.add_argument("--update-gitignore", action="store_true", help="Add detected file paths to .gitignore.")
    parser.add_argument("--untrack-detected", action="store_true", help="Remove detected files from the git index.")
    args = parser.parse_args()

    repo_root = get_repo_root()
    target_files = get_target_files(repo_root, staged_only=args.staged_only)

    if not target_files:
        print("No files to inspect.")
        return 0

    violations: dict[str, list[str]] = {}
    for relative_path in target_files:
        if should_skip_path(relative_path):
            continue
        file_path = repo_root / relative_path
        if not file_path.exists():
            continue
        reasons = detect_file_pii(file_path)
        if reasons:
            violations[relative_path.replace("\\", "/")] = reasons

    if not violations:
        print(f"PII guard passed for {len(target_files)} file(s).")
        return 0

    detected_files = sorted(violations)
    gitignore_updated = False
    if args.update_gitignore:
        gitignore_updated = update_gitignore(repo_root, detected_files)
        if gitignore_updated:
            stage_gitignore(repo_root)

    if args.untrack_detected:
        untrack_detected_files(repo_root, detected_files)

    print("PII guard detected likely sensitive content:", file=sys.stderr)
    for relative_path in detected_files:
        print(f" - {relative_path}: {', '.join(violations[relative_path])}", file=sys.stderr)

    if gitignore_updated:
        print("Detected file paths were added to .gitignore.", file=sys.stderr)
    if args.untrack_detected:
        print("Detected files were removed from the git index.", file=sys.stderr)

    return 1


if __name__ == "__main__":
    sys.exit(main())
