import json
import copy
import argparse
import importlib
import importlib.util
import multiprocessing
import signal
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils import *
from src.prompt.prompt_mbpp import *
import functools
from threading import Thread
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, *args, **kwargs):
        return iterable

try:
    from gpt4_utils import FewShotLLM
except ImportError:
    FewShotLLM = None


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = SCRIPT_DIR.parent / 'data'


def ensure_parent(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def missing_files(paths):
    return [str(path) for path in paths if not Path(path).exists()]


def stop_missing(stage, paths, hint=None):
    missing = missing_files(paths)
    if not missing:
        return

    print(f'\n[ClarifyGPT] Nao consegui executar a etapa "{stage}" porque faltam arquivos:')
    for path in missing:
        print(f'  - {path}')
    if hint:
        print(f'\n{hint}')
    sys.exit(2)


def indent_block(text, spaces):
    prefix = ' ' * spaces
    return '\n'.join(prefix + line if line.strip() else line for line in text.splitlines())


def prompt_parts(messages):
    instruction = messages[0]['content']
    examples = []
    for idx in range(1, len(messages), 2):
        examples.append({
            'user': messages[idx]['content'],
            'assistant': messages[idx + 1]['content'],
        })
    return instruction, examples


def create_llm():
    if FewShotLLM is None:
        raise SystemExit(
            'Missing dependency for LLM requests. Run "python -m pip install -r requirements.txt" first.'
        )
    return FewShotLLM()


def llm_usage_dict(code_llm):
    return {
        'usage': getattr(code_llm, 'last_usage', None),
        'model': getattr(code_llm, 'last_model', None),
        'provider': getattr(code_llm, 'last_provider', None),
    }


def load_prompt_module(module_name):
    if not module_name:
        return

    if module_name.endswith('.py') or Path(module_name).exists():
        module_path = Path(module_name).resolve()
        spec = importlib.util.spec_from_file_location('clarify_prompt_override', module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        module = importlib.import_module(module_name)

    globals()['askcq_prompt'] = module.askcq_prompt
    globals()['answercq_prompt'] = module.answercq_prompt
    globals()['synthesize_prompt'] = module.synthesize_prompt


def _exec_code_worker(code_to_be_test, queue):
    loc = {}
    try:
        exec(code_to_be_test, loc)
        queue.put(loc.get('xx', 'error!!!'))
    except Exception:
        queue.put('error!!!')


def exec_code_with_timeout(code_to_be_test, timeout_seconds):
    queue = multiprocessing.Queue(maxsize=1)
    process = multiprocessing.Process(target=_exec_code_worker, args=(code_to_be_test, queue))
    process.start()
    process.join(timeout_seconds)

    if process.is_alive():
        process.terminate()
        process.join(1)
        return 'error!!!'

    if queue.empty():
        return 'error!!!'

    try:
        return queue.get_nowait()
    except Exception:
        return 'error!!!'


# 1. run sample codes on tests, get task_id of the unclear prompts
def runTests_getTaskID(sample_code_file, tests_file, save_path=None, sample_count=25, limit=None, test_timeout=0.2):
    with open(tests_file, 'r') as f:
        tests_lines = f.readlines()

    with open(sample_code_file, 'r') as f:
        sample_code_lines = f.readlines()

    if limit is not None:
        tests_lines = tests_lines[:limit]

    if save_path is None:
        save_path = sample_code_file.replace(".jsonl", "_needcq.jsonl")

    ensure_parent(save_path)
    with open(save_path, 'w') as w:
        for test_idx, tests_line in tqdm(
                enumerate(tests_lines)):  # , sample_code_line in zip(tests_lines, sample_code_lines):
            tests_line = json.loads(tests_line)
            prompt = tests_line['prompt']
            entry_point = tests_line['entry_point']
            tests = tests_line['tests']
            time_limit_func = 'import signal\nfrom contextlib import contextmanager\nclass TimeoutException(Exception): pass\n\n@contextmanager\ndef time_limit(seconds: float):\n    def signal_handler(signum, frame):\n        raise TimeoutException("Timed out!")\n    signal.setitimer(signal.ITIMER_REAL, seconds)\n    signal.signal(signal.SIGALRM, signal_handler)\n    try:\n        yield\n    finally:\n        signal.setitimer(signal.ITIMER_REAL, 0)\n'

            all_test_results = {}
            for sample_code_line in sample_code_lines[test_idx * sample_count: (test_idx + 1) * sample_count]:
                sample_code_line = json.loads(sample_code_line)
                assert prompt == sample_code_line['prompt']
                generated_raw_code = sample_code_line['raw_code_completion']
                complete_code = parse_code_w_prompt_mbpp('gpt-3.5', generated_raw_code, prompt, entry_point)
                # print(complete_code)
                # assert 1==2
                test_result = []
                for test in tests:
                    test_list = test.split('\n')
                    test_list[-1] = 'xx = ' + test_list[-1]
                    test = '\n'.join(test_list)

                    if hasattr(signal, 'setitimer'):
                        code_to_be_test = time_limit_func + '\n' + complete_code + f'\n\ntry:\n    with time_limit({test_timeout}):\n' + indent_block(test, 8) + '\nexcept Exception:\n    xx = "error!!!"'
                    else:
                        code_to_be_test = complete_code + '\n\ntry:\n' + indent_block(test, 4) + '\nexcept Exception:\n    xx = "error!!!"'
                    # print(code_to_be_test)
                    if hasattr(signal, 'setitimer'):
                        loc = {}
                        try:
                            exec(code_to_be_test, loc)
                            return_value = loc['xx']
                        except Exception:
                            return_value = 'error!!!'
                    else:
                        return_value = exec_code_with_timeout(code_to_be_test, test_timeout)
                    test_result.append(return_value)

                if str(test_result) in all_test_results.keys():
                    all_test_results[str(test_result)].append(clean_format(generated_raw_code))
                else:
                    all_test_results[str(test_result)] = [clean_format(generated_raw_code)]

            # print(len(all_test_results))
            # print('=================================')
            if len(all_test_results) > 1:
                print(len(all_test_results))
                need_cq_dict = {'task_id': tests_line['task_id'], 'prompt': prompt, 'candidate_codes': [],
                                'exec_results': list(all_test_results.keys())}
                for v_idx, v in enumerate(all_test_results.values()):
                    need_cq_dict['candidate_codes'].append(v[0])
                    if v_idx >= 4:
                        break
                print(len(need_cq_dict['candidate_codes']))
                print('=================================')
                json.dump(need_cq_dict, w)
                w.write('\n')
            elif 'error!!!' in list(all_test_results.keys())[0]:
                print(list(all_test_results.keys())[0])
                need_cq_dict = {'task_id': tests_line['task_id'], 'prompt': prompt, 'candidate_codes': [],
                                'exec_results': list(all_test_results.keys())}
                for v_idx, v in enumerate(all_test_results.values()):
                    need_cq_dict['candidate_codes'].append(v[0])
                    need_cq_dict['candidate_codes'].append(v[1])
                print(len(need_cq_dict['candidate_codes']))
                print('=================================')
                json.dump(need_cq_dict, w)
                w.write('\n')

            # else:
            #     print(task_id, all_test_results.keys())

    return save_path


# 2. submit askcq task & run parallel request
def askcq_runRequest(inference_type, needcq_file, askcq_path=None):
    code_llm = create_llm()
    instruction, examples = prompt_parts(askcq_prompt[inference_type])

    with open(needcq_file, 'r') as f:
        data_lines = f.readlines()

    if askcq_path is None:
        askcq_path = needcq_file.replace(".jsonl", "_askcq_results.jsonl")

    ensure_parent(askcq_path)
    with open(askcq_path, 'w') as w:
        for data_line in tqdm(data_lines):
            data_line = json.loads(data_line)
            task_id = data_line['task_id']
            ori_prompt = data_line['prompt']
            candidate_codes = data_line['candidate_codes']

            code_string = ''
            for idx, candidate_c in enumerate(candidate_codes):
                code_string += f'Solution {idx}:\n{candidate_c}\n'

            if inference_type == 'zero_shot':
                llm_response = code_llm._completion(800, 0.0, 1,
                                                    instruction,
                                                    examples,
                                                    f'User Requirement:\n{ori_prompt.strip()}\n{code_string.strip()}'
                                                    f'\nAnalysis:\n{{insert your analysis results here}}'
                                                    f'\nClarifying Questions:\n{{insert your clarifying questions here}}',
                                                    )
            else:
                llm_response = code_llm._completion(800, 0.0, 1,
                                                    instruction,
                                                    examples,
                                                    f'User Requirement:\n{ori_prompt.strip()}\n{code_string.strip()}',
                                                    )

            for res in llm_response:
                print(res)
                print('=======================================')
                json.dump(dict(task_id=task_id, askcq=res, **llm_usage_dict(code_llm)), w)
                w.write('\n')

    return askcq_path


# 3. submit answercq task & run parallel request
def answercq_runRequest(inference_type, needcq_file, askcq_results_path, answercq_path=None):
    code_llm = create_llm()
    instruction, examples = prompt_parts(answercq_prompt[inference_type])

    with open(needcq_file, 'r') as f:
        ori_data_lines = f.readlines()

    with open(askcq_results_path, 'r') as f:
        data_lines = f.readlines()

    assert len(data_lines) == len(ori_data_lines)

    if answercq_path is None:
        answercq_path = askcq_results_path.replace(".jsonl", "_answercq_results.jsonl")

    ensure_parent(answercq_path)
    with open(answercq_path, 'w') as w:
        for ori_data_line, data_line in tqdm(zip(ori_data_lines, data_lines)):
            ori_data_line = json.loads(ori_data_line)
            data_line = json.loads(data_line)
            cq = parse_cq_mbpp(data_line['askcq'])
            task_id = ori_data_line['task_id']
            ori_prompt = ori_data_line['prompt']

            # print(answercq_prompt[inference_type][0])
            # print(answercq_prompt[inference_type][1:])
            # assert 1==2
            # print(answercq_prompt[inference_type])

            llm_response = code_llm._completion(300, 0.0, 1,
                                                instruction,
                                                examples,
                                                f'User Requirement:\n{ori_prompt.strip()}'
                                                       f'\n\n### Clarifying Questions:\n{cq.strip()}'
                                                       f'\n\n### Answers:\n{{insert answers here}}'
                                                )

            for res in llm_response:
                print(res)
                json.dump(dict(task_id=task_id, answercq=res, **llm_usage_dict(code_llm)), w)
                w.write('\n')

    return answercq_path


def answercq_w_test_runRequest(test_file, inference_type, needcq_file, askcq_results_path, answercq_path=None):
    code_llm = create_llm()
    instruction, examples = prompt_parts(answercq_prompt[inference_type])

    with open(needcq_file, 'r') as f:
        ori_data_lines = f.readlines()

    with open(askcq_results_path, 'r') as f:
        data_lines = f.readlines()

    with open(test_file, 'r') as f:
        test_lines = f.readlines()

    assert len(data_lines) == len(ori_data_lines) == len(test_lines)

    if answercq_path is None:
        answercq_path = askcq_results_path.replace(".jsonl", "_answercq_results.jsonl")

    ensure_parent(answercq_path)
    with open(answercq_path, 'w') as w:
        for ori_data_line, data_line, test_line in tqdm(zip(ori_data_lines, data_lines, test_lines)):
            ori_data_line = json.loads(ori_data_line)
            data_line = json.loads(data_line)
            test_line = json.loads(test_line)
            cq = parse_cq_mbpp(data_line['askcq'])
            task_id = ori_data_line['task_id']
            assert task_id == test_line['task_id']
            python_func = test_line['solution']
            test_cases = '\n'.join(test_line['test_list'])

            # print(answercq_prompt[inference_type][0])
            # print(answercq_prompt[inference_type][1:])
            # assert 1==2
            # print(answercq_prompt[inference_type])

            llm_response = code_llm._completion(300, 0.0, 1,
                                                instruction,
                                                examples,
                                                f'Python Function:\n{python_func.strip()}'
                                                       f'\nTest Cases:\n{test_cases.strip()}'
                                                       f'\n\n### Clarifying Questions:\n{cq.strip()}'
                                                       f'\n\n### Answers:\n{{insert answers here}}',
                                                )

            for res in llm_response:
                print(res)
                json.dump(dict(task_id=task_id, answercq=res, **llm_usage_dict(code_llm)), w)
                w.write('\n')

    return answercq_path


# 4. synthesize the prompt with cqs and answers
def synthesize_runRequest(inference_type, needcq_file, askcq_results_path, answercq_results_path,
                          synthesize_path=None):
    code_llm = create_llm()
    instruction, examples = prompt_parts(synthesize_prompt[inference_type])

    with open(needcq_file, 'r') as f:
        ori_data_lines = f.readlines()

    with open(askcq_results_path, 'r') as f:
        ask_data_lines = f.readlines()

    with open(answercq_results_path, 'r') as f:
        answer_data_lines = f.readlines()

    if synthesize_path is None:
        synthesize_path = answercq_results_path.replace(".jsonl", "_synthesize_results.jsonl")

    ensure_parent(synthesize_path)
    with open(synthesize_path, 'w') as w:
        for ori_data_line, ask_data_line, answer_data_line in tqdm(zip(ori_data_lines, ask_data_lines, answer_data_lines)):
            ori_data_line = json.loads(ori_data_line)
            ask_data_line = json.loads(ask_data_line)
            answer_data_line = json.loads(answer_data_line)

            ori_prompt = ori_data_line['prompt']
            ask_cq = ask_data_line['askcq']
            answer_cq = answer_data_line['answercq']
            task_id = answer_data_line['task_id']
            clarification = parse_clarification_mbpp(ask_cq, answer_cq)
            refined_prompt = refine_prompt_clarify(ori_prompt, clarification)

            llm_response = code_llm._completion(300, 0.0, 1,
                                                instruction,
                                                examples,
                                                f'User Requirement:\n{refined_prompt}',
                                                )

            for res in llm_response:
                print(res)
                print('=================================')
                json.dump(dict(task_id=task_id, raw_code_completion=res, **llm_usage_dict(code_llm)), w)
                w.write('\n')

    return synthesize_path


# 5. generate the final humaneval file
def generate_file(humaneval_file, greedy_generate_file, synthesize_results_list, final_path=None):
    with open(humaneval_file, 'r') as f:
        ori_data_lines = f.readlines()
    with open(greedy_generate_file, 'r') as f:
        greedy_data_lines = f.readlines()

    n = len(synthesize_results_list)
    modified_code_dict = {'task_id_list': [], 'code_list': []}
    for i in range(n):
        with open(synthesize_results_list[i], 'r') as f:
            synthesize_data_lines = f.readlines()

        modified_code_dict['task_id_list'] = []
        modified_code_dict['code_list'].append([])
        for synthesize_data_line in synthesize_data_lines:
            synthesize_data_line = json.loads(synthesize_data_line)
            task_id = synthesize_data_line['task_id']
            generated_raw_code = synthesize_data_line['raw_code_completion']

            modified_code_dict['task_id_list'].append(task_id)
            modified_code_dict['code_list'][i].append(generated_raw_code)
        assert len(modified_code_dict['task_id_list']) == len(modified_code_dict['code_list'][i])

    ensure_parent(final_path)
    with open(final_path, 'w') as w:
        for ori_idx, ori_data_line in tqdm(enumerate(ori_data_lines)):
            ori_data_line = json.loads(ori_data_line)
            task_id = ori_data_line['task_id']
            for greedy_idx, greedy_data_line in enumerate(greedy_data_lines[ori_idx * n: (ori_idx + 1) * n]):
                greedy_data_line = json.loads(greedy_data_line)

                if task_id not in modified_code_dict['task_id_list']:
                    json.dump(dict(prompt=ori_data_line['prompt'], samples=greedy_data_line['samples']), w)
                    w.write('\n')
                else:
                    entry_point = ori_data_line['entry_point']
                    idx = modified_code_dict['task_id_list'].index(task_id)
                    generated_raw_code = modified_code_dict['code_list'][greedy_idx][idx]
                    ori_prompt = ori_data_line['prompt']
                    code_completion = parse_code_wo_prompt('gpt-3.5', generated_raw_code, ori_prompt, entry_point)
                    json.dump(dict(prompt=ori_data_line['prompt'], samples=[code_completion]), w)
                    w.write('\n')

    return final_path


def build_args():
    parser = argparse.ArgumentParser(
        description='Run the ClarifyGPT GPT-4 MBPP pipeline and create missing intermediate files.'
    )
    parser.add_argument(
        '--stage',
        choices=['all', 'needcq', 'askcq', 'answercq', 'synthesize', 'final'],
        default='all',
        help='Pipeline step to run. "all" runs missing steps in order.',
    )
    parser.add_argument('--data-dir', default=str(DEFAULT_DATA_DIR), help='Directory used for input/output jsonl files.')
    parser.add_argument('--inference-type', default='three_shot')
    parser.add_argument('--run-id', type=int, default=0, help='Suffix used for generated request/result files.')
    parser.add_argument('--limit', type=int, help='Only process the first N tasks. Useful for smoke tests.')
    parser.add_argument('--samples-per-task', type=int, default=25,
                        help='How many sample-code rows exist for each task in --sample-code-file.')
    parser.add_argument('--test-timeout', type=float, default=0.2,
                        help='Maximum seconds to execute each generated sample against each test during needcq.')
    parser.add_argument('--force', action='store_true', help='Regenerate files even when they already exist.')
    parser.add_argument('--sample-code-file', help='Sample-code jsonl used to build mbpp_needcq_gpt4.jsonl.')
    parser.add_argument('--test-case-file', help='MBPP tests jsonl used to build mbpp_needcq_gpt4.jsonl.')
    parser.add_argument('--mbpp-file', help='Original MBPP jsonl used to build the final output.')
    parser.add_argument('--greedy-generate-file', help='Greedy baseline jsonl used to build the final output.')
    parser.add_argument('--needcq-path', help='Path for mbpp_needcq_gpt4.jsonl.')
    parser.add_argument('--askcq-path', help='Path for generated ask-cq results.')
    parser.add_argument('--answercq-path', help='Path for generated answer-cq results.')
    parser.add_argument('--synthesize-path', help='Path for generated synthesize results.')
    parser.add_argument('--final-path', help='Path for final MBPP output.')
    parser.add_argument('--prompt-module',
                        help='Optional Python module or .py file with askcq_prompt, answercq_prompt and synthesize_prompt.')
    return parser.parse_args()


def path_arg(value, default):
    return Path(value) if value else Path(default)


def should_run(path, force):
    return force or not Path(path).exists()


def run_pipeline(args):
    load_prompt_module(args.prompt_module)

    data_dir = Path(args.data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    inference_type = args.inference_type
    run_id = args.run_id

    sample_code_file = path_arg(
        args.sample_code_file,
        data_dir / 'mbpp_sanitized_microsoft_sample_0.8_25_results_final_gpt4.jsonl',
    )
    test_case_file = path_arg(args.test_case_file, data_dir / 'mbpp_tests_final.jsonl')
    mbpp_file = path_arg(args.mbpp_file, data_dir / 'mbpp_sanitized_microsoft.jsonl')
    greedy_generate_file = path_arg(
        args.greedy_generate_file,
        data_dir / 'gpt4_greedy_mbpp' / 'mbpp_sanitized_microsoft_greedy_0.0_3_results_final_gpt4_1.jsonl',
    )
    needcq_path = path_arg(args.needcq_path, data_dir / 'mbpp_needcq_gpt4.jsonl')
    askcq_path = path_arg(
        args.askcq_path,
        data_dir / 'generated' / f'mbpp_askcq_{inference_type}_{run_id}_gpt4_results.jsonl',
    )
    answercq_path = path_arg(
        args.answercq_path,
        data_dir / 'generated' / f'mbpp_answercq_{inference_type}_{run_id}_gpt4_results.jsonl',
    )
    synthesize_path = path_arg(
        args.synthesize_path,
        data_dir / 'generated' / f'mbpp_synthesize_{inference_type}_{run_id}_gpt4_results.jsonl',
    )
    final_path = path_arg(
        args.final_path,
        data_dir / 'generated' / f'mbpp_final_{inference_type}_gpt4_{run_id}.jsonl',
    )

    if args.stage in ['all', 'needcq'] and should_run(needcq_path, args.force):
        stop_missing(
            'needcq',
            [sample_code_file, test_case_file],
            'Gere primeiro o arquivo de amostras reais com:\n'
            '  python src\\generate_mbpp_samples.py --samples-per-task 3 --limit 5 --sleep-between-tasks 2 --force\n'
            'Ou, para smoke test fake/reference:\n'
            '  python src\\prepare_mbpp_data.py --write-reference-samples --samples-per-task 3\n'
            'Depois rode esta etapa novamente com o mesmo --samples-per-task.',
        )
        print(f'[ClarifyGPT] Gerando {needcq_path}')
        runTests_getTaskID(
            str(sample_code_file),
            str(test_case_file),
            str(needcq_path),
            sample_count=args.samples_per_task,
            limit=args.limit,
            test_timeout=args.test_timeout,
        )

    if args.stage == 'needcq':
        return

    if args.stage in ['all', 'askcq'] and should_run(askcq_path, args.force):
        stop_missing('askcq', [needcq_path], 'Rode primeiro com --stage needcq ou informe --needcq-path.')
        print(f'[ClarifyGPT] Gerando {askcq_path}')
        askcq_runRequest(inference_type, str(needcq_path), str(askcq_path))

    if args.stage == 'askcq':
        return

    if args.stage in ['all', 'answercq'] and should_run(answercq_path, args.force):
        stop_missing('answercq', [needcq_path, askcq_path], 'Rode primeiro com --stage askcq ou informe --askcq-path.')
        print(f'[ClarifyGPT] Gerando {answercq_path}')
        answercq_runRequest(inference_type, str(needcq_path), str(askcq_path), str(answercq_path))

    if args.stage == 'answercq':
        return

    if args.stage in ['all', 'synthesize'] and should_run(synthesize_path, args.force):
        stop_missing(
            'synthesize',
            [needcq_path, askcq_path, answercq_path],
            'Rode primeiro as etapas askcq e answercq, ou informe --askcq-path e --answercq-path.',
        )
        print(f'[ClarifyGPT] Gerando {synthesize_path}')
        synthesize_runRequest(inference_type, str(needcq_path), str(askcq_path), str(answercq_path), str(synthesize_path))

    if args.stage == 'synthesize':
        return

    if args.stage in ['all', 'final'] and should_run(final_path, args.force):
        stop_missing(
            'final',
            [mbpp_file, greedy_generate_file, synthesize_path],
            'Para gerar o arquivo final, coloque o dataset MBPP, a saida greedy baseline e o synthesize result '
            'em src/data ou informe --mbpp-file, --greedy-generate-file e --synthesize-path.',
        )
        print(f'[ClarifyGPT] Gerando {final_path}')
        generate_file(str(mbpp_file), str(greedy_generate_file), [str(synthesize_path)], str(final_path))


if __name__ == '__main__':
    run_pipeline(build_args())
