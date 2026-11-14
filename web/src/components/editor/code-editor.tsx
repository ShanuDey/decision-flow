"use client";

import { autocompletion, type CompletionContext, completionKeymap } from "@codemirror/autocomplete";
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { bracketMatching } from "@codemirror/language";
import { type Extension, RangeSetBuilder } from "@codemirror/state";
import {
  Decoration,
  type DecorationSet,
  EditorView,
  keymap,
  lineNumbers,
  ViewPlugin,
  type ViewUpdate,
} from "@codemirror/view";
import { useEffect, useRef } from "react";

import { suggest } from "@/lib/graph/suggest";
import type { Graph } from "@/lib/graph/types";

const TOKENS: [RegExp, string][] = [
  [/^("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/, "cm-tok-string"],
  [/^\d+(?:\.\d+)?/, "cm-tok-number"],
  [/^(?:true|false|null|in)\b/, "cm-tok-keyword"],
  [/^(?:input|vars|nodes)\b/, "cm-tok-scope"],
  [/^(?:&&|\|\||==|!=|<=|>=|[<>!?:+\-*/%])/, "cm-tok-op"],
  [/^\{\{|^\}\}/, "cm-tok-op"],
];

// Re-tokenizes the whole text on each change; fine because expressions are capped at 2000 characters.
function mark(view: EditorView): DecorationSet {
  const builder = new RangeSetBuilder<Decoration>();
  const text = view.state.doc.toString();
  let i = 0;
  while (i < text.length) {
    const rest = text.slice(i);
    const hit = TOKENS.map(([re, cls]) => [re.exec(rest), cls] as const).find(([m]) => m);
    if (hit?.[0]) {
      builder.add(i, i + hit[0][0].length, Decoration.mark({ class: hit[1] }));
      i += hit[0][0].length;
    } else {
      i += /^[A-Za-z_]\w*/.exec(rest)?.[0].length ?? 1;
    }
  }
  return builder.finish();
}

const highlighter = ViewPlugin.fromClass(
  class {
    decorations: DecorationSet;
    constructor(view: EditorView) {
      this.decorations = mark(view);
    }
    update(update: ViewUpdate) {
      if (update.docChanged) this.decorations = mark(update.view);
    }
  },
  { decorations: (v) => v.decorations },
);

const theme = EditorView.theme({
  "&": { backgroundColor: "transparent", fontSize: "13px", height: "100%", color: "inherit" },
  "&.cm-focused": { outline: "none" },
  ".cm-scroller": { fontFamily: "var(--font-geist-mono), ui-monospace, Consolas, monospace", lineHeight: "1.7" },
  ".cm-gutters": { backgroundColor: "transparent", color: "var(--muted-foreground)", border: "none" },
  ".cm-content": { caretColor: "var(--foreground)" },
  "&.cm-focused .cm-cursor": { borderLeftColor: "var(--foreground)" },
  ".cm-tok-string": { color: "var(--syntax-string)" },
  ".cm-tok-number": { color: "var(--syntax-number)" },
  ".cm-tok-keyword": { color: "var(--syntax-keyword)" },
  ".cm-tok-scope": { color: "var(--syntax-scope)", fontWeight: "600" },
  ".cm-tok-op": { color: "var(--muted-foreground)" },
  ".cm-tooltip": {
    backgroundColor: "var(--popover)",
    color: "var(--popover-foreground)",
    border: "1px solid var(--border)",
    borderRadius: "8px",
  },
  ".cm-tooltip-autocomplete ul li[aria-selected]": {
    backgroundColor: "var(--accent)",
    color: "var(--accent-foreground)",
  },
});

interface Props {
  value: string;
  onChange: (value: string) => void;
  // Called on demand so completions always see the live graph.
  getGraph: () => Graph;
  nodeId: string;
  label: string;
  // Insert request from clicking the data tree.
  insertRequest?: { text: string; n: number } | null;
}

export function CodeEditor({ value, onChange, getGraph, nodeId, label, insertRequest }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView | null>(null);
  const change = useRef(onChange);
  const graph = useRef(getGraph);
  const id = useRef(nodeId);
  useEffect(() => {
    change.current = onChange;
    graph.current = getGraph;
    id.current = nodeId;
  });

  useEffect(() => {
    if (!host.current) return;
    const complete = (ctx: CompletionContext) => {
      const text = ctx.state.doc.toString();
      const { from, items } = suggest(graph.current(), id.current, text, ctx.pos);
      if (!items.length && !ctx.explicit) return null;
      return {
        from,
        filter: false,
        options: items.map((i) => ({ label: i.insert, displayLabel: i.label, detail: i.detail })),
      };
    };
    const extensions: Extension[] = [
      lineNumbers(),
      history(),
      bracketMatching(),
      highlighter,
      autocompletion({ override: [complete], activateOnTyping: true }),
      keymap.of([...completionKeymap, ...defaultKeymap, ...historyKeymap]),
      EditorView.lineWrapping,
      EditorView.contentAttributes.of({ "aria-label": label }),
      EditorView.updateListener.of((u) => {
        if (u.docChanged) change.current(u.state.doc.toString());
      }),
      theme,
    ];
    const v = new EditorView({ doc: value, extensions, parent: host.current });
    view.current = v;
    v.focus();
    return () => {
      v.destroy();
      view.current = null;
    };
    // Created once; later value changes sync below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const v = view.current;
    if (v && v.state.doc.toString() !== value) {
      v.dispatch({ changes: { from: 0, to: v.state.doc.length, insert: value } });
    }
  }, [value]);

  useEffect(() => {
    const v = view.current;
    if (!v || !insertRequest) return;
    const { from, to } = v.state.selection.main;
    v.dispatch({
      changes: { from, to, insert: insertRequest.text },
      selection: { anchor: from + insertRequest.text.length },
    });
    v.focus();
  }, [insertRequest]);

  return <div ref={host} data-testid="code-editor" className="h-full min-h-0 overflow-auto" />;
}
