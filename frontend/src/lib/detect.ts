/* Client-side language guess for highlighting and display only.
   The backend re-detects authoritatively on session creation.
   Mirrors backend/app/services/detect.py (kept intentionally small). */

export type Lang =
  | "python"
  | "javascript"
  | "typescript"
  | "java"
  | "cpp"
  | "csharp"
  | "go"
  | "sql";

export const LANGUAGES: { value: Lang; label: string }[] = [
  { value: "python", label: "Python" },
  { value: "javascript", label: "JavaScript" },
  { value: "typescript", label: "TypeScript" },
  { value: "java", label: "Java" },
  { value: "cpp", label: "C++" },
  { value: "csharp", label: "C#" },
  { value: "go", label: "Go" },
  { value: "sql", label: "SQL" },
];

const RULES: { lang: Lang; patterns: RegExp[] }[] = [
  {
    lang: "python",
    patterns: [/^\s*def\s+\w+\s*\(.*\)\s*:/m, /^\s*(import|from)\s+\w+/m, /\bprint\s*\(/, /\bNone\b/],
  },
  {
    lang: "javascript",
    patterns: [/\bfunction\s+\w*\s*\(/, /=>/, /\bconsole\.(log|error)/, /^\s*(let|const|var)\s+\w+/m, /===/],
  },
  {
    lang: "typescript",
    patterns: [/:\s*(number|string|boolean|void|any)\b/, /\binterface\s+\w+/, /\btype\s+\w+\s*=/],
  },
  { lang: "java", patterns: [/\bpublic\s+class\s+\w+/, /\bSystem\.out\.print/, /\bpublic\s+static\s+void\s+main/] },
  { lang: "cpp", patterns: [/#include\s*</, /\bstd::/, /\bcout\s*<</, /\bint\s+main\s*\(/] },
  { lang: "csharp", patterns: [/\busing\s+System\s*;/, /\bConsole\.(Write|Read)/, /\bnamespace\s+\w+/] },
  { lang: "go", patterns: [/^package\s+\w+/m, /\bfunc\s+main\s*\(/, /\bfmt\./, /:=/] },
  {
    lang: "sql",
    patterns: [/^\s*SELECT\s+/im, /\bFROM\s+\w+/i, /\bWHERE\s+/i, /\bGROUP\s+BY\s+/i],
  },
];

export function guessLanguage(code: string): Lang | null {
  if (!code || !code.trim()) return null;
  const scores = RULES.map(({ lang, patterns }) => ({
    lang,
    score: patterns.reduce((n, p) => n + (p.test(code) ? 1 : 0), 0),
  }));
  const ts = scores.find((s) => s.lang === "typescript")!;
  const js = scores.find((s) => s.lang === "javascript")!;
  if (ts.score > 0 && ts.score >= js.score) return "typescript";
  const ranked = [...scores].sort((a, b) => b.score - a.score);
  if (ranked[0].score === 0 || ranked[0].score - ranked[1].score < 1) return null;
  return ranked[0].lang;
}
