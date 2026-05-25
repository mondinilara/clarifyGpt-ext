import argparse
import ast
import json
import re
from pathlib import Path


DATASET_NAME = 'google-research-datasets/mbpp'
CONFIG_NAME = 'sanitized'
SPLITS = ['train', 'validation', 'test', 'prompt']


def extract_signature_and_entry_point(code):
    match = re.search(r'^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*:', code, re.MULTILINE)
    if not match:
        raise ValueError(f'Could not find a function definition in code:\n{code}')
    line = match.group(0).strip()
    return line, match.group(1)


def build_prompt(signature, requirement):
    return f"{signature}\n    '''\n    {requirement.strip()}\n    '''"


def assertion_to_expression(assertion):
    tree = ast.parse(assertion.strip())
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Assert):
        return assertion

    test = tree.body[0].test
    if (
        isinstance(test, ast.Call)
        and isinstance(test.func, ast.Attribute)
        and test.func.attr == 'isclose'
        and test.args
    ):
        return ast.unparse(test.args[0])
    if isinstance(test, ast.Compare):
        return ast.unparse(test.left)
    return ast.unparse(test)


def load_mbpp_from_huggingface():
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise SystemExit(
            'Missing dependency: datasets. Run "python -m pip install -r requirements.txt" first.'
        ) from exc

    dataset = load_dataset(DATASET_NAME, CONFIG_NAME)
    rows = []
    for split in SPLITS:
        if split in dataset:
            rows.extend(dataset[split])
    return rows


def load_mbpp_from_jsonl(path):
    rows = []
    with open(path, 'r', encoding='utf8') as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def normalize_row(row):
    code = row.get('code') or row.get('solution')
    if not code:
        raise ValueError(f'Missing code/solution for task_id={row.get("task_id")}')

    signature, entry_point = extract_signature_and_entry_point(code)
    tests = row.get('test_list') or row.get('tests')
    if not tests:
        raise ValueError(f'Missing tests/test_list for task_id={row.get("task_id")}')

    if "'''" in row['prompt'] and row['prompt'].lstrip().startswith('def '):
        prompt = row['prompt']
    else:
        prompt = build_prompt(signature, row['prompt'])
    execution_tests = [assertion_to_expression(test) for test in tests]
    test_code = '\n'.join(tests)

    return {
        'task_id': int(row['task_id']),
        'prompt': prompt,
        'entry_point': entry_point,
        'tests': execution_tests,
        'test_list': tests,
        'test': test_code,
        'solution': code,
    }


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf8') as handle:
        for row in rows:
            json.dump(row, handle)
            handle.write('\n')


def write_reference_samples(path, rows, samples_per_task):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf8') as handle:
        for row in rows:
            completion = row['solution']
            for _ in range(samples_per_task):
                json.dump({
                    'task_id': row['task_id'],
                    'prompt': row['prompt'],
                    'raw_code_completion': row['solution'],
                    'samples': [completion],
                }, handle)
                handle.write('\n')


def parse_args():
    parser = argparse.ArgumentParser(
        description='Download/convert MBPP sanitized data into the JSONL files expected by ClarifyGPT.'
    )
    parser.add_argument('--input-jsonl', help='Use a local MBPP JSONL instead of downloading from Hugging Face.')
    parser.add_argument('--data-dir', default=str(Path(__file__).resolve().parent / 'data'))
    parser.add_argument('--write-reference-samples', action='store_true',
                        help='Create reference-code sample files for smoke testing only; these are not GPT-4 outputs.')
    parser.add_argument('--samples-per-task', type=int, default=25)
    return parser.parse_args()


def main():
    args = parse_args()
    data_dir = Path(args.data_dir).resolve()

    raw_rows = load_mbpp_from_jsonl(args.input_jsonl) if args.input_jsonl else load_mbpp_from_huggingface()
    rows = sorted((normalize_row(row) for row in raw_rows), key=lambda row: row['task_id'])

    mbpp_path = data_dir / 'mbpp_sanitized_microsoft.jsonl'
    tests_path = data_dir / 'mbpp_tests_final.jsonl'
    write_jsonl(mbpp_path, rows)
    write_jsonl(tests_path, rows)

    print(f'[ClarifyGPT] Wrote {len(rows)} tasks:')
    print(f'  - {mbpp_path}')
    print(f'  - {tests_path}')

    if args.write_reference_samples:
        sample_path = data_dir / 'mbpp_sanitized_microsoft_sample_0.8_25_results_final_gpt4.jsonl'
        greedy_path = data_dir / 'gpt4_greedy_mbpp' / 'mbpp_sanitized_microsoft_greedy_0.0_3_results_final_gpt4_1.jsonl'
        write_reference_samples(sample_path, rows, args.samples_per_task)
        write_reference_samples(greedy_path, rows, 1)
        print('\n[ClarifyGPT] Wrote reference-code sample files for smoke testing only:')
        print(f'  - {sample_path}')
        print(f'  - {greedy_path}')
        print('These files use MBPP reference solutions, not GPT-4 generations.')


if __name__ == '__main__':
    main()
