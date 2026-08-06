from __future__ import annotations
import argparse, json, re, sys, time
from datetime import datetime
from pathlib import Path

if __package__ in (None, ""):
    ROOT = Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

from rag.generation.config import DEFAULT_GENERATION_CONFIG, GenerationConfig
from rag.pipeline import RAGPipeline
from rag.retrieval.config import DEFAULT_RETRIEVAL_CONFIG
from rag.retrieval.run_hybrid_search import discover_announcements, select_announcement, select_format

HERE = Path(__file__).resolve().parent
DEFAULT_QUESTIONS = HERE / "questions.json"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "outputs" / "benchmark"

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--announcement", default=None)
    p.add_argument("--format", choices=("hwp","hwpx"), default=None)
    p.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--model-name", default=DEFAULT_GENERATION_CONFIG.model_name)
    p.add_argument("--llm-base-url", default=DEFAULT_GENERATION_CONFIG.base_url)
    p.add_argument("--temperature", type=float, default=DEFAULT_GENERATION_CONFIG.temperature)
    p.add_argument("--top-p", type=float, default=DEFAULT_GENERATION_CONFIG.top_p)
    p.add_argument("--max-tokens", type=int, default=DEFAULT_GENERATION_CONFIG.max_tokens)
    p.add_argument("--non-interactive", action="store_true")
    return p.parse_args()

def load_questions(path):
    data = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    return data.get("document",""), data["questions"]

def resolve_doc(args):
    if args.non_interactive:
        if not args.announcement:
            raise ValueError("--non-interactive 사용 시 --announcement가 필요합니다.")
        return args.announcement, args.format
    items = discover_announcements(DEFAULT_RETRIEVAL_CONFIG.outputs_root)
    if args.announcement:
        hit = next((x for x in items if x["name"] == args.announcement), None)
        if hit is None:
            raise ValueError(f"검색 가능한 공고가 아닙니다: {args.announcement}")
        ann = args.announcement
        formats = [str(x) for x in hit["formats"]]
    else:
        ann, formats = select_announcement(items)
    fmt = args.format or select_format(formats)
    if fmt not in formats:
        raise ValueError(f"{ann}에서 사용할 수 없는 형식입니다: {fmt}")
    return ann, fmt

def safe_name(s):
    return re.sub(r"[^0-9A-Za-z가-힣._-]+","_",s).strip("_") or "model"

def render_txt(meta, results):
    lines = [
        "="*90, "LH 공고문 RAG 모델 벤치마크 결과", "="*90,
        f"문서명       : {meta['document']}",
        f"공고 폴더    : {meta['announcement']}",
        f"문서 형식    : {meta['format']}",
        f"생성 모델    : {meta['model']}",
        f"실행 시작    : {meta['started_at']}",
        f"질문 수      : {len(results)}",
        f"전체 소요시간: {meta['total_seconds']:.2f}초", ""
    ]
    for r in results:
        lines += [
            "="*90,
            f"Q{r['id']:02d} [{r['category']}]",
            "-"*90,
            f"질문: {r['question']}", "",
            f"상태: {r['status']}",
            f"응답시간: {r['elapsed_seconds']:.2f}초", "",
            "[답변]", r.get("answer",""), "", "[검색 근거]"
        ]
        if r.get("sources"):
            for s in r["sources"]:
                lines += [
                    f"- 근거 {s['source_number']}: {s['section_label']}",
                    f"  chunk_id: {s['chunk_id']}"
                ]
        else:
            lines.append("- 없음")
        if r.get("error"):
            lines += ["", "[오류]", r["error"]]
        lines.append("")
    return "\n".join(lines)

def main():
    args = parse_args()
    try:
        document, questions = load_questions(args.questions)
        ann, fmt = resolve_doc(args)
        gen_cfg = GenerationConfig(
            base_url=args.llm_base_url,
            chat_completions_path=DEFAULT_GENERATION_CONFIG.chat_completions_path,
            model_name=args.model_name,
            temperature=args.temperature,
            top_p=args.top_p,
            max_tokens=args.max_tokens,
            timeout_seconds=DEFAULT_GENERATION_CONFIG.timeout_seconds,
            context_top_k=DEFAULT_GENERATION_CONFIG.context_top_k,
            max_chars_per_context=DEFAULT_GENERATION_CONFIG.max_chars_per_context,
            require_source_markers=DEFAULT_GENERATION_CONFIG.require_source_markers,
        )
        print("="*80)
        print("모델 일괄 벤치마크")
        print(f"공고: {ann} / 형식: {fmt} / 모델: {args.model_name}")
        print(f"질문 수: {len(questions)}")
        pipeline = RAGPipeline.from_files(
            ann, document_format=fmt, generation_config=gen_cfg
        )
        started = datetime.now()
        total_start = time.perf_counter()
        results = []
        for idx, item in enumerate(questions, 1):
            print(f"\n[{idx}/{len(questions)}] Q{item['id']:02d} {item['question']}")
            t0 = time.perf_counter()
            try:
                generated = pipeline.ask(item["question"])
                elapsed = time.perf_counter() - t0
                sources = [{
                    "source_number": s.source_number,
                    "chunk_id": s.chunk_id,
                    "section_label": s.section_label,
                } for s in generated.sources]
                result = {**item, "status":"성공", "elapsed_seconds":elapsed,
                          "answer":generated.answer, "sources":sources, "error":None}
                print(f"완료 ({elapsed:.2f}초)")
            except Exception as exc:
                elapsed = time.perf_counter() - t0
                result = {**item, "status":"실패", "elapsed_seconds":elapsed,
                          "answer":"", "sources":[],
                          "error":f"{type(exc).__name__}: {exc}"}
                print(f"실패 ({elapsed:.2f}초): {result['error']}")
            results.append(result)

        total = time.perf_counter() - total_start
        outdir = args.output_dir.expanduser().resolve()
        outdir.mkdir(parents=True, exist_ok=True)
        stamp = started.strftime("%Y%m%d_%H%M%S")
        stem = f"{ann}_{fmt}_{safe_name(args.model_name)}_{stamp}"
        txt_path = outdir / f"{stem}.txt"
        json_path = outdir / f"{stem}.json"
        meta = {
            "document": document,
            "announcement": ann,
            "format": fmt,
            "model": args.model_name,
            "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
            "total_seconds": total,
        }
        txt_path.write_text(render_txt(meta, results), encoding="utf-8")
        json_path.write_text(json.dumps(
            {**meta, "results":results},
            ensure_ascii=False, indent=2
        ), encoding="utf-8")
        print("\n"+"="*80)
        print("벤치마크 완료")
        print(f"TXT : {txt_path}")
        print(f"JSON: {json_path}")
        return 0
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단되었습니다.")
        return 130
    except Exception as exc:
        print(f"\n[벤치마크 실행 실패]\n{type(exc).__name__}: {exc}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
