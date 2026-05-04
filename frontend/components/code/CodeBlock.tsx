"use client";

import { Highlight, themes } from "prism-react-renderer";
import { cn } from "@/lib/utils";

interface Props {
  code: string;
  language?: string;
  showLineNumbers?: boolean;
  className?: string;
  maxHeight?: string;
}

export default function CodeBlock({
  code,
  language = "python",
  showLineNumbers = true,
  className,
  maxHeight,
}: Props) {
  const lang = language === "dockerfile" ? "docker" : language === "text" ? "bash" : language;
  return (
    <div
      className={cn(
        "rounded-md border border-border bg-[#0a0d12] overflow-auto font-mono text-xs",
        className,
      )}
      style={maxHeight ? { maxHeight } : undefined}
    >
      <Highlight code={code.trimEnd()} language={lang} theme={themes.vsDark}>
        {({ className: hl, style, tokens, getLineProps, getTokenProps }) => (
          <pre className={cn("p-3 leading-relaxed", hl)} style={{ ...style, background: "transparent" }}>
            {tokens.map((line, i) => {
              const { key: lineKey, ...lineProps } = getLineProps({ line });
              return (
                <div key={i} {...lineProps} className="flex">
                  {showLineNumbers && (
                    <span className="select-none text-muted-foreground/40 w-7 shrink-0 text-right pr-3">
                      {i + 1}
                    </span>
                  )}
                  <span className="whitespace-pre-wrap break-all">
                    {line.map((token, j) => {
                      const { key: tokKey, ...tokProps } = getTokenProps({ token });
                      return <span key={j} {...tokProps} />;
                    })}
                  </span>
                </div>
              );
            })}
          </pre>
        )}
      </Highlight>
    </div>
  );
}
