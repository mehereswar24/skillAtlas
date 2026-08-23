'use client';

import { useEffect, useState } from 'react';
import { Monitor, Moon, Sun } from 'lucide-react';

import { cn } from '@/lib/utils';

type Theme = 'light' | 'dark' | 'system';

const STORAGE_KEY = 'skillatlas-theme';

/**
 * Applies the stored theme before first paint.
 *
 * This runs as a blocking inline script in <head>. Doing it in an effect
 * instead would render the light theme first and then swap — the flash of
 * wrong theme that every dark-mode implementation is judged by.
 *
 * `nonce` is required by the CSP that `src/proxy.ts` sets. Next nonces the
 * scripts it emits itself, but this one is hand-written, so the root layout
 * reads `x-nonce` off the request and passes it down. Without it the theme
 * simply never applies and every visitor gets the light theme.
 */
export function ThemeScript({ nonce }: { nonce?: string }) {
  const script = `
(function () {
  try {
    var stored = localStorage.getItem('${STORAGE_KEY}');
    var dark = stored === 'dark' ||
      ((!stored || stored === 'system') &&
        window.matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.classList.toggle('dark', dark);
    document.documentElement.style.colorScheme = dark ? 'dark' : 'light';
  } catch (e) {}
})();`.trim();

  // suppressHydrationWarning: browsers deliberately hide the `nonce` content
  // attribute from the DOM once the document is parsed, so that an injected
  // CSS selector cannot read it back out. React therefore sees `nonce=""` on
  // the client against the real value in the server HTML and reports a
  // mismatch it cannot patch. The script has already run by then; the warning
  // is about an attribute nobody reads.
  return (
    <script
      nonce={nonce}
      suppressHydrationWarning
      dangerouslySetInnerHTML={{ __html: script }}
    />
  );
}

function apply(theme: Theme) {
  const dark =
    theme === 'dark' ||
    (theme === 'system' &&
      window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.classList.toggle('dark', dark);
  document.documentElement.style.colorScheme = dark ? 'dark' : 'light';
}

const OPTIONS: { value: Theme; label: string; icon: typeof Sun }[] = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'System', icon: Monitor },
];

export function ThemeToggle({ className }: { className?: string }) {
  const [theme, setTheme] = useState<Theme>('system');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setTheme((localStorage.getItem(STORAGE_KEY) as Theme | null) ?? 'system');
  }, []);

  // Follow the OS while the preference is "system".
  useEffect(() => {
    if (theme !== 'system') return;
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => apply('system');
    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  }, [theme]);

  function choose(next: Theme) {
    setTheme(next);
    localStorage.setItem(STORAGE_KEY, next);
    apply(next);
  }

  return (
    <div
      role="radiogroup"
      aria-label="Colour theme"
      className={cn(
        'inline-flex items-center gap-0.5 rounded-lg border bg-card p-0.5',
        className,
      )}
    >
      {OPTIONS.map(({ value, label, icon: Icon }) => (
        <button
          key={value}
          type="button"
          role="radio"
          // Before hydration we do not know the stored value; showing none
          // selected is better than briefly showing the wrong one.
          aria-checked={mounted && theme === value}
          aria-label={label}
          title={label}
          onClick={() => choose(value)}
          className={cn(
            'rounded-md p-1.5 transition-colors',
            mounted && theme === value
              ? 'bg-secondary text-foreground'
              : 'text-muted-foreground hover:text-foreground',
          )}
        >
          <Icon className="h-4 w-4" />
        </button>
      ))}
    </div>
  );
}
