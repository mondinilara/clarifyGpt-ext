from copy import deepcopy

from src.prompt.prompt_mbpp import (
    askcq_prompt as original_askcq_prompt,
    answercq_prompt as original_answercq_prompt,
    synthesize_prompt as original_synthesize_prompt,
)


askcq_prompt = deepcopy(original_askcq_prompt)
answercq_prompt = deepcopy(original_answercq_prompt)
synthesize_prompt = deepcopy(original_synthesize_prompt)


askcq_prompt["three_shot"] = [
    {
        "role": "system",
        "content": (
            "Given a requirement and candidate solutions, find ambiguity. "
            "Compare solution behavior, then output only: ### Analysis and ### Clarifying Questions."
        ),
    },
    {
        "role": "user",
        "content": (
            "User Requirement:\n"
            "def lateralsuface_cylinder(r,h):\n"
            "    '''\n"
            "    Write a function to find the lateral surface area of a cylinder.\n"
            "    '''\n"
            "Solution 0:\n"
            "def lateralsuface_cylinder(r,h):\n"
            "    return 2 * 3.1415 * r * h\n"
            "Solution 1:\n"
            "import math\n"
            "def lateralsuface_cylinder(r,h):\n"
            "    return 2 * math.pi * r * h"
        ),
    },
    {
        "role": "assistant",
        "content": (
            "### Analysis:\n"
            "Both compute lateral surface area. They differ only in pi precision: 3.1415 vs math.pi.\n"
            "### Clarifying Questions:\n"
            "1. What do r and h represent?\n"
            "2. Should pi be approximate or exact?"
        ),
    },
    {
        "role": "user",
        "content": (
            "User Requirement:\n"
            "def max_val(listval):\n"
            "    '''\n"
            "    Write a function to find the maximum value in a given heterogeneous list.\n"
            "    '''\n"
            "Solution 0:\n"
            "def max_val(listval):\n"
            "    return max(listval)\n"
            "Solution 1:\n"
            "def max_val(listval):\n"
            "    return max(listval)"
        ),
    },
    {
        "role": "assistant",
        "content": (
            "### Analysis:\n"
            "Both use max() directly. Ambiguity: heterogeneous may mix incomparable types.\n"
            "### Clarifying Questions:\n"
            "1. What types can appear in the list?\n"
            "2. Should non-integers be ignored?\n"
            "3. Provide an input-output example."
        ),
    },
    {
        "role": "user",
        "content": (
            "User Requirement:\n"
            "import collections as ct\n"
            "def merge_dictionaries_three(dict1,dict2, dict3):\n"
            "    '''\n"
            "    Write a function to merge three dictionaries into a single dictionary.\n"
            "    '''\n"
            "Solution 0:\n"
            "def merge_dictionaries_three(dict1,dict2, dict3):\n"
            "    merged_dict = ct.ChainMap(dict1, dict2, dict3)\n"
            "    return dict(merged_dict)\n"
            "Solution 1:\n"
            "def merge_dictionaries_three(dict1,dict2, dict3):\n"
            "    return ct.ChainMap(dict1, dict2, dict3)\n"
            "Solution 2:\n"
            "def merge_dictionaries_three(dict1, dict2, dict3):\n"
            "    return {**dict1, **dict2, **dict3}"
        ),
    },
    {
        "role": "assistant",
        "content": (
            "### Analysis:\n"
            "Solutions differ on output type and duplicate-key precedence: dict(ChainMap), ChainMap, or unpacking.\n"
            "### Clarifying Questions:\n"
            "1. Should output be dict or ChainMap?\n"
            "2. If keys overlap, which dictionary wins?\n"
            "3. Provide one expected example."
        ),
    },
]


answercq_prompt["three_shot"] = [
    {
        "role": "system",
        "content": (
            "Answer the clarifying questions from the requirement. "
            "If missing, infer a reasonable answer. Output only ### Answers."
        ),
    },
    {
        "role": "user",
        "content": (
            "User Requirement:\n"
            "def lateralsuface_cylinder(r,h):\n"
            "    '''\n"
            "    Write a function to find the lateral surface area of a cylinder.\n"
            "    '''\n"
            "### Clarifying Questions:\n"
            "1. What do r and h represent?\n"
            "2. Should pi be approximate or exact?\n"
            "### Answers:\n"
            "{insert answers here}"
        ),
    },
    {
        "role": "assistant",
        "content": (
            "### Answers:\n"
            "1. r is radius; h is height.\n"
            "2. Approximate pi such as 3.1415 is acceptable."
        ),
    },
    {
        "role": "user",
        "content": (
            "User Requirement:\n"
            "def max_val(listval):\n"
            "    '''\n"
            "    Write a function to find the maximum value in a given heterogeneous list.\n"
            "    '''\n"
            "### Clarifying Questions:\n"
            "1. What types can appear in the list?\n"
            "2. Should non-integers be ignored?\n"
            "3. Provide an input-output example.\n"
            "### Answers:\n"
            "{insert answers here}"
        ),
    },
    {
        "role": "assistant",
        "content": (
            "### Answers:\n"
            "1. The list may contain mixed types, e.g. strings and integers.\n"
            "2. Yes, compare only integers.\n"
            "3. ['Python', 30, 20, 40, 50, 'version'] -> 50."
        ),
    },
    {
        "role": "user",
        "content": (
            "User Requirement:\n"
            "import collections as ct\n"
            "def merge_dictionaries_three(dict1,dict2, dict3):\n"
            "    '''\n"
            "    Write a function to merge three dictionaries into a single dictionary.\n"
            "    '''\n"
            "### Clarifying Questions:\n"
            "1. Should output be dict or ChainMap?\n"
            "2. If keys overlap, which dictionary wins?\n"
            "3. Provide one expected example.\n"
            "### Answers:\n"
            "{insert answers here}"
        ),
    },
    {
        "role": "assistant",
        "content": (
            "### Answers:\n"
            "1. Return a regular dictionary.\n"
            "2. The first dictionary wins on duplicate keys.\n"
            "3. merge_dictionaries_three({'B':'Black'}, {'B':'Blue'}, {'G':'Green'}) -> {'B':'Black','G':'Green'}."
        ),
    },
]


synthesize_prompt["three_shot"] = [
    {
        "role": "system",
        "content": (
            "Given a clarified requirement, return only the Python function. "
            "Follow the signature exactly. No explanations, tests, or extra imports unless already provided."
        ),
    },
    {
        "role": "user",
        "content": (
            "User Requirement:\n"
            "def lateralsuface_cylinder(r,h):\n"
            "    '''\n"
            "    Write a function to find the lateral surface area of a cylinder.\n"
            "    Clarification:\n"
            "    r is radius; h is height. Approximate pi such as 3.1415 is acceptable.\n"
            "    '''"
        ),
    },
    {
        "role": "assistant",
        "content": "def lateralsuface_cylinder(r,h):\n    return 2 * 3.1415 * r * h",
    },
    {
        "role": "user",
        "content": (
            "User Requirement:\n"
            "def max_val(listval):\n"
            "    '''\n"
            "    Write a function to find the maximum value in a given heterogeneous list.\n"
            "    Clarification:\n"
            "    The list may mix types; compare only integers.\n"
            "    '''"
        ),
    },
    {
        "role": "assistant",
        "content": (
            "def max_val(listval):\n"
            "     max_val = max(i for i in listval if isinstance(i, int))\n"
            "     return(max_val)"
        ),
    },
    {
        "role": "user",
        "content": (
            "User Requirement:\n"
            "import collections as ct\n"
            "def merge_dictionaries_three(dict1,dict2, dict3):\n"
            "    '''\n"
            "    Write a function to merge three dictionaries into a single dictionary.\n"
            "    Clarification:\n"
            "    Return a regular dict. Include all keys; on duplicate keys, the first dictionary wins.\n"
            "    '''"
        ),
    },
    {
        "role": "assistant",
        "content": (
            "def merge_dictionaries_three(dict1,dict2, dict3):\n"
            "    merged_dict = ct.ChainMap(dict1, dict2, dict3)\n"
            "    return dict(merged_dict)"
        ),
    },
]
