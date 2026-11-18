#!/usr/bin/env python3
"""Scans the repository for API keys, passwords, personal paths, and emails before publishing.
Usage: python scripts/check_secrets.py [path]   (exit code 1 if anything is found)"""
import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", "data", "__pycache__", ".venv", "node_modules"}
SKIP_FILES = {"check_secrets.py", "test_hygiene.py"}  # contain fake secrets on purpose, to test the scanner
SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".zip", ".db", ".pyc"}
DATA_URI = re.compile(r"data:[\w/+.-]+;base64,[A-Za-z0-9+/=]+")
RULES = [
    ("API key", re.compile(r"\b(sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35})")),
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("plaintext credential", re.compile(r"(?i)\b(api[_-]?key|secret|passw(?:or)?d|token)\b\s*[:=]\s*['\"][^'\"\s]{8,}['\"]")),
    ("personal path", re.compile(r"(?i)(?:[A-Z]:[\\/]Users[\\/](?!<|%|Public|Default|\{)[^\\/\s'\"]+|/Users/(?!<|Shared)[^/\s'\"]+/|/home/(?!<|runner|user/)[^/\s'\"]+/)")),
    ("email address", re.compile(r"\b[\w.+-]+@(?!example\.|users\.noreply\.github\.com)[\w-]+\.[\w.-]+\b")),
]


def scan(root):
    findings = []
    for path in sorted(Path(root).rglob("*")):
        if not path.is_file() or path.suffix.lower() in SKIP_SUFFIX or SKIP_DIRS & set(path.parts):
            continue
        if path.name in SKIP_FILES:
            continue
        try:
            text = DATA_URI.sub("data:…", path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for label, rule in RULES:
                if rule.search(line):
                    findings.append((str(path.relative_to(root)), number, label, line.strip()[:90]))
    return findings


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent)
    findings = scan(root)
    for file, number, label, line in findings:
        print("%s:%d  [%s]  %s" % (file, number, label, line))
    print("No findings." if not findings else "\n%d finding(s): review them before publishing." % len(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
