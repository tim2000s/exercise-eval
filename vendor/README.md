# Vendored libraries

Copied verbatim from npm at the versions pinned in `package.json`, so that the published site
has no build step and no runtime dependency on a package registry. Refresh them with
`npm install && npm run vendor`.

| File | Package | Version | Licence | Purpose |
|---|---|---|---|---|
| `sql-wasm.js`, `sql-wasm.wasm` | sql.js | 1.13.0 | MIT | Reads the SQLite database inside a Health Connect export. Chosen over wa-sqlite and the official sqlite-wasm because it opens a database straight from a `Uint8Array`, which is exactly what falls out of unzipping the single entry, with no OPFS or VFS setup. Its limitation is holding the whole database in the WASM heap, which makes it a poor fit above roughly 100 MB |
| `fflate.js` | fflate | 0.8.2 | MIT | Unzips the export. Chosen over JSZip at 11.8 KiB gzipped against 27.3 KiB, and because it can stream from `file.stream()`, which matters for the larger Strava and Garmin archives |

Pyodide is loaded from the jsDelivr CDN rather than vendored, because the distribution is over
100 MB once the scientific packages are counted and a repository is the wrong place for it. The
version is pinned in `js/pyodide-bridge.js`.
