# Fork / CI backlog (mylar3-mod)

Durable **backlog** for infrastructure and release tooling that is **not** tied to a single in-app feature. For Library Housekeeping requirements, use `HOUSEKEEPING_ENHANCEMENTS.md`.

| ID | Priority | Description | Status | Notes / resolution |
|----|----------|-------------|--------|----------------------|
| **CI-1** | Low–medium | **GHCR image tags and traceability** | **Done** | Workflow: `.github/workflows/build_feature_container.yml`. Tags: `ghcr.io/<owner>/mylar3:latest` and `ghcr.io/<owner>/mylar3:<upstreamVersion>-mod.<n>` (repo stays `mylar3-mod`; image name matches komga-mod pattern). Version files: `fork.version`, `fork.build`. |

---

## Docker image tags

On each push to `ghcr-build` (and other non-`stable` / non-`nightly` branches), CI publishes:

- **`ghcr.io/james-a/mylar3:latest`** — always the most recent build from the triggering branch
- **`ghcr.io/james-a/mylar3:0.11.0-mod.2`** — example immutable tag (`fork.version` + `fork.build`)

**Before publishing another image for the same upstream Mylar3 version:** increment `fork.build` (e.g. `1` → `2` → `0.11.0-mod.2`).

**After merging a new upstream release:** set `fork.version` to that release (e.g. `0.12.0`) and reset `fork.build` to `1`.

---

## Changelog (append only)

| Date | Change |
|------|--------|
| 2026-04-28 | Created; **CI-1** added (GHCR tagging / version clarity). |
| 2026-06-27 | Merged upstream **v0.10.0** on `ghcr-build`; CI workflow uses LSIO **`nightly`** ref; sed comments reordered (primary `MylarComics/mylar3` + `commits/nightly`, legacy patterns kept as no-ops). |
| 2026-09-01 | Merged upstream **v0.11.0** on `ghcr-build`; no CI workflow changes in merge. Rebuild/push GHCR image when ready to deploy. |
| 2026-09-01 | **CI-1 done:** explicit `latest` + `{fork.version}-mod.{fork.build}` tags; added `fork.version` / `fork.build` (komga-mod pattern). |
| 2026-09-01 | GHCR package renamed to `ghcr.io/james-a/mylar3` (was `mylar3-mod`); `fork.build` bumped to `2`. Update NAS compose from old image path. |

*Agents: add a row when this backlog or CI behaviour changes.*
