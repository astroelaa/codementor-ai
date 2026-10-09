import { Suspense, lazy, useMemo } from "react";
import { javascript } from "@codemirror/lang-javascript";
import { python } from "@codemirror/lang-python";
import { useTheme } from "../lib/theme";

const CodeMirror = lazy(() => import("@uiw/react-codemirror"));

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
  const extensions = useMemo(
    () => [language === "javascript" ? javascript() : python()],
    [language],
  );
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
