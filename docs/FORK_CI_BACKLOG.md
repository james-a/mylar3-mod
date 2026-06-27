# Fork / CI backlog (mylar3-mod)

Durable **backlog** for infrastructure and release tooling that is **not** tied to a single in-app feature. For Library Housekeeping requirements, use `HOUSEKEEPING_ENHANCEMENTS.md`.

| ID | Priority | Description | Status | Notes / resolution |
|----|----------|-------------|--------|----------------------|
| **CI-1** | Low–medium | **GHCR image tags and traceability** — make it easy to see **which build** or **when** an image was produced, without relying only on a **mutable** branch tag (e.g. `ghcr-build` moving on every push) | **Backlog** | Workflow: `.github/workflows/build_feature_container.yml`; `docker/metadata-action` (currently default tag set). **When revisited, consider:** (1) Document or standardise on **immutable** tags already produced by defaults (e.g. `type=sha`) vs branch tag. (2) Add **readable** unique tags with `type=raw` (e.g. date + `github.run_id` or `run_number`). (3) **SemVer** from git release tags for named releases. (4) **OCI labels** on the image (`org.opencontainers.image.revision`, `created`, `version`). Full trade-off discussion was in chat (2026-04-28; analysis only, no code). |

---

## Changelog (append only)

| Date | Change |
|------|--------|
| 2026-04-28 | Created; **CI-1** added (GHCR tagging / version clarity). |
| 2026-06-27 | Merged upstream **v0.10.0** on `ghcr-build`; CI workflow uses LSIO **`nightly`** ref; sed comments reordered (primary `MylarComics/mylar3` + `commits/nightly`, legacy patterns kept as no-ops). |

*Agents: add a row when this backlog or CI behaviour changes.*
