from __future__ import annotations

from simple_flow_agent.drafts import Draft, DraftStore
from simple_flow_documentation_curation.models import CurationAnalysis


def create_documentation_draft(
    store: DraftStore,
    analysis: CurationAnalysis,
    *,
    affected_project_documents: list[str],
) -> Draft:
    if not affected_project_documents:
        raise ValueError("Documentation-Curation drafts must name affected project documents.")
    return store.create_documentation(
        change="Apply Documentation-Curation proposals through the existing DOCUMENTATION workflow.",
        reason=_render_reason(analysis),
        impact=_render_impact(analysis),
        supersedes=_render_supersedes(analysis),
        affected_project_documents=affected_project_documents,
        source_context=_render_source_context(analysis),
    )


def _render_reason(analysis: CurationAnalysis) -> str:
    lines = ["Documentation-Curation produced structured review units."]
    for decision in analysis.decisions:
        lines.append(
            f"- Decision {decision.decision_id} ({decision.component}, {decision.proposed_classification}): {decision.decision}"
        )
        lines.append(f"  Short Reason: {decision.short_reason}")
        lines.append(f"  References: {', '.join(decision.exact_references)}")
    for finding in analysis.findings:
        lines.append(
            f"- Finding {finding.finding_id} ({finding.component}, {finding.finding_type}): {finding.conflict}"
        )
        lines.append(f"  Question: {finding.question}")
        lines.append(f"  References: {', '.join(finding.exact_references)}")
    for proposal in analysis.new_components:
        lines.append(
            f"- New Component Proposal {proposal.component_id}: {proposal.reason_for_separation}"
        )
        lines.append(f"  Evidence: {', '.join(proposal.evidence)}")
    return "\n".join(lines)


def _render_impact(analysis: CurationAnalysis) -> str:
    operation_lines = [
        f"- {operation.operation}: {operation.target_component} / {operation.target_section}"
        for operation in analysis.proposed_baseline_operations
    ]
    if not operation_lines:
        operation_lines = ["- NO_CHANGE: no baseline operation proposed."]
    return (
        "This draft proposes documentation-only baseline updates. It does not "
        "authorize code, configuration, script, Issue, branch, PR, or merge actions.\n"
        + "\n".join(operation_lines)
    )


def _render_supersedes(analysis: CurationAnalysis) -> str:
    superseded = [
        decision.supersedes
        for decision in analysis.decisions
        if decision.supersedes.strip()
    ]
    return ", ".join(superseded) if superseded else "None"


def _render_source_context(analysis: CurationAnalysis) -> str:
    lines = ["Source: Documentation-Curation structured analysis."]
    if analysis.pending_cursor is not None:
        lines.append(
            "Pending Curation Cursor: "
            f"{analysis.pending_cursor.updated_at} / {analysis.pending_cursor.stable_id}"
        )
    lines.append("Stop Point: DOCUMENTATION Canonical Draft created.")
    return "\n".join(lines)
