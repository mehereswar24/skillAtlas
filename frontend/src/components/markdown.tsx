import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { cn } from '@/lib/utils';

/**
 * Renders authored concept content.
 *
 * Styles are applied per element rather than via a typography plugin so the
 * output matches the rest of the design tokens, and `react-markdown` does not
 * render raw HTML by default — authored content cannot inject markup.
 */
export function Markdown({ children, className }: { children: string; className?: string }) {
  return (
    <div className={cn('space-y-4 leading-relaxed', className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h2 className="mt-8 text-2xl font-bold tracking-tight">{children}</h2>
          ),
          h2: ({ children }) => (
            <h3 className="mt-8 text-xl font-bold tracking-tight">{children}</h3>
          ),
          h3: ({ children }) => <h4 className="mt-6 text-lg font-semibold">{children}</h4>,
          p: ({ children }) => <p className="text-[15px] text-foreground/90">{children}</p>,
          ul: ({ children }) => (
            <ul className="ml-5 list-disc space-y-1.5 text-[15px] text-foreground/90">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="ml-5 list-decimal space-y-1.5 text-[15px] text-foreground/90">
              {children}
            </ol>
          ),
          strong: ({ children }) => (
            <strong className="font-semibold text-foreground">{children}</strong>
          ),
          code: ({ children }) => (
            <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[0.85em]">
              {children}
            </code>
          ),
          pre: ({ children }) => (
            <pre className="overflow-x-auto rounded-lg border bg-muted/60 p-4 text-sm">
              {children}
            </pre>
          ),
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer noopener"
              className="text-primary underline underline-offset-4 hover:no-underline"
            >
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-primary/40 pl-4 text-muted-foreground italic">
              {children}
            </blockquote>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
