from __future__ import annotations

from simple_flow_documentation_curation.models import (
    BASELINE_ACTIONS,
    CurationAnalysis,
    PatchOperation,
    ProposalClassification,
)


def plan_patch_operations(analysis: CurationAnalysis) -> list[PatchOperation]:
    operations: list[PatchOperation] = []
    for decision in analysis.decisions:
        classification = ProposalClassification(decision.proposed_classification)
        action = decision.proposed_baseline_action
        if action not in BASELINE_ACTIONS:
            raise ValueError(f"Unsupported baseline action: {action}")
        if classification in {
            ProposalClassification.FINAL,
            ProposalClassification.SUPERSEDED,
        }:
            operations.append(
                PatchOperation(
                    operation=action,
                    target_component=decision.component,
                    target_section=decision.affected_baseline_section,
                    reason=decision.short_reason,
                    payload=decision.to_json_data(),
                )
            )
            if action == "SUPERSEDE_DECISION" and decision.supersedes.strip():
                for superseded_id in _ids(decision.supersedes):
                    operations.append(
                        PatchOperation(
                            operation="UPDATE_DECISION",
                            target_component=decision.component,
                            target_section=decision.affected_baseline_section,
                            reason=f"{superseded_id} is superseded by {decision.decision_id}.",
                            payload={
                                "decision_id": superseded_id,
                                "status": "SUPERSEDED",
                                "superseded_by": decision.decision_id,
                            },
                        )
                    )
        else:
            operations.append(
                PatchOperation(
                    operation="NO_CHANGE",
                    target_component=decision.component,
                    target_section=decision.affected_baseline_section,
                    reason=f"{classification.value} proposals do not enter the baseline.",
                    payload=decision.to_json_data(),
                )
            )

    for finding in analysis.findings:
        operations.append(
            PatchOperation(
                operation="NO_CHANGE",
                target_component=finding.component,
                target_section=finding.affected_baseline_section,
                reason=f"{finding.finding_type} documentation finding requires human review.",
                payload=finding.to_json_data(),
            )
        )

    for proposal in analysis.new_components:
        operations.append(
            PatchOperation(
                operation="CREATE_COMPONENT_BASELINE",
                target_component=proposal.component_id,
                target_section="Component Index",
                reason=proposal.reason_for_separation,
                payload=proposal.to_json_data(),
            )
        )
    return operations


def _ids(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]
