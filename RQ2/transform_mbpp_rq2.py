import argparse
import ast
import copy
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "src" / "data" / "mbpp_sanitized_microsoft.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "RQ2" / "data"


DOCSTRING_REWRITES = [
    ("Write a python function to ", "Implement a Python routine that "),
    ("Write a function to ", "Implement a function that "),
    ("Write a python function which ", "Implement a Python routine that "),
    ("Write a function which ", "Implement a function that "),
    ("Write a program to ", "Create code that "),
    ("given ", "provided "),
    ("the given ", "the supplied "),
    ("find ", "compute "),
    ("check whether ", "determine whether "),
    ("check if ", "determine if "),
    ("returns ", "produces "),
    ("return ", "produce "),
]


def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            json.dump(row, handle, ensure_ascii=False)
            handle.write("\n")


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(obj, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def parse_signature(prompt):
    first_line = prompt.strip().splitlines()[0]
    module = ast.parse(first_line + "\n    pass\n")
    func = module.body[0]
    if not isinstance(func, ast.FunctionDef):
        raise ValueError(f"Could not parse function signature: {first_line}")
    return first_line, func.name, [arg.arg for arg in func.args.args]


def replace_identifier(text, old, new):
    return re.sub(rf"\b{re.escape(old)}\b", new, text)


def rewrite_docstring(text):
    rewritten = text
    for old, new in DOCSTRING_REWRITES:
        rewritten = rewritten.replace(old, new)

    if rewritten == text:
        rewritten = "Solve the task described here: " + rewritten

    return rewritten


def extract_docstring(prompt):
    match = re.search(r"'''(.*?)'''", prompt, flags=re.DOTALL)
    if not match:
        return None
    return match.group(1)


def build_prompt(new_name, new_args, old_prompt):
    docstring = extract_docstring(old_prompt)
    if docstring is None:
        rewritten_docstring = " Implement the requested behavior. "
    else:
        rewritten_docstring = rewrite_docstring(docstring)

    return (
        f"def {new_name}({', '.join(new_args)}):\n"
        "    '''\n"
        f"{rewritten_docstring.strip()}\n"
        "    '''"
    )


def can_reorder_args(args):
    return len(args) >= 2


class TestCallTransformer(ast.NodeTransformer):
    def __init__(self, old_name, new_name, reverse_args):
        self.old_name = old_name
        self.new_name = new_name
        self.reverse_args = reverse_args

    def visit_Call(self, node):
        self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id == self.old_name:
            node.func.id = self.new_name
            if self.reverse_args and len(node.args) >= 2 and not node.keywords:
                node.args = list(reversed(node.args))
        return node


def transform_test_code(text, old_name, new_name, reverse_args):
    try:
        tree = ast.parse(text)
        tree = TestCallTransformer(old_name, new_name, reverse_args).visit(tree)
        ast.fix_missing_locations(tree)
        return ast.unparse(tree)
    except Exception:
        result = replace_identifier(text, old_name, new_name)
        return result


def transform_test_expr(text, old_name, new_name, reverse_args):
    try:
        tree = ast.parse(text, mode="eval")
        tree = TestCallTransformer(old_name, new_name, reverse_args).visit(tree)
        ast.fix_missing_locations(tree)
        return ast.unparse(tree)
    except Exception:
        result = replace_identifier(text, old_name, new_name)
        return result


def transform_tests(row, old_name, new_name, reverse_args):
    transformed = copy.deepcopy(row)
    transformed["tests"] = [
        transform_test_expr(value, old_name, new_name, reverse_args) for value in row["tests"]
    ]
    transformed["test_list"] = [
        transform_test_code(value, old_name, new_name, reverse_args) for value in row["test_list"]
    ]
    transformed["test"] = "\n".join(transformed["test_list"])
    return transformed


def transform_expression(text, old_name, new_name, arg_map):
    result = replace_identifier(text, old_name, new_name)
    for old_arg, new_arg in arg_map.items():
        result = replace_identifier(result, old_arg, new_arg)
    return result


def transform_solution(solution, old_name, new_name, arg_map, prompt_args):
    result = replace_identifier(solution, old_name, new_name)
    for old_arg, new_arg in arg_map.items():
        result = replace_identifier(result, old_arg, new_arg)
    result = re.sub(
        rf"def\s+{re.escape(new_name)}\s*\([^)]*\)\s*:",
        f"def {new_name}({', '.join(prompt_args)}):",
        result,
        count=1,
    )
    return result


def transform_row(row):
    _first_line, old_name, old_args = parse_signature(row["prompt"])
    new_name = f"rq2_task_{row['task_id']}"
    renamed_args = [f"rq2_arg_{idx + 1}" for idx, _ in enumerate(old_args)]

    if can_reorder_args(renamed_args):
        new_args = list(reversed(renamed_args))
        reorder_applied = True
    else:
        new_args = renamed_args
        reorder_applied = False

    arg_map = dict(zip(old_args, renamed_args))
    transformed = transform_tests(row, old_name, new_name, reorder_applied)
    transformed["prompt"] = build_prompt(new_name, new_args, row["prompt"])
    transformed["entry_point"] = new_name
    transformed["solution"] = transform_solution(row.get("solution", ""), old_name, new_name, arg_map, new_args)

    report = {
        "task_id": row["task_id"],
        "old_entry_point": old_name,
        "new_entry_point": new_name,
        "old_args": old_args,
        "renamed_args": renamed_args,
        "prompt_arg_order": new_args,
        "function_renamed": old_name != new_name,
        "arguments_renamed": old_args != renamed_args,
        "arguments_reordered_in_prompt": reorder_applied,
        "docstring_paraphrased": True,
    }

    return transformed, report


def parse_args():
    parser = argparse.ArgumentParser(description="Build RQ2 MBPP data-leakage stress-test inputs.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Original MBPP jsonl.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for transformed files.")
    parser.add_argument("--limit", type=int, help="Optional number of tasks to transform.")
    return parser.parse_args()


def main():
    args = parse_args()
    rows = load_jsonl(Path(args.input))
    if args.limit:
        rows = rows[: args.limit]

    transformed_rows = []
    report_rows = []
    for row in rows:
        transformed, report = transform_row(row)
        transformed_rows.append(transformed)
        report_rows.append(report)

    output_dir = Path(args.output_dir)
    write_jsonl(output_dir / "mbpp_rq2_transformed.jsonl", transformed_rows)
    write_jsonl(output_dir / "mbpp_rq2_tests_final.jsonl", transformed_rows)
    write_jsonl(output_dir / "mbpp_rq2_transform_report.jsonl", report_rows)
    write_json(
        output_dir / "mbpp_rq2_summary.json",
        {
            "source": str(Path(args.input)),
            "task_count": len(transformed_rows),
            "outputs": {
                "source": str(output_dir / "mbpp_rq2_transformed.jsonl"),
                "tests": str(output_dir / "mbpp_rq2_tests_final.jsonl"),
                "report": str(output_dir / "mbpp_rq2_transform_report.jsonl"),
            },
            "transformations": [
                "function entry_point renamed to rq2_task_<task_id>",
                "all formal parameters renamed to rq2_arg_<position>",
                "formal parameter order reversed in the prompt when the function has at least two parameters",
                "docstring paraphrased with deterministic lexical rewrites",
                "tests updated to call the renamed function",
            ],
        },
    )
    print(f"[RQ2] Wrote {len(transformed_rows)} transformed tasks to {output_dir}")


if __name__ == "__main__":
    main()
