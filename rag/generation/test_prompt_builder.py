from __future__ import annotations

import sys
from pathlib import Path


if __package__ in (None, ""):
    PROJECT_ROOT = Path(__file__).resolve().parents[2]

    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))


from rag.generation.models import SourceContext
from rag.generation.prompt_builder import build_prompt


def main() -> int:
    sources = [
        SourceContext(
            source_number=1,
            chunk_id="sample_chunk_001",
            announcement_id="sample_announcement",
            document_id="sample_document",
            document_format="hwpx",
            section_path=["공급금액", "계약금"],
            title="계약금",
            content="계약금은 1,000만원 정액제입니다.",
            reranker_score=0.98,
            reranker_rank=1,
        )
    ]

    prompt = build_prompt(
        query="계약금은 얼마야?",
        announcement_directory="announcement_001",
        document_format="hwpx",
        sources=sources,
    )

    print("=" * 70)
    print("SYSTEM PROMPT")
    print("=" * 70)
    print(prompt.system_prompt)

    print()
    print("=" * 70)
    print("USER PROMPT")
    print("=" * 70)
    print(prompt.user_prompt)

    return 0


if __name__ == "__main__":
    sys.exit(main())
