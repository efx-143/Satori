"use client";
// components/CodeEditor.tsx
// Monaco editor wrapper with MXESA [26] Industrial Dark theme.
// Lazy-loaded to prevent SSR issues.

import { useRef } from "react";
import dynamic from "next/dynamic";
import type { editor } from "monaco-editor";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center bg-[#141414]">
      <div className="flex items-center gap-2 font-mono text-xs text-[#DE6557]">
        <span className="inline-block h-2 w-2 bg-[#DE6557] animate-ping" />
        <span>INITIALIZING DOJO EDITOR…</span>
      </div>
    </div>
  ),
});

interface Props {
  value: string;
  onChange: (value: string) => void;
  language?: string;
  readOnly?: boolean;
}

const MXESA_THEME: editor.IStandaloneThemeData = {
  base: "vs-dark",
  inherit: true,
  rules: [
    { token: "comment", foreground: "757367", fontStyle: "italic" },
    { token: "keyword", foreground: "DE6557", fontStyle: "bold" },
    { token: "string", foreground: "E5A83B" },
    { token: "number", foreground: "DE6557" },
    { token: "type", foreground: "9BBBDD", fontStyle: "bold" },
    { token: "function", foreground: "FFFFFF", fontStyle: "bold" },
    { token: "identifier", foreground: "F0EFEA" },
    { token: "operator", foreground: "9BBBDD" },
  ],
  colors: {
    "editor.background": "#141414",
    "editor.foreground": "#F0EFEA",
    "editorLineNumber.foreground": "#42403B",
    "editorLineNumber.activeForeground": "#DE6557",
    "editor.lineHighlightBackground": "#1B1B1B",
    "editorIndentGuide.background": "#292825",
    "editor.selectionBackground": "#3D2B29",
    "editorCursor.foreground": "#DE6557",
    "scrollbarSlider.background": "#DE655740",
    "scrollbarSlider.hoverBackground": "#DE655780",
    "scrollbarSlider.activeBackground": "#DE6557",
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
    monaco.editor.defineTheme("mxesa-dark", MXESA_THEME);
    monaco.editor.setTheme("mxesa-dark");
  }

  return (
    <div className="h-full w-full bg-[#141414]">
      <MonacoEditor
        height="100%"
        language={language}
        value={value}
        theme="mxesa-dark"
        onChange={(v) => onChange(v ?? "")}
        onMount={handleMount}
        options={{
          fontSize: 14,
          fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace",
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
    </div>
  );
}
