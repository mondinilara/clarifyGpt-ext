import argparse
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "src" / "data"


DEFAULT_SOURCE = DATA_DIR / "mbpp_sanitized_microsoft.jsonl"
DEFAULT_FINAL = DATA_DIR / "generated" / "mbpp_final_three_shot_gpt4_0.jsonl"
DEFAULT_SAMPLES = DATA_DIR / "mbpp_sanitized_microsoft_sample_0.8_25_results_final_gpt4.jsonl"
DEFAULT_OUTPUT_DIR = DATA_DIR / "generated" / "eval_subset"


def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            json.dump(row, handle, ensure_ascii=False)
            handle.write("\n")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create aligned MBPP source/prediction files for evaluating only a subset of generated tasks."
    )
    parser.add_argument(
        "--task-count",
        type=int,
        required=True,
        help="Number of tasks to include in the evaluation subset. Example: 32 or 427.",
    )
    parser.add_argument(
        "--samples-per-task",
        type=int,
        default=None,
        help="If provided, only tasks with at least this many generated samples are eligible.",
    )
    parser.add_argument("--source-path", default=str(DEFAULT_SOURCE), help="Full MBPP source jsonl.")
    parser.add_argument("--final-path", default=str(DEFAULT_FINAL), help="Full final prediction jsonl.")
    parser.add_argument(
        "--sample-code-file",
        default=str(DEFAULT_SAMPLES),
        help="Generated code samples jsonl used to decide which tasks were actually generated.",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for subset files.")
    parser.add_argument(
        "--prefix",
        default=None,
        help="Output filename prefix. Default: mbpp_eval_first_<task-count>.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.task_count < 1:
        raise ValueError("--task-count must be greater than zero.")

    source_path = Path(args.source_path)
    final_path = Path(args.final_path)
    sample_code_file = Path(args.sample_code_file)
    output_dir = Path(args.output_dir)
    prefix = args.prefix or f"mbpp_eval_first_{args.task_count}"

    source_rows = load_jsonl(source_path)
    final_rows = load_jsonl(final_path)
    sample_rows = load_jsonl(sample_code_file)

    sample_counts = Counter(row["task_id"] for row in sample_rows if "task_id" in row)
    min_samples = args.samples_per_task or 1
    eligible_task_ids = {
        task_id for task_id, count in sample_counts.items() if count >= min_samples
    }

    selected_source = []
    for row in source_rows:
        if row.get("task_id") in eligible_task_ids:
            selected_source.append(row)
        if len(selected_source) == args.task_count:
            break

    if len(selected_source) < args.task_count:
        raise RuntimeError(
            f"Only found {len(selected_source)} eligible tasks, but --task-count requested {args.task_count}. "
            f"Check --samples-per-task or generate more samples first."
        )

    selected_prompts = {row["prompt"] for row in selected_source}
    selected_final = [row for row in final_rows if row.get("prompt") in selected_prompts]

    missing_prompts = selected_prompts - {row.get("prompt") for row in selected_final}
    if missing_prompts:
        raise RuntimeError(
            f"The final prediction file is missing {len(missing_prompts)} selected prompts. "
            "Rerun the final stage before creating the subset."
        )

    if len(selected_final) != len(selected_source):
        raise RuntimeError(
            f"Expected {len(selected_source)} predictions, found {len(selected_final)}. "
            "The final prediction file may contain duplicate prompts."
        )

    source_out = output_dir / f"{prefix}_source.jsonl"
    final_out = output_dir / f"{prefix}_final.jsonl"

    write_jsonl(source_out, selected_source)
    write_jsonl(final_out, selected_final)

    print(f"[ClarifyGPT] Wrote {len(selected_source)} source tasks: {source_out}")
    print(f"[ClarifyGPT] Wrote {len(selected_final)} predictions: {final_out}")
    print("[ClarifyGPT] Evaluate with:")
    print("python evaluation\\MBPP\\main.py `")
    print(f"  --source_path_for_solution {source_out} `")
    print(f"  --predict_path_for_solution {final_out}")


if __name__ == "__main__":
    main()
