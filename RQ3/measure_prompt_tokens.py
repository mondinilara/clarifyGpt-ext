import importlib
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


PROMPT_SETS = [
    ("askcq", "askcq_prompt"),
    ("answercq", "answercq_prompt"),
    ("synthesize", "synthesize_prompt"),
]


def load_counter():
    try:
        import tiktoken

        encoding = tiktoken.get_encoding("cl100k_base")
        return "tiktoken:cl100k_base", lambda text: len(encoding.encode(text))
    except Exception:
        pattern = re.compile(r"\w+|[^\w\s]", re.UNICODE)
        return "regex_estimate", lambda text: len(pattern.findall(text))


def message_text(messages):
    return "\n".join(f"{msg['role']}:\n{msg['content']}" for msg in messages)


def main():
    original = importlib.import_module("src.prompt.prompt_mbpp")
    optimized = importlib.import_module("RQ3.prompt_mbpp_optimized")
    method, count_tokens = load_counter()

    rows = []
    total_original = 0
    total_optimized = 0

    for stage, attr in PROMPT_SETS:
        original_text = message_text(getattr(original, attr)["three_shot"])
        optimized_text = message_text(getattr(optimized, attr)["three_shot"])
        original_tokens = count_tokens(original_text)
        optimized_tokens = count_tokens(optimized_text)
        total_original += original_tokens
        total_optimized += optimized_tokens
        rows.append({
            "stage": stage,
            "original_tokens": original_tokens,
            "optimized_tokens": optimized_tokens,
            "reduced_tokens": original_tokens - optimized_tokens,
            "reduction_percent": round((1 - optimized_tokens / original_tokens) * 100, 2),
        })

    summary = {
        "tokenizer": method,
        "inference_type": "three_shot",
        "stages": rows,
        "total_original_tokens": total_original,
        "total_optimized_tokens": total_optimized,
        "total_reduced_tokens": total_original - total_optimized,
        "total_reduction_percent": round((1 - total_optimized / total_original) * 100, 2),
        "note": (
            "Counts cover static few-shot prompt messages only. Runtime task text, candidate code, "
            "clarifying questions and answers vary per example and are not included here."
        ),
    }

    output_path = ROOT / "RQ3" / "token_reduction_report.json"
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
