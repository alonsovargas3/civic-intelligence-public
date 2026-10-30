# Public static build

This repository is a source-code snapshot with no approved analytical data package.
The committed availability file is control metadata only: all counts and data-dependent
tabs are unavailable. Story routes show an explicit unavailable page. Topic cards are
an inventory, not current findings. No backend, credentials, or private export is needed.

From the repository root:

```sh
cd frontend
npm ci
npm test
VITE_STATIC=1 npm run build
npm run preview
```

Check home, navigation, methodology/about, stories index, a story route, and dashboard.
The dashboard must show disabled crime/311 years, Ownership/Council/Methods/Equity,
and no map or counts. Address lookup remains unavailable. No `/v1` request is needed.
The default live build remains available for developers supplying their own backend;
it is not the public snapshot build.

To enable data later, separately approve fixture provenance, license, dates, geographic
coverage, schemas, time windows, denominators, and narrative claims. Use synthetic,
clearly labeled examples or separately approved public aggregates and geometry. Do not
copy private `frontend/public/data`, generated reports, screenshots, or raw records.
The private exporter and infrastructure are not part of this code-only sync.

Preserve LICENSE unchanged. Review the complete public diff before any public push.
