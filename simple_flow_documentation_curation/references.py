from __future__ import annotations

from dataclasses import dataclass
import re

from simple_flow_documentation_curation.models import NormalizedHistoryPackage


REFERENCE_RE = re.compile(r"^(?P<kind>issue|pr|commit):(?P<id>[^#]+)(?P<anchor>#.+)?$")


@dataclass(frozen=True)
class ResolvedReference:
    reference: str
    url: str
    kind: str


class ReferenceResolver:
    def __init__(self, package: NormalizedHistoryPackage):
        self.package = package

    def resolve(self, reference: str) -> ResolvedReference:
        match = REFERENCE_RE.fullmatch(reference)
        if not match:
            raise ValueError(f"Unsupported reference format: {reference}")

        kind = match.group("kind")
        identifier = match.group("id")
        anchor = match.group("anchor") or ""
        if kind == "issue":
            item_id = f"issue:{int(identifier)}"
            if item_id not in self.package.item_ids:
                raise ValueError(f"Unknown reference: {reference}")
            return ResolvedReference(reference, _repo_url(self.package.repository, f"issues/{identifier}{anchor}"), kind)
        if kind == "pr":
            item_id = f"pr:{int(identifier)}"
            if item_id not in self.package.item_ids:
                raise ValueError(f"Unknown reference: {reference}")
            return ResolvedReference(reference, _repo_url(self.package.repository, f"pull/{identifier}{anchor}"), kind)
        if kind == "commit":
            if identifier not in self.package.commit_shas:
                raise ValueError(f"Unknown reference: {reference}")
            return ResolvedReference(reference, _repo_url(self.package.repository, f"commit/{identifier}{anchor}"), kind)
        raise ValueError(f"Unsupported reference format: {reference}")

    def validate_all(self, references: tuple[str, ...] | list[str]) -> list[ResolvedReference]:
        return [self.resolve(reference) for reference in references]


def _repo_url(repository: str, suffix: str) -> str:
    clean = repository.removeprefix("https://github.com/").removesuffix(".git").strip("/")
    if not clean:
        return suffix
    return f"https://github.com/{clean}/{suffix}"
