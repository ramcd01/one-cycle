from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .chunker import StructureAwareChunker
from .config import ChunkingConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Chunk normalized HWP/HWPX JSON into retrieval-ready JSON."
    )
    parser.add_argument("--input", required=True, help="Input JSON file or directory")
    parser.add_argument("--output", required=True, help="Output JSON file or directory")
    parser.add_argument("--announcement-id", default=None)
    parser.add_argument("--target-tokens", type=int, default=500)
    parser.add_argument("--max-tokens", type=int, default=800)
    parser.add_argument("--min-tokens", type=int, default=80)
    parser.add_argument("--overlap-tokens", type=int, default=80)
    parser.add_argument("--tokenizer", default=None, help="Local HF tokenizer path/name")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = ChunkingConfig(
        target_tokens=args.target_tokens,
        max_tokens=args.max_tokens,
        min_tokens=args.min_tokens,
        overlap_tokens=args.overlap_tokens,
        tokenizer_name_or_path=args.tokenizer,
    )
    chunker = StructureAwareChunker(config)

    input_path = Path(args.input)
    output_path = Path(args.output)

    if input_path.is_file():
        result = chunker.chunk_file(
            input_path,
            announcement_id=args.announcement_id,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as file:
            json.dump(result, file, ensure_ascii=False, indent=2)
        print_summary(input_path, output_path, result)
        return 0

    if input_path.is_dir():
        output_path.mkdir(parents=True, exist_ok=True)
        files = sorted(input_path.glob("*.json"))
        if not files:
            print(f"No JSON files found in {input_path}", file=sys.stderr)
            return 2
        failed = 0
        for file_path in files:
            try:
                result = chunker.chunk_file(file_path)
                target = output_path / f"{file_path.stem}_chunks.json"
                with target.open("w", encoding="utf-8") as file:
                    json.dump(result, file, ensure_ascii=False, indent=2)
                print_summary(file_path, target, result)
            except Exception as exc:  # continue batch while reporting failures
                failed += 1
                print(f"FAILED {file_path}: {exc}", file=sys.stderr)
        return 1 if failed else 0

    print(f"Input does not exist: {input_path}", file=sys.stderr)
    return 2


def print_summary(input_path: Path, output_path: Path, result: dict) -> None:
    report = result["report"]
    print(
        f"OK {input_path.name} -> {output_path} | "
        f"chunks={report['total_chunks']} "
        f"types={report['chunk_types']} "
        f"max_tokens={report['token_stats']['max']}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
