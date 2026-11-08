from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SUBMISSIONS_PATH = ROOT / "lab2_large_submissions.jsonl"
LABELS_PATH = ROOT / "lab2_large_labels.json"
ASSIGNMENT_ID = "lab2-python"
SEED = 20261108

TEMPLATES = {
    "factorial_recursive": """def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)


def solve():
    data = input().strip()
    number = int(data)
    result = factorial(number)
    print(result)
""",
    "factorial_iterative": """def factorial(n):
    result = 1
    for value in range(2, n + 1):
        result *= value
    return result


def solve():
    number = int(input().strip())
    print(factorial(number))
""",
    "palindrome_slice": """def is_palindrome(text):
    cleaned = text.lower().replace(" ", "")
    return cleaned == cleaned[::-1]


def solve():
    value = input().strip()
    print(is_palindrome(value))
""",
    "palindrome_two_pointer": """def is_palindrome(text):
    left = 0
    right = len(text) - 1
    while left < right:
        if text[left].lower() != text[right].lower():
            return False
        left += 1
        right -= 1
    return True
""",
    "fibonacci_iterative": """def fibonacci(n):
    if n <= 1:
        return n
    previous = 0
    current = 1
    for _ in range(2, n + 1):
        previous, current = current, previous + current
    return current
""",
    "fibonacci_recursive": """def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)
""",
    "prime_trial": """def is_prime(number):
    if number < 2:
        return False
    divisor = 2
    while divisor * divisor <= number:
        if number % divisor == 0:
            return False
        divisor += 1
    return True
""",
    "prime_for": """def is_prime(n):
    if n < 2:
        return False
    for divisor in range(2, int(n ** 0.5) + 1):
        if n % divisor == 0:
            return False
    return True
""",
    "count_vowels_loop": """def count_vowels(text):
    total = 0
    vowels = set("aeiou")
    for char in text.lower():
        if char in vowels:
            total += 1
    return total
""",
    "count_vowels_sum": """def count_vowels(text):
    vowels = "aeiou"
    return sum(1 for char in text.lower() if char in vowels)
""",
    "sort_numbers_builtin": """def sort_numbers(values):
    return sorted(values)
""",
    "sort_numbers_bubble": """def sort_numbers(values):
    items = list(values)
    for left in range(len(items)):
        for right in range(0, len(items) - left - 1):
            if items[right] > items[right + 1]:
                items[right], items[right + 1] = items[right + 1], items[right]
    return items
""",
    "gcd_euclid": """def gcd(a, b):
    while b:
        a, b = b, a % b
    return abs(a)
""",
    "gcd_recursive": """def gcd(a, b):
    if b == 0:
        return abs(a)
    return gcd(b, a % b)
""",
    "brackets_stack": """def is_balanced(text):
    pairs = {')': '(', ']': '[', '}': '{'}
    stack = []
    for char in text:
        if char in pairs.values():
            stack.append(char)
        elif char in pairs:
            if not stack or stack.pop() != pairs[char]:
                return False
    return not stack
""",
    "brackets_counter": """def is_balanced(text):
    depth = 0
    for char in text:
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        if depth < 0:
            return False
    return depth == 0
""",
}

TASK_GROUPS = [
    ("factorial", "factorial_recursive", "factorial_iterative"),
    ("palindrome", "palindrome_slice", "palindrome_two_pointer"),
    ("fibonacci", "fibonacci_iterative", "fibonacci_recursive"),
    ("prime", "prime_trial", "prime_for"),
    ("vowels", "count_vowels_loop", "count_vowels_sum"),
    ("sort", "sort_numbers_builtin", "sort_numbers_bubble"),
    ("gcd", "gcd_euclid", "gcd_recursive"),
    ("brackets", "brackets_stack", "brackets_counter"),
]

RENAMES = {
    "number": "value",
    "value": "item",
    "result": "answer",
    "total": "count",
    "text": "raw_text",
    "cleaned": "normalized",
    "previous": "prev",
    "current": "cur",
    "divisor": "factor",
    "values": "data",
    "items": "numbers",
    "char": "symbol",
}


def main() -> None:
    rng = random.Random(SEED)
    submissions: list[dict[str, object]] = []
    labels: list[dict[str, object]] = []
    submitted_at = datetime(2026, 11, 3, 9, 0, tzinfo=timezone(timedelta(hours=3)))

    counter = 1
    for task_name, primary_key, independent_key in TASK_GROUPS:
        for cluster in range(10):
            base_code = TEMPLATES[primary_key]
            independent_code = TEMPLATES[independent_key]

            ids = []
            variants = [
                ("base", base_code, True),
                ("renamed", rename_variables(base_code), True),
                ("comments", add_comments(base_code, task_name), True),
                ("whitespace", change_whitespace(base_code), True),
                ("independent", independent_code, False),
            ]
            for variant_name, code, review_required in variants:
                submission_id = f"large-{counter:04d}"
                ids.append((submission_id, variant_name, review_required))
                submissions.append(
                    submission_payload(
                        submission_id=submission_id,
                        assignment_id=ASSIGNMENT_ID,
                        student_id=f"student-large-{counter:04d}",
                        submitted_at=submitted_at + timedelta(minutes=counter),
                        text_answer=f"Generated {task_name} {variant_name} sample.",
                        code=code,
                    )
                )
                counter += 1

            base_id = ids[0][0]
            for candidate_id, variant_name, review_required in ids[1:]:
                labels.append(
                    label_payload(
                        base_id,
                        candidate_id,
                        review_required=review_required,
                        relation=(
                            f"{task_name}_{variant_name}"
                            if review_required
                            else f"{task_name}_independent_solution"
                        ),
                    )
                )

            if cluster == 0:
                same_student_first = f"large-{counter:04d}"
                submissions.append(
                    submission_payload(
                        submission_id=same_student_first,
                        assignment_id=ASSIGNMENT_ID,
                        student_id=f"student-repeat-{task_name}",
                        submitted_at=submitted_at + timedelta(minutes=counter),
                        text_answer=f"Same-student first {task_name} version.",
                        code=base_code,
                    )
                )
                counter += 1
                same_student_second = f"large-{counter:04d}"
                submissions.append(
                    submission_payload(
                        submission_id=same_student_second,
                        assignment_id=ASSIGNMENT_ID,
                        student_id=f"student-repeat-{task_name}",
                        submitted_at=submitted_at + timedelta(minutes=counter),
                        text_answer=f"Same-student second {task_name} version.",
                        code=add_comments(base_code, task_name),
                    )
                )
                counter += 1
                labels.append(
                    label_payload(
                        same_student_first,
                        same_student_second,
                        review_required=False,
                        relation=f"{task_name}_same_student_repeated_version",
                    )
                )

    special_ids: dict[str, str] = {}
    for special_name, code in (
        ("template_only_a", "def solve():\n    data = input().strip()\n    result = data\n    print(result)\n"),
        ("template_only_b", "def solve():\n    data = input().strip()\n    result = data\n    print(result)\n"),
        ("empty", ""),
        ("comment_only", "# generated empty solution\n# no executable code\n"),
        ("syntax_error", "def solve(\n    print('broken')\n"),
    ):
        submission_id = f"large-{counter:04d}"
        special_ids[special_name] = submission_id
        submissions.append(
            submission_payload(
                submission_id=submission_id,
                assignment_id=ASSIGNMENT_ID,
                student_id=f"student-special-{special_name}",
                submitted_at=submitted_at + timedelta(minutes=counter),
                text_answer=f"Special case {special_name}.",
                code=code,
            )
        )
        counter += 1

    labels.extend(
        [
            label_payload(special_ids["template_only_a"], special_ids["template_only_b"], review_required=False, relation="template_only"),
            label_payload(special_ids["empty"], special_ids["comment_only"], review_required=False, relation="insufficient_data"),
            label_payload(special_ids["syntax_error"], special_ids["template_only_a"], review_required=False, relation="syntax_error"),
        ]
    )

    rng.shuffle(submissions)
    SUBMISSIONS_PATH.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in submissions) + "\n",
        encoding="utf-8",
    )
    LABELS_PATH.write_text(
        json.dumps(labels, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "seed": SEED,
                "submissions": len(submissions),
                "labels": len(labels),
                "submissions_path": str(SUBMISSIONS_PATH),
                "labels_path": str(LABELS_PATH),
            },
            ensure_ascii=False,
        )
    )


def submission_payload(
    *,
    submission_id: str,
    assignment_id: str,
    student_id: str,
    submitted_at: datetime,
    text_answer: str,
    code: str,
) -> dict[str, object]:
    return {
        "submission_id": submission_id,
        "assignment_id": assignment_id,
        "student_id": student_id,
        "submitted_at": submitted_at.isoformat(),
        "text_answer": text_answer,
        "code": code,
        "language": "python",
        "ai_declaration": {"used": False, "details": None},
    }


def label_payload(
    left: str,
    right: str,
    *,
    review_required: bool,
    relation: str,
) -> dict[str, object]:
    return {
        "left_submission_id": left,
        "right_submission_id": right,
        "review_required": review_required,
        "relation": relation,
        "notes": "Generated deterministic labeled pair for Lab 2 evaluation.",
    }


def rename_variables(code: str) -> str:
    result = code
    for old, new in RENAMES.items():
        result = result.replace(old, new)
    return result


def add_comments(code: str, task_name: str) -> str:
    lines = code.splitlines()
    output: list[str] = [f"# generated {task_name} solution"]
    for index, line in enumerate(lines):
        output.append(line)
        if index == 1:
            output.append("    # keep the same algorithmic structure")
    return "\n".join(output) + "\n"


def change_whitespace(code: str) -> str:
    return "\n".join(line.rstrip() + ("  " if line.strip() else "") for line in code.splitlines()) + "\n"


if __name__ == "__main__":
    main()
