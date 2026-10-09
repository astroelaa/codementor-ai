"""Sample buggy snippets students can try, one per supported language."""

from app.schemas import SnippetResponse

SAMPLE_SNIPPETS: dict[str, SnippetResponse] = {
    "python": SnippetResponse(
        language="python",
        title="Average of a list",
        description=(
            "Works for normal lists, crashes on one specific input. "
            "Find out which one, and why."
        ),
        code=(
            "def average(numbers):\n"
            '    """Return the average of a list of numbers."""\n'
            "    total = 0\n"
            "    for n in numbers:\n"
            "        total += n\n"
            "    return total / len(numbers)\n"
            "\n"
            "\n"
            "print(average([2, 4, 6]))\n"
            "print(average([]))"
        ),
    ),
    "javascript": SnippetResponse(
        language="javascript",
        title="Average of an array",
        description=(
            "Returns a strange result for normal arrays and a worse one for "
            "an edge case. Two bugs hide in the loop."
        ),
        code=(
            "function average(nums) {\n"
            "  let total = 0;\n"
            "  for (let i = 1; i <= nums.length; i++) {\n"
            "    total += nums[i];\n"
            "  }\n"
            "  return total / nums.length;\n"
            "}\n"
            "\n"
            "console.log(average([2, 4, 6]));\n"
            "console.log(average([]));"
        ),
    ),
}
