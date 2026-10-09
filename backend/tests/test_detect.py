"""Language detection + prompt grounding tests."""

from app.mentor_prompts import chat_system_prompt, hint_system_prompt
from app.services.detect import detect_language

PYTHON = "def average(numbers):\n    total = 0\n    return total / len(numbers)\n"
JS = "function average(nums) {\n  let total = 0;\n  return total / nums.length;\n}"
TS = "function average(nums: number[]): number {\n  return nums.length;\n}"
JAVA = "public class Stats {\n    public static void main(String[] args) {\n        System.out.println(1);\n    }\n}"
CPP = "#include <iostream>\nint main() {\n    std::cout << 1;\n}"
CSHARP = "using System;\nclass A {\n    static void Main() {\n        Console.WriteLine(1);\n    }\n}"
GO = "package main\nimport \"fmt\"\nfunc main() {\n    fmt.Println(1)\n}"
SQL = "SELECT department, AVG(bonus) FROM employees GROUP BY department;"


def test_detects_all_supported_languages():
    assert detect_language(PYTHON) == "python"
    assert detect_language(JS) == "javascript"
    assert detect_language(TS) == "typescript"
    assert detect_language(JAVA) == "java"
    assert detect_language(CPP) == "cpp"
    assert detect_language(CSHARP) == "csharp"
    assert detect_language(GO) == "go"
    assert detect_language(SQL) == "sql"


def test_unknown_on_empty_ambiguous_tie():
    assert detect_language("") == "unknown"
    assert detect_language("   ") == "unknown"
    assert detect_language("x = 1") == "unknown"
    assert detect_language("print(x)\nconsole.log(y)") == "unknown"


def test_chat_prompt_contains_code_and_grounding_rules():
    prompt = chat_system_prompt(language="python", code=PYTHON, hints_left=3)
    assert PYTHON in prompt
    assert "python" in prompt
    assert "NEVER ask the student to paste code" in prompt
    assert "ONE suspicious area" in prompt
    assert "Maximum 80 words" in prompt


def test_hint_prompt_contains_code():
    prompt = hint_system_prompt(language="go", code=GO, hints_left=2)
    assert GO in prompt
    assert "already provided above" in prompt


def test_session_auto_detect_and_unknown(user_headers):
    from tests.conftest import client

    r = client.post(
        "/api/sessions", json={"language": "auto", "code": GO}, headers=user_headers
    )
    assert r.status_code == 201, r.text
    assert r.json()["language"] == "go"

    r = client.post(
        "/api/sessions", json={"language": "auto", "code": "x = 1"}, headers=user_headers
    )
    assert r.status_code == 422
    assert "explicitly" in r.json()["detail"]


def test_snippets_cover_all_languages():
    from tests.conftest import client

    r = client.get("/api/snippets")
    assert r.status_code == 200
    langs = {s["language"] for s in r.json()}
    assert langs == {
        "python", "javascript", "typescript", "java",
        "cpp", "csharp", "go", "sql",
    }
