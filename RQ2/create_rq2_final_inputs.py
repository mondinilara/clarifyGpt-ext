import argparse
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RQ2_DATA = ROOT / "RQ2" / "data"


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
        description="Create RQ2 source and greedy baseline files needed by the ClarifyGPT final stage."
    )
    parser.add_argument("--task-count", type=int, required=True, help="Number of RQ2 tasks to include.")
    parser.add_argument("--samples-per-task", type=int, default=25, help="Required samples per selected task.")
    parser.add_argument(
        "--source-path",
        default=str(RQ2_DATA / "mbpp_rq2_transformed.jsonl"),
        help="RQ2 transformed MBPP source file.",
    )
    parser.add_argument(
        "--sample-code-file",
        default=str(RQ2_DATA / "mbpp_rq2_sample_25.jsonl"),
        help="RQ2 generated samples file.",
    )
    parser.add_argument("--output-dir", default=str(RQ2_DATA), help="Output directory.")
    parser.add_argument("--prefix", default=None, help="Output prefix. Default: mbpp_rq2_first_<task-count>.")
    return parser.parse_args()


def main():
    args = parse_args()
    source_rows = load_jsonl(Path(args.source_path))
    sample_rows = load_jsonl(Path(args.sample_code_file))
    output_dir = Path(args.output_dir)
    prefix = args.prefix or f"mbpp_rq2_first_{args.task_count}"

    samples_by_task = defaultdict(list)
    for row in sample_rows:
        samples_by_task[row["task_id"]].append(row)

    selected_source = []
    greedy_rows = []
    for source in source_rows:
        task_id = source["task_id"]
        task_samples = samples_by_task.get(task_id, [])
        if len(task_samples) < args.samples_per_task:
            continue

        selected_source.append(source)
        first_sample = task_samples[0]["raw_code_completion"]
        greedy_rows.append({
            "task_id": task_id,
            "prompt": source["prompt"],
            "raw_code_completion": first_sample,
            "samples": [first_sample],
        })

        if len(selected_source) == args.task_count:
            break

    if len(selected_source) < args.task_count:
        raise RuntimeError(
            f"Only found {len(selected_source)} tasks with at least {args.samples_per_task} samples. "
            f"Requested {args.task_count}."
        )

    source_out = output_dir / f"{prefix}_source.jsonl"
    greedy_out = output_dir / f"{prefix}_greedy.jsonl"
    write_jsonl(source_out, selected_source)
    write_jsonl(greedy_out, greedy_rows)

    print(f"[RQ2] Wrote source subset: {source_out}")
    print(f"[RQ2] Wrote greedy baseline: {greedy_out}")
    print("[RQ2] Use these paths in --mbpp-file and --greedy-generate-file for the final stage.")


if __name__ == "__main__":
    main()
