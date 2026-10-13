# Publication privacy notes

This public copy preserves numerical light and color measurements, including raw samples and rejected or interrupted experiment observations, together with selected analysis code, plots, and acquisition firmware.

Home Assistant state snapshots, entity and device identifiers, automation/configuration files, service traces, deployment records, logs, runtime paths, and local export audits were excluded. These files can identify household devices, users, locations, network details, or local account paths and are not needed to interpret the measurements. Repository documentation and plots use generic fixture labels. Any broker or credential settings in firmware examples are placeholders; real credential files and binaries are excluded.

Third-party observer source and its license notice are retained for attribution. Numeric sample values and timestamps are retained; timestamps are UTC measurement times and do not include household identity. Original working files remain in the private workspace and were not modified.

The HC adaptive lookup is included as a numeric-only curve in `calibration/koto-hc/adaptive-lookup/`. Its original Home Assistant entity-to-module map, machine-local source path, and deployment context were removed.
