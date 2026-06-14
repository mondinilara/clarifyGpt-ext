# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

import ctypes

try:
    libgcc_s = ctypes.CDLL('libgcc_s.so.1')
except OSError:
    libgcc_s = None

from collections import defaultdict
from concurrent.futures import as_completed, ProcessPoolExecutor
import logging
import platform

from _execution import check_correctness, check_correctness_with_test_cases

logging.basicConfig(
    format="SystemLog: [%(asctime)s][%(name)s][%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

def evaluate_with_test_code(
    samples,
    timeout,
    workers=None,
):
    logger.info(f'Start evaluation with test code, timeout={timeout}')
    # Check the generated samples against test suites.
    if workers is None:
        workers = 1 if platform.system() == 'Windows' else None

    if workers == 1:
        existed_completion = defaultdict(set)
        results = defaultdict(defaultdict)

        unique_samples = []
        for sample in samples:
            task_id = sample["task_id"]
            completion = sample["completion"]
            if completion in existed_completion[task_id]:
                continue
            existed_completion[task_id].add(completion)
            unique_samples.append(sample)

        logger.info(f'{len(unique_samples)} execution requests are submitted')
        for idx, sample in enumerate(unique_samples):
            logger.info('[{}/{}] execution completed'.format(idx + 1, len(unique_samples)))
            result = check_correctness(
                sample["task_id"],
                sample["prompt"],
                sample["completion"],
                sample["test"],
                sample["entry_point"],
                timeout,
            )
            results[result["task_id"]][result["completion"]] = result

        logger.info('execution finished! start parsing results')
        samples_with_result = []
        for sample in samples:
            task_id = sample["task_id"]
            completion = sample["completion"]
            result = results[task_id][completion]
            sample["result"] = result["result"]
            sample["passed"] = result["passed"]
            samples_with_result.append(sample)

        assert len(samples_with_result) == len(samples), "Some problems are not attempted."
        return samples_with_result

    with ProcessPoolExecutor(max_workers=workers) as executor:

        futures = []
        existed_completion = defaultdict(set)
        results = defaultdict(defaultdict)

        for sample in samples:
            task_id = sample["task_id"]
            prompt = sample['prompt']
            test = sample['test']
            entry_point = sample['entry_point']
            completion = sample["completion"]
            if completion in existed_completion[task_id]:
                continue
            existed_completion[task_id].add(completion)
            args = (task_id, prompt, completion, test, entry_point, timeout)
            future = executor.submit(check_correctness, *args)
            futures.append(future)
        logger.info(f'{len(futures)} execution requests are submitted')
        
        for idx, future in enumerate(as_completed(futures)):
            logger.info('[{}/{}] execution completed'.format(idx+1, len(futures)))
            result = future.result()
            results[result["task_id"]][result["completion"]] = result

    logger.info('execution finished! start parsing results')
    samples_with_result = []
    for sample in samples:
        task_id = sample["task_id"]
        completion = sample["completion"]
        result = results[task_id][completion]
        sample["result"] = result["result"]
        sample["passed"] = result["passed"]
        samples_with_result.append(sample)

    assert len(samples_with_result) == len(samples), "Some problems are not attempted."
    return samples_with_result

def evaluate_with_test_cases(
    solutions,
    test_cases_dict,
    timeout,
    limit,
    workers=None,
):
    logger.info(f'Start evaluation with test cases, timeout={timeout}, limit={limit}')
    # Check the generated solutions against test suites.
    if workers is None:
        workers = 1 if platform.system() == 'Windows' else None

    if workers == 1:
        results_list = []
        existed_completion = defaultdict(set)

        unique_solutions = []
        for solution in solutions:
            task_id = solution['task_id']
            completion = solution['completion']
            if completion in existed_completion[task_id]:
                continue
            existed_completion[task_id].add(completion)
            task_test_cases = test_cases_dict[task_id]
            if not task_test_cases:
                continue
            limited_task_test_cases = [cases_per_sample[:limit] for cases_per_sample in task_test_cases]
            limited_task_test_cases = sum(limited_task_test_cases, [])
            unique_solutions.append((solution, list(set(limited_task_test_cases))))

        logger.info(f'{len(unique_solutions)} execution requests are submitted')
        for idx, (solution, limited_task_test_cases) in enumerate(unique_solutions):
            logger.info('[{}/{}] execution completed'.format(idx + 1, len(unique_solutions)))
            results_list.append(check_correctness_with_test_cases(
                solution['task_id'],
                solution['prompt'],
                solution['completion'],
                limited_task_test_cases,
                timeout,
            ))

        logger.info('execution finished!')
        return results_list

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = []
        results_list = []
        existed_completion = defaultdict(set)

        for solution in solutions:
            task_id = solution['task_id']
            prompt = solution['prompt']
            completion = solution['completion']
            if completion in existed_completion[task_id]:
                continue
            existed_completion[task_id].add(completion)
            task_test_cases = test_cases_dict[task_id]
            if not task_test_cases:
                continue
            # get limited test cases
            limited_task_test_cases = [cases_per_sample[:limit] for cases_per_sample in task_test_cases]
            limited_task_test_cases = sum(limited_task_test_cases, [])
            
            args = (task_id, prompt, completion, list(set(limited_task_test_cases)), timeout)
            future = executor.submit(check_correctness_with_test_cases, *args)
            futures.append(future)

        logger.info(f'{len(futures)} execution requests are submitted')
        for idx, future in enumerate(as_completed(futures)):
            logger.info('[{}/{}] execution completed'.format(idx+1, len(futures)))
            result = future.result()
            results_list.append(result)

    logger.info('execution finished!')
    return results_list

