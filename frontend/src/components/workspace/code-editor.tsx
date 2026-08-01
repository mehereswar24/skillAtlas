'use client';

/**
 * CodeMirror 6, loaded only in the browser.
 *
 * `next/dynamic` with `ssr: false` is not optional here — CodeMirror reaches
 * for `document` while building its extensions, so rendering it on the server
 * throws before the page ever reaches the client.
 */

import { useMemo } from 'react';
import dynamic from 'next/dynamic';
import { css } from '@codemirror/lang-css';
import { html } from '@codemirror/lang-html';
import { javascript } from '@codemirror/lang-javascript';
import { python } from '@codemirror/lang-python';
import { sql } from '@codemirror/lang-sql';
import { oneDark } from '@codemirror/theme-one-dark';
import type { Extension } from '@codemirror/state';

import { languageForPath } from './runtime-protocol';
import { Skeleton } from '@/components/ui/skeleton';

const CodeMirror = dynamic(() => import('@uiw/react-codemirror'), {
  ssr: false,
  loading: () => <Skeleton className="h-full min-h-80 w-full rounded-none" />,
});

const LANGUAGES: Record<string, () => Extension> = {
  python,
  javascript,
  html,
  css,
  sql,
};

export function CodeEditor({
  path,
  value,
  onChange,
  readOnly = false,
  dark,
}: {
  path: string;
  value: string;
  onChange: (next: string) => void;
  readOnly?: boolean;
  dark: boolean;
}) {
  const extensions = useMemo(() => {
    const factory = LANGUAGES[languageForPath(path)];
    return factory ? [factory()] : [];
  }, [path]);

  return (
    <CodeMirror
      value={value}
      onChange={onChange}
      extensions={extensions}
      theme={dark ? oneDark : 'light'}
      editable={!readOnly}
      readOnly={readOnly}
      height="100%"
      basicSetup={{
        lineNumbers: true,
        highlightActiveLine: !readOnly,
        foldGutter: false,
        autocompletion: false,
        // The learner is writing code, not prose: tabs should indent.
        indentOnInput: true,
      }}
      className="h-full text-sm"
      aria-label={`${path} editor`}
    />
  );
}
