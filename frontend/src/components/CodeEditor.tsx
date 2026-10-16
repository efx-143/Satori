"use client";
// components/CodeEditor.tsx
// Monaco editor wrapper with Debug Dojo dark theme.
// Lazy-loaded to prevent SSR issues.

import { useRef } from "react";
import dynamic from "next/dynamic";
import type { editor } from "monaco-editor";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center bg-[#1e1e2e]">
      <span className="animate-pulse text-sm text-violet-400">
        Loading editor…
      </span>
    </div>
  ),
});

interface Props {
  value: string;
  onChange: (value: string) => void;
  language?: string;
  readOnly?: boolean;
}

const DOJO_THEME: editor.IStandaloneThemeData = {
  base: "vs-dark",
  inherit: true,
  rules: [
    { token: "comment",        foreground: "6272a4", fontStyle: "italic" },
    { token: "keyword",        foreground: "bd93f9" },
    { token: "string",         foreground: "f1fa8c" },
    { token: "number",         foreground: "bd93f9" },
    { token: "type",           foreground: "8be9fd" },
    { token: "function",       foreground: "50fa7b" },
    { token: "identifier",     foreground: "f8f8f2" },
  ],
  colors: {
    "editor.background":           "#13131f",
    "editor.foreground":           "#f8f8f2",
    "editorLineNumber.foreground": "#44475a",
    "editorLineNumber.activeForeground": "#bd93f9",
    "editor.lineHighlightBackground": "#1e1e2e",
    "editorIndentGuide.background": "#44475a",
    "editor.selectionBackground":  "#44475a",
    "editorCursor.foreground":     "#bd93f9",
    "scrollbarSlider.background":  "#44475a80",
  },
};

export default function CodeEditor({
  value,
  onChange,
  language = "python",
  readOnly = false,
}: Props) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);

  function handleMount(
    ed: editor.IStandaloneCodeEditor,
    monaco: typeof import("monaco-editor")
  ) {
    editorRef.current = ed;
    monaco.editor.defineTheme("dojo-dark", DOJO_THEME);
    monaco.editor.setTheme("dojo-dark");
  }

  return (
    <MonacoEditor
      height="100%"
      language={language}
      value={value}
      theme="dojo-dark"
      onChange={(v) => onChange(v ?? "")}
      onMount={handleMount}
      options={{
        fontSize: 14,
        fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
        fontLigatures: true,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        lineNumbers: "on",
        renderLineHighlight: "line",
        padding: { top: 16, bottom: 16 },
        readOnly,
        automaticLayout: true,
        tabSize: 4,
        wordWrap: "on",
      }}
    />
  );
}
