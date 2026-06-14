import argparse
import csv
import importlib
import importlib.util
import json
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLARIFY_DIR = PROJECT_ROOT / "src" / "clarify"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(CLARIFY_DIR) not in sys.path:
    sys.path.insert(0, str(CLARIFY_DIR))

from utils import parse_clarification_mbpp, parse_cq_mbpp, refine_prompt_clarify


GPT_4O_MINI_INPUT_PER_1M = 0.15
GPT_4O_MINI_OUTPUT_PER_1M = 0.60


def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def load_counter():
    try:
        import tiktoken

        encoding = tiktoken.get_encoding("cl100k_base")
        return "tiktoken:cl100k_base", lambda text: len(encoding.encode(text))
    except Exception:
        pattern = re.compile(r"\w+|[^\w\s]", re.UNICODE)
        return "regex_estimate", lambda text: len(pattern.findall(text))


def load_prompt_module(module_name):
    if not module_name:
        return importlib.import_module("src.prompt.prompt_mbpp")

    if module_name.endswith(".py") or Path(module_name).exists():
        module_path = Path(module_name).resolve()
        spec = importlib.util.spec_from_file_location("token_prompt_module", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    return importlib.import_module(module_name)


def prompt_parts(messages):
    instruction = messages[0]["content"]
    examples = []
    for idx in range(1, len(messages), 2):
        examples.append({
            "user": messages[idx]["content"],
            "assistant": messages[idx + 1]["content"],
        })
    return instruction, examples


def chat_text(instruction, examples, prompt):
    parts = [f"system:\n{instruction}"]
    for example in examples:
        parts.append(f"user:\n{example['user']}")
        parts.append(f"assistant:\n{example['assistant']}")
    parts.append(f"user:\n{prompt}")
    return "\n".join(parts)


def usage_tokens(rows):
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    rows_with_usage = 0

    for row in rows:
        usage = row.get("usage")
        if not usage:
            continue
        rows_with_usage += 1
        prompt_tokens += usage.get("prompt_tokens", 0) or 0
        completion_tokens += usage.get("completion_tokens", 0) or 0
        total_tokens += usage.get("total_tokens", 0) or 0

    return {
        "usage_rows": rows_with_usage,
        "actual_input_tokens": prompt_tokens,
        "actual_output_tokens": completion_tokens,
        "actual_total_tokens": total_tokens or prompt_tokens + completion_tokens,
    }


def index_unique_by_task_id(rows, label):
    indexed = {}
    for row in rows:
        task_id = row.get("task_id")
        if task_id in indexed:
            raise RuntimeError(f"Duplicate task_id {task_id} in {label}.")
        indexed[task_id] = row
    return indexed


def align_rows_by_task_id(needcq_rows, askcq_rows, answercq_rows, synthesize_rows):
    need_by_id = index_unique_by_task_id(needcq_rows, "needcq")
    ask_by_id = index_unique_by_task_id(askcq_rows, "askcq")
    answer_by_id = index_unique_by_task_id(answercq_rows, "answercq")
    synth_by_id = index_unique_by_task_id(synthesize_rows, "synthesize")

    common_ids = [
        row["task_id"]
        for row in needcq_rows
        if row["task_id"] in ask_by_id and row["task_id"] in answer_by_id and row["task_id"] in synth_by_id
    ]

    if not common_ids:
        raise RuntimeError(
            "No common task_id values across needcq, askcq, answercq and synthesize files."
        )

    return (
        [need_by_id[task_id] for task_id in common_ids],
        [ask_by_id[task_id] for task_id in common_ids],
        [answer_by_id[task_id] for task_id in common_ids],
        [synth_by_id[task_id] for task_id in common_ids],
        common_ids,
        {
            "needcq_rows": len(needcq_rows),
            "askcq_rows": len(askcq_rows),
            "answercq_rows": len(answercq_rows),
            "synthesize_rows": len(synthesize_rows),
            "matched_rows": len(common_ids),
        },
    )


def cost(input_tokens, output_tokens, input_price, output_price):
    return (input_tokens / 1_000_000 * input_price) + (output_tokens / 1_000_000 * output_price)


def estimate_askcq(needcq_rows, askcq_rows, prompts, count_tokens, inference_type):
    instruction, examples = prompt_parts(prompts.askcq_prompt[inference_type])
    input_tokens = 0
    output_tokens = 0

    for need_row, out_row in zip(needcq_rows, askcq_rows):
        code_string = ""
        for idx, candidate_c in enumerate(need_row["candidate_codes"]):
            code_string += f"Solution {idx}:\n{candidate_c}\n"

        if inference_type == "zero_shot":
            prompt = (
                f"User Requirement:\n{need_row['prompt'].strip()}\n{code_string.strip()}"
                "\nAnalysis:\n{insert your analysis results here}"
                "\nClarifying Questions:\n{insert your clarifying questions here}"
            )
        else:
            prompt = f"User Requirement:\n{need_row['prompt'].strip()}\n{code_string.strip()}"

        input_tokens += count_tokens(chat_text(instruction, examples, prompt))
        output_tokens += count_tokens(out_row.get("askcq", ""))

    return input_tokens, output_tokens


def estimate_answercq(needcq_rows, askcq_rows, answercq_rows, prompts, count_tokens, inference_type):
    instruction, examples = prompt_parts(prompts.answercq_prompt[inference_type])
    input_tokens = 0
    output_tokens = 0

    for need_row, ask_row, out_row in zip(needcq_rows, askcq_rows, answercq_rows):
        cq = parse_cq_mbpp(ask_row["askcq"])
        prompt = (
            f"User Requirement:\n{need_row['prompt'].strip()}"
            f"\n\n### Clarifying Questions:\n{cq.strip()}"
            "\n\n### Answers:\n{insert answers here}"
        )
        input_tokens += count_tokens(chat_text(instruction, examples, prompt))
        output_tokens += count_tokens(out_row.get("answercq", ""))

    return input_tokens, output_tokens


def estimate_synthesize(needcq_rows, askcq_rows, answercq_rows, synthesize_rows, prompts, count_tokens, inference_type):
    instruction, examples = prompt_parts(prompts.synthesize_prompt[inference_type])
    input_tokens = 0
    output_tokens = 0

    for need_row, ask_row, answer_row, out_row in zip(needcq_rows, askcq_rows, answercq_rows, synthesize_rows):
        clarification = parse_clarification_mbpp(ask_row["askcq"], answer_row["answercq"])
        refined_prompt = refine_prompt_clarify(need_row["prompt"], clarification)
        prompt = f"User Requirement:\n{refined_prompt}"
        input_tokens += count_tokens(chat_text(instruction, examples, prompt))
        output_tokens += count_tokens(out_row.get("raw_code_completion", ""))

    return input_tokens, output_tokens


def parse_args():
    parser = argparse.ArgumentParser(description="Estimate token usage and cost for ClarifyGPT MBPP experiments.")
    parser.add_argument("--experiment-name", required=True)
    parser.add_argument("--needcq-path", required=True)
    parser.add_argument("--askcq-path", required=True)
    parser.add_argument("--answercq-path", required=True)
    parser.add_argument("--synthesize-path", required=True)
    parser.add_argument("--prompt-module", help="Prompt module used by this experiment. Omit for original prompts.")
    parser.add_argument("--inference-type", default="three_shot")
    parser.add_argument("--input-price-per-1m", type=float, default=GPT_4O_MINI_INPUT_PER_1M)
    parser.add_argument("--output-price-per-1m", type=float, default=GPT_4O_MINI_OUTPUT_PER_1M)
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--output-csv", default=None)
    return parser.parse_args()


def main():
    args = parse_args()
    tokenizer, count_tokens = load_counter()
    prompts = load_prompt_module(args.prompt_module)

    needcq_rows = load_jsonl(Path(args.needcq_path))
    askcq_rows = load_jsonl(Path(args.askcq_path))
    answercq_rows = load_jsonl(Path(args.answercq_path))
    synthesize_rows = load_jsonl(Path(args.synthesize_path))

    needcq_rows, askcq_rows, answercq_rows, synthesize_rows, matched_task_ids, row_counts = align_rows_by_task_id(
        needcq_rows,
        askcq_rows,
        answercq_rows,
        synthesize_rows,
    )

    stages = []
    for stage_name, estimator, rows in [
        ("askcq", estimate_askcq, askcq_rows),
        ("answercq", estimate_answercq, answercq_rows),
        ("synthesize", estimate_synthesize, synthesize_rows),
    ]:
        if stage_name == "askcq":
            estimated_input, estimated_output = estimator(
                needcq_rows, askcq_rows, prompts, count_tokens, args.inference_type
            )
        elif stage_name == "answercq":
            estimated_input, estimated_output = estimator(
                needcq_rows, askcq_rows, answercq_rows, prompts, count_tokens, args.inference_type
            )
        else:
            estimated_input, estimated_output = estimator(
                needcq_rows, askcq_rows, answercq_rows, synthesize_rows, prompts, count_tokens, args.inference_type
            )

        actual = usage_tokens(rows)
        stages.append({
            "stage": stage_name,
            "calls": len(rows),
            "estimated_input_tokens": estimated_input,
            "estimated_output_tokens": estimated_output,
            "estimated_total_tokens": estimated_input + estimated_output,
            "estimated_cost_usd": round(
                cost(estimated_input, estimated_output, args.input_price_per_1m, args.output_price_per_1m),
                6,
            ),
            **actual,
        })

    total_estimated_input = sum(row["estimated_input_tokens"] for row in stages)
    total_estimated_output = sum(row["estimated_output_tokens"] for row in stages)
    total_actual_input = sum(row["actual_input_tokens"] for row in stages)
    total_actual_output = sum(row["actual_output_tokens"] for row in stages)

    summary = {
        "experiment_name": args.experiment_name,
        "tokenizer": tokenizer,
        "inference_type": args.inference_type,
        "prompt_module": args.prompt_module or "src.prompt.prompt_mbpp",
        "row_counts": row_counts,
        "matched_task_ids": matched_task_ids,
        "pricing": {
            "input_per_1m": args.input_price_per_1m,
            "output_per_1m": args.output_price_per_1m,
        },
        "stages": stages,
        "totals": {
            "calls": sum(row["calls"] for row in stages),
            "estimated_input_tokens": total_estimated_input,
            "estimated_output_tokens": total_estimated_output,
            "estimated_total_tokens": total_estimated_input + total_estimated_output,
            "estimated_cost_usd": round(
                cost(total_estimated_input, total_estimated_output, args.input_price_per_1m, args.output_price_per_1m),
                6,
            ),
            "actual_input_tokens_from_usage": total_actual_input,
            "actual_output_tokens_from_usage": total_actual_output,
            "actual_cost_usd_from_usage": round(
                cost(total_actual_input, total_actual_output, args.input_price_per_1m, args.output_price_per_1m),
                6,
            ) if total_actual_input or total_actual_output else None,
        },
        "note": (
            "Estimated tokens are reconstructed offline from saved JSONL files. "
            "Actual usage is available only for rows generated after usage logging was added."
        ),
    }

    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.output_json:
        output_json = Path(args.output_json)
        output_json.parent.mkdir(parents=True, exist_ok=True)
        with open(output_json, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, ensure_ascii=False, indent=2)
            handle.write("\n")

    if args.output_csv:
        output_csv = Path(args.output_csv)
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        with open(output_csv, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                "experiment_name",
                "stage",
                "calls",
                "estimated_input_tokens",
                "estimated_output_tokens",
                "estimated_total_tokens",
                "estimated_cost_usd",
                "actual_input_tokens",
                "actual_output_tokens",
                "actual_total_tokens",
            ])
            writer.writeheader()
            for row in stages:
                writer.writerow({
                    "experiment_name": args.experiment_name,
                    "stage": row["stage"],
                    "calls": row["calls"],
                    "estimated_input_tokens": row["estimated_input_tokens"],
                    "estimated_output_tokens": row["estimated_output_tokens"],
                    "estimated_total_tokens": row["estimated_total_tokens"],
                    "estimated_cost_usd": row["estimated_cost_usd"],
                    "actual_input_tokens": row["actual_input_tokens"],
                    "actual_output_tokens": row["actual_output_tokens"],
                    "actual_total_tokens": row["actual_total_tokens"],
                })


if __name__ == "__main__":
    main()
