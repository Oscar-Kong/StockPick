"use client";

import { useState } from "react";

/** Display-only nested list (not an interactive ARIA tree — expand uses buttons). */
function AstNodeInner({ node, depth }: { node: Record<string, unknown>; depth: number }) {
  const kind = String(node.kind ?? node.type ?? node.op ?? "node");
  const label = String(node.field ?? node.name ?? node.value ?? kind);
  const children = (node.children ?? node.args ?? node.operands) as unknown[] | undefined;
  const [open, setOpen] = useState(depth < 2);

  return (
    <li className="text-sm">
      <button
        type="button"
        className="flex items-center gap-1 text-left hover:underline focus:outline-none focus:ring-2 focus:ring-zinc-400"
        onClick={() => children?.length && setOpen((v) => !v)}
        aria-expanded={children?.length ? open : undefined}
        aria-label={`${kind}: ${label}`}
      >
        {children?.length ? (open ? "▾" : "▸") : "•"} <span className="font-medium">{kind}</span>
        <span className="font-mono text-xs text-zinc-500">{label !== kind ? label : ""}</span>
      </button>
      {open && children?.length ? (
        <ul className="ml-4 border-l border-zinc-200 pl-2 dark:border-zinc-700">
          {children.map((child, i) => (
            <AstNode key={i} node={child} depth={depth + 1} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function AstNode({ node, depth = 0 }: { node: unknown; depth?: number }) {
  if (node == null) return null;
  if (typeof node !== "object") {
    return (
      <li className="font-mono text-xs text-zinc-600 dark:text-zinc-400">{String(node)}</li>
    );
  }
  return <AstNodeInner node={node as Record<string, unknown>} depth={depth} />;
}

export function AstTreeView({ ast, label = "Formula AST" }: { ast: unknown; label?: string }) {
  if (!ast) {
    return <p className="text-sm text-zinc-500">AST not available.</p>;
  }

  return (
    <div className="rounded border border-zinc-200 p-3 dark:border-zinc-700">
      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</p>
      <ul aria-label={label} className="space-y-1">
        <AstNode node={ast} />
      </ul>
    </div>
  );
}
