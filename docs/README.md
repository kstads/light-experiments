# Public report

Static GitHub Pages report. Publish from `main` → `/docs`. No build dependencies, analytics, remote fonts, Home Assistant access, or credentials.

`data/` contains only allowlisted numeric aggregate fields and quality flags from the matched fast-protocol HC and SD curves. Measurement values are preserved without normalization to rated specifications. Relative output divides each module's illuminance by its own measured ascending full-output illuminance. Neither source histories nor household state snapshots are deployed as site assets.

Serve this folder with any static HTTP server for local preview. Opening `index.html` directly from the filesystem may block JSON fetches.
