import numpy as np

from rag.context_rag import (
    build_contextual_query,
    get_ranked_indices,
    reciprocal_rank_fusion,
)


def test_build_contextual_query_without_history():
    question = "신청 기간은 언제인가요?"

    result = build_contextual_query(
        current_question=question,
        previous_questions=[],
        max_history_turns=3,
    )

    assert result == question


def test_build_contextual_query_uses_recent_history():
    result = build_contextual_query(
        current_question="그럼 미성년자는요?",
        previous_questions=[
            "오래된 질문",
            "누가 신청할 수 있나요?",
        ],
        max_history_turns=1,
    )

    assert "오래된 질문" not in result
    assert "누가 신청할 수 있나요?" in result
    assert "그럼 미성년자는요?" in result


def test_get_ranked_indices_orders_scores_descending():
    scores = np.array([0.2, 0.9, 0.5], dtype=np.float32)

    result = get_ranked_indices(
        scores=scores,
        candidate_k=2,
    )

    assert result == [1, 2]


def test_reciprocal_rank_fusion_prioritizes_shared_result():
    result = reciprocal_rank_fusion(
        current_ranking=[0, 1],
        contextual_ranking=[1, 2],
    )

    assert result[1] > result[0]
    assert result[1] > result[2]
