import { Suspense, lazy, useMemo } from "react";
import { cpp } from "@codemirror/lang-cpp";
import { go } from "@codemirror/lang-go";
import { java } from "@codemirror/lang-java";
import { javascript } from "@codemirror/lang-javascript";
import { python } from "@codemirror/lang-python";
import { sql } from "@codemirror/lang-sql";
import { useTheme } from "../lib/theme";

const CodeMirror = lazy(() => import("@uiw/react-codemirror"));

function extensionFor(language: string) {
  switch (language) {
    case "javascript":
      return javascript();
    case "typescript":
      return javascript({ typescript: true });
    case "java":
      return java();
    case "cpp":
      return cpp();
    case "go":
      return go();
    case "sql":
      return sql();
    case "csharp":
      return java(); // no official C# grammar; Java is the closest highlight
    case "python":
    default:
      return python();
  }
}

export function CodeEditor({
  language,
  value,
  onChange,
  label,
}: {
  language: string;
  value: string;
  onChange: (v: string) => void;
  label: string;
}) {
  const { theme } = useTheme();
  const extensions = useMemo(() => [extensionFor(language)], [language]);
  return (
    <Suspense
      fallback={
        <div className="flex flex-col gap-2 p-4" aria-label="Loading editor">
          <div className="skeleton h-4 w-2/3" />
          <div className="skeleton h-4 w-11/12" />
          <div className="skeleton h-4 w-3/4" />
          <div className="skeleton h-4 w-5/6" />
        </div>
      }
    >
      <CodeMirror
        value={value}
        extensions={extensions}
        theme={theme}
        onChange={onChange}
        aria-label={label}
        basicSetup={{ lineNumbers: true, highlightActiveLine: false, foldGutter: false }}
        style={{ fontSize: 13.5 }}
      />
    </Suspense>
  );
}
