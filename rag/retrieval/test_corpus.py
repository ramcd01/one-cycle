from __future__ import annotations

import argparse
import sys

from .corpus_loader import CorpusLoadError, load_corpus
from .tokenizer import tokenize


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Retrieval 코퍼스 로드 테스트"
    )
    parser.add_argument("--announcement", required=True)
    parser.add_argument(
        "--format",
        choices=("hwp", "hwpx"),
        default=None,
    )
    args = parser.parse_args()

    try:
        corpus = load_corpus(
            args.announcement,
            document_format=args.format,
        )
        item = corpus.items[0]

        print("=" * 70)
        print("Retrieval 코퍼스 로드 완료")
        print("=" * 70)
        print(f"공고 폴더: {corpus.announcement_directory}")
        print(f"문서 형식: {corpus.document_format}")
        print(f"모델: {corpus.model_name}")
        print(f"청크 수: {corpus.size}")
        print(f"임베딩 shape: {corpus.embeddings.shape}")
        print(f"정규화: {corpus.normalized}")
        print(f"첫 chunk_id: {item.chunk_id}")
        print(f"section_path: {item.section_path}")
        print(f"BM25 tokens: {tokenize(item.search_text)[:30]}")
        return 0

    except CorpusLoadError as exc:
        print()
        print("[코퍼스 로드 실패]")
        print(exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
