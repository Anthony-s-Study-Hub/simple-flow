from __future__ import annotations

import re


def bump_version(version: str) -> str:
    match = re.fullmatch(r"v(?P<major>\d+)\.(?P<minor>\d+)", version.strip())
    if not match:
        raise ValueError(f"Unsupported baseline version format: {version}")
    return f"v{int(match.group('major'))}.{int(match.group('minor')) + 1}"


def set_last_updated(text: str, date: str) -> str:
    if re.search(r"^Last Updated:", text, flags=re.MULTILINE):
        return re.sub(r"^Last Updated:.*$", f"Last Updated: {date}", text, flags=re.MULTILINE)
    return text.rstrip() + f"\nLast Updated: {date}\n"
