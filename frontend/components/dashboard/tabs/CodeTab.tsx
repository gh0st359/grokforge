"use client";

import { useEffect, useState } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import FileTree from "@/components/code/FileTree";
import CodeBlock from "@/components/code/CodeBlock";
import type { AnyEvent } from "@/lib/events";
import { fileMapFromEvents } from "@/lib/useJobStream";

interface Props { events: AnyEvent[] }

export default function CodeTab({ events }: Props) {
  const files = fileMapFromEvents(events);
  const paths = Object.keys(files);
  const [selected, setSelected] = useState<string | null>(null);

  // Auto-select main.py / first file when files first appear.
  useEffect(() => {
    if (selected && files[selected]) return;
    if (paths.length === 0) return;
    const fav = paths.find((p) => p.endsWith("main.py")) ?? paths[0];
    setSelected(fav);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paths.length, selected]);

  const cur = selected ? files[selected] : null;

  return (
    <div className="grid grid-cols-12 gap-3 h-[60vh]">
      <Card className="col-span-4 lg:col-span-3 flex flex-col">
        <div className="px-3 py-2 border-b border-border text-[10px] uppercase tracking-wider text-muted-foreground flex items-center justify-between">
          <span>files</span>
          <Badge variant="outline" className="text-[10px]">{paths.length}</Badge>
        </div>
        <ScrollArea className="flex-1">
          <div className="p-1.5">
            <FileTree files={files} selected={selected} onSelect={setSelected} />
          </div>
        </ScrollArea>
      </Card>
      <Card className="col-span-8 lg:col-span-9 flex flex-col">
        {cur ? (
          <>
            <div className="px-3 py-2 border-b border-border flex items-center gap-2">
              <span className="font-mono text-xs">{selected}</span>
              <Badge variant="outline" className="text-[10px]">{cur.language}</Badge>
              <span className="ml-auto text-[10px] text-muted-foreground">{cur.lines} lines</span>
            </div>
            <div className="flex-1 overflow-hidden p-2">
              <CodeBlock code={cur.content} language={cur.language} className="h-full" />
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-xs text-muted-foreground">
            files will appear here as the Coder writes them
          </div>
        )}
      </Card>
    </div>
  );
}
