from __future__ import annotations

from fnmatch import fnmatch
from pathlib import PurePosixPath

from simple_flow_gates.contracts import ContractError, IssueContract


def validate_scope_gate(issue: IssueContract, changed_files: list[str]) -> None:
    patterns = issue.scope_patterns
    if not patterns:
        raise ContractError("Issue scope must declare at least one allowed path or pattern.")

    outside = [
        path for path in _normalize_files(changed_files) if not _matches_any(path, patterns)
    ]
    if outside:
        raise ContractError(
            "Changed file(s) outside issue scope: " + ", ".join(sorted(outside))
        )


def validate_documentation_gate(issue: IssueContract, changed_files: list[str]) -> None:
    required_docs = issue.documentation_impact
    if not required_docs:
        return

    normalized_files = _normalize_files(changed_files)
    missing = [doc for doc in required_docs if not _matches_any_doc(doc, normalized_files)]
    if missing:
        raise ContractError(
            "Documentation Impact requires changes to: " + ", ".join(missing)
        )


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(_match_path(path, pattern) for pattern in patterns)


def _matches_any_doc(doc_pattern: str, changed_files: list[str]) -> bool:
    return any(_match_path(path, doc_pattern) for path in changed_files)


def _match_path(path: str, pattern: str) -> bool:
    normalized_pattern = _normalize_path(pattern)
    if fnmatch(path, normalized_pattern):
        return True
    if normalized_pattern.endswith("/"):
        return path.startswith(normalized_pattern)
    if not any(char in normalized_pattern for char in "*?[]"):
        return path == normalized_pattern or path.startswith(normalized_pattern.rstrip("/") + "/")
    return False


def _normalize_files(files: list[str]) -> list[str]:
    return [_normalize_path(path) for path in files]


def _normalize_path(path: str) -> str:
    return PurePosixPath(path.replace("\\", "/")).as_posix().lstrip("./")

