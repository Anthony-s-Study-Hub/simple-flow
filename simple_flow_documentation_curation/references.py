from __future__ import annotations

from dataclasses import dataclass
import re

from simple_flow_documentation_curation.models import NormalizedHistoryPackage


REFERENCE_RE = re.compile(r"^(?P<kind>issue|pr|commit):(?P<id>[^#]+)(?P<anchor>#.+)?$")
PR_REVIEW_RE = re.compile(r"^pr:(?P<number>\d+)#review:(?P<review_id>[^#]+)$")
PR_COMMENT_RE = re.compile(r"^pr:(?P<number>\d+)#comment:(?P<comment_id>[^#]+)$")
FILE_RE = re.compile(
    r"^file:(?P<sha>[^:]+):(?P<path>.+):(?P<start>\d+)(?:-(?P<end>\d+))?$"
)


@dataclass(frozen=True)
class ResolvedReference:
    reference: str
    url: str
    kind: str


class ReferenceResolver:
    def __init__(self, package: NormalizedHistoryPackage):
        self.package = package

    def resolve(self, reference: str) -> ResolvedReference:
        if file_match := FILE_RE.fullmatch(reference):
            return self._resolve_file(file_match, reference)
        if review_match := PR_REVIEW_RE.fullmatch(reference):
            return self._resolve_review(review_match, reference)
        if comment_match := PR_COMMENT_RE.fullmatch(reference):
            return self._resolve_comment(comment_match, reference)

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

    def _resolve_review(self, match: re.Match[str], reference: str) -> ResolvedReference:
        number = int(match.group("number"))
        review_id = match.group("review_id")
        item = self._pr(number, reference)
        for review in item.reviews:
            if review.review_id == review_id:
                url = review.url or _repo_url(
                    self.package.repository,
                    f"pull/{number}#pullrequestreview-{review_id}",
                )
                return ResolvedReference(reference, url, "review")
        raise ValueError(f"Unknown review reference: {reference}")

    def _resolve_comment(self, match: re.Match[str], reference: str) -> ResolvedReference:
        number = int(match.group("number"))
        comment_id = match.group("comment_id")
        item = self._pr(number, reference)
        for comment in item.comments:
            if comment.comment_id == comment_id:
                url = comment.url or _repo_url(
                    self.package.repository,
                    f"pull/{number}#discussion_r{comment_id}",
                )
                return ResolvedReference(reference, url, "comment")
        raise ValueError(f"Unknown comment reference: {reference}")

    def _resolve_file(self, match: re.Match[str], reference: str) -> ResolvedReference:
        sha = match.group("sha")
        if sha not in self.package.commit_shas:
            raise ValueError(f"Unknown reference: {reference}")
        path = match.group("path").replace("\\", "/").lstrip("/")
        start = match.group("start")
        end = match.group("end")
        suffix = f"blob/{sha}/{path}#L{start}"
        if end:
            suffix += f"-L{end}"
        return ResolvedReference(reference, _repo_url(self.package.repository, suffix), "file")

    def _pr(self, number: int, reference: str):
        item_id = f"pr:{number}"
        if item_id not in self.package.item_ids:
            raise ValueError(f"Unknown reference: {reference}")
        return self.package.work_item(item_id)


def _repo_url(repository: str, suffix: str) -> str:
    clean = repository.removeprefix("https://github.com/").removesuffix(".git").strip("/")
    if not clean:
        return suffix
    return f"https://github.com/{clean}/{suffix}"
