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


def bump_baseline_metadata(text: str, date: str) -> str:
    version_match = re.search(r"^Version:\s*(?P<version>\S+)", text, flags=re.MULTILINE)
    if not version_match:
        raise ValueError("Baseline metadata is missing Version.")
    updated = re.sub(
        r"^Version:\s*\S+",
        f"Version: {bump_version(version_match.group('version'))}",
        text,
        flags=re.MULTILINE,
    )
    return set_last_updated(updated, date)


def update_component_index_timestamp(text: str, component_id: str, date: str) -> str:
    lines = text.splitlines()
    updated: list[str] = []
    changed = False
    for line in lines:
        cells = _table_cells(line)
        if len(cells) == 6 and cells[0] == component_id:
            cells[-1] = date
            updated.append("| " + " | ".join(cells) + " |")
            changed = True
        else:
            updated.append(line)
    if not changed:
        raise ValueError(f"Component not found in Component Index: {component_id}")
    ending = "\n" if text.endswith("\n") else ""
    return "\n".join(updated) + ending


def _table_cells(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    return [cell.strip() for cell in stripped.strip("|").split("|")]
