/**
 * `/pyodide/pyodide.mjs` is a URL served out of `public/`, not a module on
 * disk, so TypeScript has nothing to resolve and reports TS2307 at the dynamic
 * import in `pyodide.worker.ts`. The bundler is already told to leave the
 * specifier alone (`webpackIgnore` / `turbopackIgnore`); this declares it so
 * the typechecker leaves it alone too.
 *
 * It has to be a wildcard pattern. An exact `declare module '/pyodide/…'` is
 * never consulted, because TypeScript reads a leading slash as a path to
 * resolve rather than as an ambient module name.
 *
 * Deliberately untyped: the import site casts the result to `PyodideModule`,
 * which is the shape the worker actually depends on. Typing it here as well
 * would mean maintaining two descriptions of the same object.
 */
declare module '*/pyodide.mjs';
