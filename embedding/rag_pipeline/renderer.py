from __future__ import annotations

from collections import OrderedDict

from .schemas import AnswerPlan, Citation, EvidenceItem


def _citation_marker(ids: list[str], number_by_id: dict[str, int]) -> str:
    numbers = sorted({number_by_id[item] for item in ids if item in number_by_id})
    return " ".join(f"[근거 {number}]" for number in numbers)


def _sentence(claim, number_by_id: dict[str, int]) -> str:
    marker = _citation_marker(claim.evidence_ids, number_by_id)
    text = claim.text.rstrip(" .")
    return f"{text}. {marker}".strip()


def render_answer(
    plan: AnswerPlan,
    evidence: list[EvidenceItem],
) -> tuple[str, list[Citation]]:
    evidence_map = {item.evidence_id: item for item in evidence}
    used_order: list[str] = []
    for claim in plan.claims:
        for evidence_id in claim.evidence_ids:
            if evidence_id in evidence_map and evidence_id not in used_order:
                used_order.append(evidence_id)

    number_by_id = {
        evidence_id: number
        for number, evidence_id in enumerate(used_order, start=1)
    }

    lines: list[str] = []

    if plan.answer_mode == "boolean_with_conditions":
        conclusion = next(
            claim for claim in plan.claims if claim.kind == "conclusion"
        )
        lines.append(_sentence(conclusion, number_by_id))

        conditions = [claim for claim in plan.claims if claim.kind == "condition"]
        exceptions = [claim for claim in plan.claims if claim.kind == "exception"]
        explanations = [claim for claim in plan.claims if claim.kind == "explanation"]

        if conditions:
            lines.append("")
            lines.append("**적용 조건**")
            lines.extend(
                f"- {_sentence(claim, number_by_id)}" for claim in conditions
            )
        if exceptions:
            lines.append("")
            lines.append("**예외**")
            lines.extend(
                f"- {_sentence(claim, number_by_id)}" for claim in exceptions
            )
        if explanations:
            lines.append("")
            lines.extend(_sentence(claim, number_by_id) for claim in explanations)
    else:
        grouped: OrderedDict[str, list[str]] = OrderedDict()
        ungrouped: list[str] = []

        list_modes = {
            "complete_list",
            "complete_grouped_list",
            "all_matching_items",
            "overview",
            "procedure_steps",
        }

        for claim in plan.claims:
            sentence = _sentence(claim, number_by_id)
            if claim.group:
                grouped.setdefault(claim.group, []).append(sentence)
            elif claim.kind in {"item", "step"} and plan.answer_mode in list_modes:
                ungrouped.append(f"- {sentence}")
            else:
                ungrouped.append(sentence)

        lines.extend(ungrouped)
        for group, items in grouped.items():
            if lines:
                lines.append("")
            lines.append(f"**{group}**")
            lines.extend(f"- {item}" for item in items)

    citations = [
        Citation(
            citation_id=number_by_id[evidence_id],
            evidence_id=evidence_id,
            document_name=evidence_map[evidence_id].document_name,
            location=evidence_map[evidence_id].location,
            excerpt=evidence_map[evidence_id].excerpt,
            structured_fields=evidence_map[evidence_id].structured_fields,
        )
        for evidence_id in used_order
    ]

    return "\n".join(lines).strip(), citations
