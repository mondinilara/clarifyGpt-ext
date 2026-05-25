import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLARIFY_DIR = PROJECT_ROOT / 'src' / 'clarify'
if str(CLARIFY_DIR) not in sys.path:
    sys.path.insert(0, str(CLARIFY_DIR))


DEFAULT_DATA_DIR = PROJECT_ROOT / 'src' / 'data'


def load_jsonl(path):
    rows = []
    with open(path, 'r', encoding='utf8') as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def append_jsonl(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a', encoding='utf8') as handle:
        json.dump(row, handle)
        handle.write('\n')


def build_generation_prompt(task):
    return (
        'Complete the following Python function. '
        'Return only the Python code for the solution, with no Markdown fences and no explanation.\n\n'
        f"{task['prompt'].strip()}"
    )


def parse_args():
    parser = argparse.ArgumentParser(description='Generate real MBPP code samples with the OpenAI API.')
    parser.add_argument('--source-path', default=str(DEFAULT_DATA_DIR / 'mbpp_sanitized_microsoft.jsonl'))
    parser.add_argument(
        '--output-path',
        default=str(DEFAULT_DATA_DIR / 'mbpp_sanitized_microsoft_sample_0.8_25_results_final_gpt4.jsonl'),
    )
    parser.add_argument('--samples-per-task', type=int, default=3)
    parser.add_argument('--temperature', type=float, default=0.8)
    parser.add_argument('--max-tokens', type=int, default=300)
    parser.add_argument('--sleep-between-tasks', type=float, default=1.0)
    parser.add_argument('--limit', type=int, help='Only process the first N tasks.')
    parser.add_argument('--force', action='store_true', help='Overwrite output file if it already exists.')
    return parser.parse_args()


def main():
    args = parse_args()
    from gpt4_utils import FewShotLLM

    source_path = Path(args.source_path)
    output_path = Path(args.output_path)

    if output_path.exists() and not args.force:
        raise SystemExit(f'Output file already exists. Use --force to overwrite it: {output_path}')
    if output_path.exists() and args.force:
        output_path.unlink()

    tasks = load_jsonl(source_path)
    if args.limit is not None:
        tasks = tasks[:args.limit]

    llm = FewShotLLM()
    instruction = 'You are an expert Python programmer.'
    examples = []

    total = len(tasks)
    for idx, task in enumerate(tasks, start=1):
        print(f'[ClarifyGPT] Generating {args.samples_per_task} samples for task {idx}/{total}: {task["task_id"]}')
        prompt = build_generation_prompt(task)
        completions = llm._completion(
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            n=args.samples_per_task,
            instruction=instruction,
            examples=examples,
            prompt=prompt,
        )

        for completion in completions:
            append_jsonl(output_path, {
                'task_id': task['task_id'],
                'prompt': task['prompt'],
                'raw_code_completion': completion,
            })

        if args.sleep_between_tasks > 0 and idx < total:
            time.sleep(args.sleep_between_tasks)

    print(f'[ClarifyGPT] Wrote real model samples to {output_path}')


if __name__ == '__main__':
    main()
