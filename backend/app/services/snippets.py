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
    "typescript": SnippetResponse(
        language="typescript",
        title="Typed average",
        description=(
            "The types look right, but one call still returns NaN. "
            "Types do not catch logic bugs."
        ),
        code=(
            "function average(nums: number[]): number {\n"
            "  let total: number = 0;\n"
            "  for (let i: number = 1; i <= nums.length; i++) {\n"
            "    total += nums[i];\n"
            "  }\n"
            "  return total / nums.length;\n"
            "}\n"
            "\n"
            "console.log(average([2, 4, 6]));\n"
            "console.log(average([]));"
        ),
    ),
    "java": SnippetResponse(
        language="java",
        title="Average of an array",
        description=(
            "Compiles cleanly, yet one input crashes and the rest look "
            "rounded down. Two classic Java traps."
        ),
        code=(
            "public class Stats {\n"
            "    public static double average(int[] nums) {\n"
            "        int total = 0;\n"
            "        for (int n : nums) {\n"
            "            total += n;\n"
            "        }\n"
            "        return total / nums.length;\n"
            "    }\n"
            "\n"
            "    public static void main(String[] args) {\n"
            '        System.out.println(average(new int[]{2, 4, 5}));\n'
            '        System.out.println(average(new int[]{}));\n'
            "    }\n"
            "}"
        ),
    ),
    "cpp": SnippetResponse(
        language="cpp",
        title="Average of an array",
        description=(
            "Runs, but the answer is wrong — and one input reads memory it "
            "should not touch."
        ),
        code=(
            "#include <iostream>\n"
            "\n"
            "double average(int arr[], int n) {\n"
            "    int total = 0;\n"
            "    for (int i = 0; i <= n; i++) {\n"
            "        total += arr[i];\n"
            "    }\n"
            "    return total / n;\n"
            "}\n"
            "\n"
            "int main() {\n"
            "    int a[] = {2, 4, 6};\n"
            "    std::cout << average(a, 3) << std::endl;\n"
            "    return 0;\n"
            "}"
        ),
    ),
    "csharp": SnippetResponse(
        language="csharp",
        title="Average of an array",
        description=(
            "No compiler complaints, yet whole-number results keep coming "
            "back truncated."
        ),
        code=(
            "using System;\n"
            "\n"
            "class Stats {\n"
            "    static double Average(int[] nums) {\n"
            "        int total = 0;\n"
            "        foreach (var n in nums) {\n"
            "            total += n;\n"
            "        }\n"
            "        return total / nums.Length;\n"
            "    }\n"
            "\n"
            "    static void Main() {\n"
            "        Console.WriteLine(Average(new int[]{2, 4, 5}));\n"
            "    }\n"
            "}"
        ),
    ),
    "go": SnippetResponse(
        language="go",
        title="Average of a slice",
        description=(
            "Panics on every input. The loop and the divisor disagree about "
            "where the slice ends."
        ),
        code=(
            "package main\n"
            "\n"
            'import "fmt"\n'
            "\n"
            "func average(nums []float64) float64 {\n"
            "    total := 0.0\n"
            "    for i := 1; i <= len(nums); i++ {\n"
            "        total += nums[i]\n"
            "    }\n"
            "    return total / float64(len(nums))\n"
            "}\n"
            "\n"
            "func main() {\n"
            "    fmt.Println(average([]float64{2, 4, 6}))\n"
            "}"
        ),
    ),
    "sql": SnippetResponse(
        language="sql",
        title="Average bonus by department",
        description=(
            "Runs fine, but one department reports NULL instead of 0 — and "
            "nobody noticed for months."
        ),
        code=(
            "SELECT department, AVG(bonus) AS avg_bonus\n"
            "FROM employees\n"
            "GROUP BY department;\n"
            "\n"
            "-- A department where nobody earned a bonus shows NULL, not 0.\n"
            "-- Why does AVG skip those rows, and how would you show 0 instead?"
        ),
    ),
}
