"use client";

import { useMemo } from "react";
import { File, Folder, FolderOpen } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  files: Record<string, { content: string; language: string; lines: number }>;
  selected: string | null;
  onSelect: (path: string) => void;
}

interface Node {
  name: string;
  fullPath: string;
  isFile: boolean;
  children: Node[];
  lines?: number;
}

function buildTree(files: Record<string, { lines: number }>): Node {
  const root: Node = { name: "", fullPath: "", isFile: false, children: [] };
  const paths = Object.keys(files).sort();
  for (const p of paths) {
    const parts = p.split("/");
    let cur = root;
    let acc = "";
    for (let i = 0; i < parts.length; i++) {
      const name = parts[i];
      acc = acc ? `${acc}/${name}` : name;
      const isFile = i === parts.length - 1;
      let next = cur.children.find((c) => c.name === name);
      if (!next) {
        next = { name, fullPath: acc, isFile, children: [], lines: isFile ? files[p].lines : undefined };
        cur.children.push(next);
      }
      cur = next;
    }
  }
  return root;
}

function NodeView({
  node, depth, selected, onSelect,
}: { node: Node; depth: number; selected: string | null; onSelect: (p: string) => void }) {
  if (node.isFile) {
    const isSel = selected === node.fullPath;
    return (
      <button
        onClick={() => onSelect(node.fullPath)}
        className={cn(
          "flex w-full items-center gap-1.5 py-1 px-2 rounded text-xs hover:bg-secondary/50 transition-colors",
          isSel && "bg-primary/10 text-primary",
        )}
        style={{ paddingLeft: 8 + depth * 12 }}
      >
        <File className="h-3 w-3 shrink-0" />
        <span className="truncate font-mono">{node.name}</span>
        {typeof node.lines === "number" && (
          <span className="ml-auto text-[10px] text-muted-foreground tabular-nums">
            {node.lines}L
          </span>
        )}
      </button>
    );
  }
  return (
    <div>
      {node.name && (
        <div className="flex items-center gap-1.5 py-1 px-2 text-xs text-muted-foreground"
             style={{ paddingLeft: 8 + (depth - 1) * 12 }}>
          <FolderOpen className="h-3 w-3 shrink-0" />
          <span className="font-mono">{node.name}</span>
        </div>
      )}
      {node.children.map((c) => (
        <NodeView key={c.fullPath} node={c} depth={depth + (node.name ? 1 : 0)}
                  selected={selected} onSelect={onSelect} />
      ))}
    </div>
  );
}

export default function FileTree({ files, selected, onSelect }: Props) {
  const tree = useMemo(() => buildTree(files), [files]);
  if (Object.keys(files).length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-32 text-xs text-muted-foreground">
        <Folder className="h-8 w-8 mb-2 opacity-30" />
        no files yet — the Coder will fill this in
      </div>
    );
  }
  return <NodeView node={tree} depth={0} selected={selected} onSelect={onSelect} />;
}
