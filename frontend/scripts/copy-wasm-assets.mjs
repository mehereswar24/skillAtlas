/**
 * Copy the Pyodide and sql.js runtimes into `public/` so the workspace runs
 * offline.
 *
 * The alternative is loading them from a CDN, which would make "run this
 * project" the one part of SkillAtlas that needs the internet — an odd
 * exception in a product whose AI tutor already runs locally. Copying also
 * pins the version to whatever `package.json` resolved, so a CDN publishing a
 * new build cannot change what a learner's code runs against.
 *
 * Runs on `npm install` (postinstall) and can be re-run by hand:
 *
 *     node scripts/copy-wasm-assets.mjs
 */

import { copyFile, mkdir, stat } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));

/** Only what the runtime actually loads — not the 80MB of optional wheels. */
const ASSETS = [
  // The UMD build, not the ESM one: workers load it with importScripts, which
  // only exists in a classic worker. See pyodide.worker.ts.
  { from: 'pyodide/pyodide.js', to: 'pyodide/pyodide.js' },
  { from: 'pyodide/pyodide.mjs', to: 'pyodide/pyodide.mjs' },
  { from: 'pyodide/pyodide.asm.mjs', to: 'pyodide/pyodide.asm.mjs' },
  { from: 'pyodide/pyodide.asm.wasm', to: 'pyodide/pyodide.asm.wasm' },
  { from: 'pyodide/python_stdlib.zip', to: 'pyodide/python_stdlib.zip' },
  { from: 'pyodide/pyodide-lock.json', to: 'pyodide/pyodide-lock.json' },
  { from: 'sql.js/dist/sql-wasm.js', to: 'sqljs/sql-wasm.js' },
  { from: 'sql.js/dist/sql-wasm.wasm', to: 'sqljs/sql-wasm.wasm' },
];

// Read straight out of node_modules rather than through `require.resolve`:
// both pyodide and sql.js publish an `exports` map that refuses deep paths,
// including `./package.json`, so there is nothing to resolve against.
const resolvePackageFile = (specifier) =>
  join(ROOT, 'node_modules', ...specifier.split('/'));

let copied = 0;
let missing = [];

for (const asset of ASSETS) {
  const source = resolvePackageFile(asset.from);
  const target = join(ROOT, 'public', asset.to);

  try {
    await stat(source);
  } catch {
    missing.push(asset.from);
    continue;
  }

  await mkdir(dirname(target), { recursive: true });
  await copyFile(source, target);
  copied += 1;
}

if (missing.length) {
  console.error(
    `copy-wasm-assets: ${missing.length} file(s) not found in node_modules:\n` +
      missing.map((m) => `  - ${m}`).join('\n') +
      '\nThe project workspace will not be able to run code. Try `npm install`.',
  );
  process.exit(1);
}

console.log(`copy-wasm-assets: copied ${copied} runtime files into public/.`);
