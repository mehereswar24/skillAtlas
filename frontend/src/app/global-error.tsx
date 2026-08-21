'use client';

/**
 * Last-resort boundary: catches errors thrown by the root layout itself, which
 * `app/error.tsx` cannot, because that boundary lives *inside* the layout.
 *
 * It has to render its own `<html>`/`<body>`, and it cannot rely on the app's
 * fonts or theme class being applied, so the styling here is deliberately
 * inline and self-contained.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body
        style={{
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '1rem',
          padding: '2rem',
          textAlign: 'center',
          fontFamily: 'system-ui, sans-serif',
          background: '#fafafa',
          color: '#141414',
        }}
      >
        <h1 style={{ fontSize: '1.5rem', fontWeight: 600, margin: 0 }}>
          SkillAtlas could not start this page
        </h1>
        <p style={{ maxWidth: '32rem', fontSize: '0.875rem', opacity: 0.7, margin: 0 }}>
          Something failed before the application shell could render. Reloading usually
          clears it.
        </p>
        {error.digest && (
          <p style={{ fontFamily: 'monospace', fontSize: '0.75rem', opacity: 0.6 }}>
            ref {error.digest}
          </p>
        )}
        <button
          type="button"
          onClick={reset}
          style={{
            border: '1px solid currentColor',
            borderRadius: '0.375rem',
            padding: '0.5rem 1rem',
            fontSize: '0.875rem',
            background: 'transparent',
            color: 'inherit',
            cursor: 'pointer',
          }}
        >
          Reload
        </button>
      </body>
    </html>
  );
}
