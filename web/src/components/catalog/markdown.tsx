import ReactMarkdown, { type Components } from "react-markdown";

import { safeHref } from "@/lib/markdown";

const components: Components = {
  h1: (props) => <h2 className="mt-4 mb-2 text-base font-semibold first:mt-0" {...props} />,
  h2: (props) => <h3 className="mt-4 mb-1.5 text-sm font-semibold first:mt-0" {...props} />,
  h3: (props) => <h4 className="mt-3 mb-1 text-sm font-medium first:mt-0" {...props} />,
  p: (props) => <p className="my-2 text-sm leading-relaxed" {...props} />,
  ul: (props) => <ul className="my-2 list-disc pl-5 text-sm" {...props} />,
  ol: (props) => <ol className="my-2 list-decimal pl-5 text-sm" {...props} />,
  li: (props) => <li className="my-0.5 leading-relaxed" {...props} />,
  code: (props) => <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]" {...props} />,
  pre: (props) => <pre className="my-2 overflow-x-auto rounded-lg bg-muted p-3 font-mono text-xs" {...props} />,
  a: ({ href, ...props }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="underline underline-offset-2 hover:text-foreground"
      {...props}
    />
  ),
  img: () => null,
};

// Notes come from a public repo: no raw HTML, no images, and only plain links.
export function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown skipHtml urlTransform={(url) => safeHref(url) ?? ""} components={components}>
      {children}
    </ReactMarkdown>
  );
}
