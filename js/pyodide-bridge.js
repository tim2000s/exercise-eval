// Loading and calling the Python analysis engine.
//
// Pyodide is fetched from the CDN rather than vendored, because the distribution is far too
// large for a repository. It is loaded lazily: the page parses files and shows the sessions it
// found without it, and only downloads the runtime when an analysis is actually requested. That
// keeps the first view fast for someone who wants to check their file was read correctly before
// committing to a large download.
//
// The engine takes plain objects and returns plain objects. Nothing else crosses the boundary,
// because converting a proxy per field is slow and because a JavaScript object that reaches
// Python by reference is a lifetime problem nobody needs.

const PYODIDE_VERSION = '314.0.6';
const PYODIDE_URL = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

/** The Python package, in dependency order. Fetched from this site, not from PyPI. */
const MODULES = [
  '__init__.py',
  'units.py',
  'sources.py',
  'guidelines.py',
  'intensity.py',
  'insulin.py',
  'nightscout_profile.py',
  'evaluate.py',
  'recommend.py',
  'report.py',
];

let pyodidePromise = null;

/**
 * Load Pyodide and install the analysis package into its filesystem.
 *
 * @param {(stage: string, detail: string) => void} onProgress
 */
export function loadEngine(onProgress = () => {}) {
  if (pyodidePromise) return pyodidePromise;

  pyodidePromise = (async () => {
    onProgress('runtime', `Downloading the Python runtime (Pyodide ${PYODIDE_VERSION}).`);
    const { loadPyodide } = await import(`${PYODIDE_URL}pyodide.mjs`);
    const pyodide = await loadPyodide({ indexURL: PYODIDE_URL });

    onProgress('package', 'Installing the analysis engine.');
    // The package is served as ordinary files alongside this script, so it is readable and
    // checkable by anyone looking at the site, which is the point of putting the science in
    // Python rather than burying it in the bundle.
    pyodide.FS.mkdirTree('/lib/python3/xeval');
    const sources = await Promise.all(
      MODULES.map(async (name) => {
        const res = await fetch(new URL(`../python/xeval/${name}`, import.meta.url));
        if (!res.ok) throw new Error(`Could not load python/xeval/${name}: ${res.status}`);
        return [name, await res.text()];
      }),
    );
    for (const [name, text] of sources) {
      pyodide.FS.writeFile(`/lib/python3/xeval/${name}`, text, { encoding: 'utf8' });
    }
    pyodide.runPython(`
import sys
if "/lib/python3" not in sys.path:
    sys.path.insert(0, "/lib/python3")
import xeval.report
`);
    onProgress('ready', 'The analysis engine is ready.');
    return pyodide;
  })();

  pyodidePromise.catch(() => { pyodidePromise = null; });  // allow a retry after a failure
  return pyodidePromise;
}

/**
 * Run the analysis.
 *
 * @param {object} payload sessions, entries, treatments, profile and settings
 * @returns {Promise<object>} the report
 */
export async function analyse(payload, onProgress = () => {}) {
  const pyodide = await loadEngine(onProgress);
  onProgress('analysing', `Evaluating ${payload.sessions.length} sessions.`);

  // JSON is used rather than pyodide.toPy because the payload is a few megabytes of plain
  // numbers, and the browser's JSON implementation is faster at that than a per-field
  // conversion through the proxy layer.
  pyodide.globals.set('__payload_json', JSON.stringify(payload));
  const resultJson = pyodide.runPython(`
import json
import xeval.report
json.dumps(xeval.report.analyse(json.loads(__payload_json)))
`);
  pyodide.globals.delete('__payload_json');
  return JSON.parse(resultJson);
}

/** Whether the engine has already been downloaded, so the page can say what a click will cost. */
export function isLoaded() {
  return pyodidePromise !== null;
}

export const ENGINE_VERSION = PYODIDE_VERSION;
