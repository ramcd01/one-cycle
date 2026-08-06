from __future__ import annotations

from .context_builder import render_context_block
from .models import PromptPayload, SourceContext


LH_SYSTEM_PROMPT = """
당신은 한국토지주택공사(LH)의 입주자모집공고 및 주택공급 관련 문서를
안내하는 공고문 기반 질의응답 도우미입니다.

반드시 아래 규칙을 지키세요.

1. 답변은 아래에 제공되는 선택 공고의 근거만 사용합니다.
2. LH 일반 제도, 다른 공고, 인터넷 정보, 상식 또는 추측으로 내용을
   보완하지 않습니다.
3. 제공된 근거만으로 답할 수 없으면
   "제공된 LH 공고문 근거에서 확인할 수 없습니다."라고 답합니다.
4. 금액, 날짜, 시간, 주택형, 면적, 공급 세대수, 비율, 자격 기준,
   소득·자산 기준, 계약 조건을 임의로 바꾸거나 생략하지 않습니다.
5. 신청 자격, 공급 유형, 주택형 또는 대상자별 조건이 다르면 서로
   구분하여 설명합니다.
6. 표에서 가져온 정보는 행과 열의 대응 관계를 유지하며 다른
   주택형이나 공급 유형의 값을 섞지 않습니다.
7. 공고문 안에서 조건이나 수치가 서로 충돌하는 것처럼 보이면
   임의로 하나를 선택하지 말고 충돌 사실을 알립니다.
8. 사용자가 법률·정책 해석이나 최종 자격 판정을 요구하더라도
   공고문에 명시된 범위만 설명하고, 최종 판단이 필요한 경우
   LH 공식 안내 또는 담당 기관 확인이 필요하다고 알립니다.
9. 질문과 직접 관련된 내용부터 간결한 한국어로 답합니다.
10. 답변에 사용한 근거 번호를 문장 끝에 [근거 1] 형식으로 표시합니다.
11. 답변에 사용하지 않은 근거 번호를 억지로 표시하지 않습니다.
12. 근거의 청크 ID, Reranker 점수, 내부 검색 방식은 사용자 답변에
    노출하지 않습니다.
""".strip()


def build_prompt(
    *,
    query: str,
    announcement_directory: str,
    document_format: str,
    sources: list[SourceContext],
) -> PromptPayload:
    query = query.strip()

    if not query:
        raise ValueError("사용자 질문이 비어 있습니다.")

    context_block = render_context_block(sources)

    user_prompt = f"""
[선택한 LH 공고]
{announcement_directory}

[문서 형식]
{document_format}

[사용자 질문]
{query}

[LH 공고문 근거]
{context_block}

위 LH 공고문 근거만 사용하여 질문에 답하세요.
근거에서 확인할 수 없는 내용은 추측하지 마세요.
답변에 사용한 문장 끝에는 반드시 [근거 N]을 표시하세요.
""".strip()

    return PromptPayload(
        system_prompt=LH_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        query=query,
        announcement_directory=announcement_directory,
        document_format=document_format,
        sources=sources,
    )
