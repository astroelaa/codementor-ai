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


def test_detects_c_and_rust():
    c_code = '#include <stdio.h>\nint main(void) {\n    printf("hi\\n");\n    return 0;\n}'
    assert detect_language(c_code) == "c"
    rust_code = 'fn main() {\n    let mut x = 1;\n    println!("{}", x);\n}'
    assert detect_language(rust_code) == "rust"


def test_rust_function_without_main():
    code = (
        "fn average(nums: &[f64]) -> f64 {\n"
        "    let mut total = 0.0;\n"
        "    for i in 1..=nums.len() {\n"
        "        total += nums[i];\n"
        "    }\n"
        "    total / nums.len() as f64\n"
        "}"
    )
    assert detect_language(code) == "rust"


def test_registry_schemas_and_snippets_agree():
    import app.schemas as schemas
    from app.services.languages import LANGUAGES
    from app.services.snippets import SAMPLE_SNIPPETS

    literal_keys = set(schemas.Language.__args__)
    assert set(LANGUAGES.keys()) == literal_keys
    assert set(SAMPLE_SNIPPETS.keys()) == literal_keys
    for key, info in LANGUAGES.items():
        assert info.key == key
        assert info.prompt_note
        assert info.execution == "none"


def test_languages_endpoint_lists_capabilities():
    from tests.conftest import client

    r = client.get("/api/languages")
    assert r.status_code == 200
    rows = {row["key"]: row for row in r.json()}
    assert len(rows) == 10
    assert rows["csharp"]["highlight"] == "fallback"
    assert rows["rust"]["editor"] == "rust"
    assert rows["python"]["docs"]
    assert all(row["execution"] == "none" for row in rows.values())


def test_resources_endpoint_lists_curated_links():
    from tests.conftest import client

    r = client.get("/api/resources")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) >= 10
    assert all({"language", "title", "url", "license"} <= set(row) for row in rows)

    r = client.get("/api/resources?language=rust")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["url"].startswith("https://")


def test_prompt_carries_language_guidance():
    from app.mentor_prompts import chat_system_prompt as chat

    prompt = chat(language="rust", code="fn main() {}", hints_left=3)
    assert "LANGUAGE GUIDANCE (Rust)" in prompt
    assert "ownership" in prompt.lower()


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


def test_prompt_handles_greetings_without_verbatim_repeats():
    prompt = chat_system_prompt(language="python", code=PYTHON, hints_left=3)
    assert "no reasoning about the code" in prompt
    assert "Never repeat a previous reply verbatim" in prompt


def test_goal_preamble_shapes_prompt():
    from app.mentor_prompts import chat_system_prompt as chat

    review = chat(language="python", code=PYTHON, hints_left=3, goal="review")
    assert "REVIEW MODE" in review
    explain = chat(language="python", code=PYTHON, hints_left=3, goal="explain")
    assert "EXPLAIN MODE" in explain
    debug = chat(language="python", code=PYTHON, hints_left=3)
    assert "DEBUG MODE" in debug


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


def test_session_goal_stored_and_validated(user_headers):
    from tests.conftest import client

    r = client.post(
        "/api/sessions",
        json={"language": "python", "code": "x = 1", "goal": "review"},
        headers=user_headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["goal"] == "review"

    r = client.post(
        "/api/sessions",
        json={"language": "python", "code": "x = 1"},
        headers=user_headers,
    )
    assert r.json()["goal"] == "debug"

    r = client.post(
        "/api/sessions",
        json={"language": "python", "code": "x = 1", "goal": "fix-it-all"},
        headers=user_headers,
    )
    assert r.status_code == 422


def test_snippets_cover_all_languages():
    from tests.conftest import client
    from app.services.languages import supported_keys

    r = client.get("/api/snippets")
    assert r.status_code == 200
    langs = {s["language"] for s in r.json()}
    assert langs == set(supported_keys())
