# Library Housekeeping — audit enhancements (project plan)

**Tracked copy:** this file lives in **`mylar3-src/docs/`** with the application. A second copy may exist in the parent workspace (`mylar-mod/docs/`); keep them aligned when you maintain both.

**Purpose:** Durable **source of truth** for agents and future sessions: requirements, backlog, decisions, and changelog. It does **not** replace chat: answers and plans should still be given fully in the thread; this file is updated in parallel. If you edit it manually, ask an agent to **review and implement** as needed (see project rule `project-planning-docs`).

**CI / container backlog (fork, not feature-specific):** `docs/FORK_CI_BACKLOG.md` (e.g. GHCR image tags).

**Code references (mylar3-src):**
- UI: `data/interfaces/default/housekeeping.html`
- API: `mylar/webserve.py` — `housekeeping`, `housekeepingAudit`, `comicRenameFolder`
- Audit logic: `contrib/mylar_housekeeping/audit.py`
- CBZ metadata: `contrib/mylar_housekeeping/cbz_metadata.py` — `housekeepingSeriesMetadataAudit`, `IssueInfo` enrichment, metatag stamp in `cmtagmylar.py`
- Folder rename (align to format): `contrib/mylar_housekeeping/folder_align.py` → `mylar.filers.FileHandlers.folder_create()`

**Current behaviour (snapshot):** `housekeeping` loads with an empty table unless **browser `localStorage`** has a previous audit payload, which is restored client-side. “Run audit” calls `housekeepingAudit`, then the client updates the table and **persists** the JSON to `localStorage` (a new run replaces the stored list). “Clear saved results” removes the cache and shows the empty state.

**Implementation policy:** **One requirement (or sub-requirement) per git commit** unless a change is unusable without a tiny follow-up. Confirm scope in chat before writing code (see project rule `confirm-before-coding`).

---

## Requirements & backlog

| ID | Priority | Description | Status | Notes / resolution |
|----|----------|-------------|--------|----------------------|
| **REQ-1** | **High** | **Filtering and sorting** | **Done** | See §1 |
| REQ-1.1 | High | Column sorting: Comic Name (default), Status, Publisher, Updated | **Done** | DataTables: same `sDom` / `stateSave` / paging style as `managecomics.html`; re-init after Run audit. |
| REQ-1.2 | High | Result filters with counts, checkbox UX per `/upcoming`-style | **Done** | Checkboxes + row classes + `ext.search` OR; **per-label** show only when that category’s count &gt; 0; reuse **`Downloaded`** / **`Wanted`** from `style.css` (comic details pattern). **Not** a requirement: hiding the **entire** filter block when the table has no series-level rows. |
| **REQ-2** | Low–medium | **Retain last audit results** (survive navigation / session) | **Done** | `localStorage` key `mylar_housekeeping_audit_v1`; restore on load; **Run audit** overwrites; **Clear saved results** |
| **REQ-3** | Medium | **Pagination** (controls top + bottom, page size, “showing X–Y of Z”) | **Done** | Implemented with REQ-1.1; see §3 — optional polish: expand `lengthMenu` to match post–v0.11.0 Manage Comics. |
| **REQ-4** | Low / future | **Audit performance** (non-blocking, faster on large DBs) | Assessed / backlog | See §4 — no code until prioritized |
| **REQ-5** | Medium | **Rename folder** respects **Force-Type** (`Corrected_Type`) for `$Type` in folder format | **Backlog** | See §5 — same-year name collision (Print run vs TPB) when override ignored |
| **REQ-6** | Medium–high | **CBZ ComicInfo validation** (Mylar metatag provenance + DB alignment, no CV API) | **Done** (6.1–6.4) | See §6 — **CBZ + ComicInfo.xml only**; comic-details UX; 6.5 library rollup optional |
| REQ-6.5 | Low / future | Library housekeeping rollup for CBZ metadata | **Backlog** | Optional series-level summary on housekeeping page |
| REQ-UX | Low | **Housekeeping UI parity** with post–v0.11.0 Manage Comics styling | **Backlog** | See §UX — cosmetic; not blocking |

*Status: Backlog | In progress | Done | Dropped. Link PR/commit when done.*

---

## §1 — Filtering and sorting (REQ-1)

### REQ-1.1 Sorting

- **Columns to sort:** Comic Name, Status, Publisher, Updated (as specified).
- **Default order:** Comic Name ascending (or match Manage Comics if product prefers).
- **Mechanism:** jQuery **DataTables** (already used, e.g. `managecomics.html`: `data_table.css`, `jquery.dataTables.min.js`, `lengthMenu`, `pagingType: "simple_numbers"`, `full_numbers_no_ellipses.js` where used).
- **Not sortable (typical):** art, stat icon, latest issue, have/progress, results (complex cells). **Confirm** if you want any of these later.

**Issues / notes:** The housekeeping table is **rebuilt in JS** after an audit. Any DataTable init must be **destroyed and recreated** (or use the API to clear/add rows) so sorting stays correct after `housekeepingRunAudit()`.

### REQ-1.2 Filtering (audit outcome)

- **All filters selected by default** → show full list (match upcoming/wanted table behaviour).
- **Filter dimensions (suggested, aligns with your description):**
  1. **All passed** — all three checks Pass (special rows: config/empty/series error stay visible or get a separate rule; **to confirm**).
  2. **Folder check failed** — `result_series_folder` ≠ Pass  
  3. **Issue files check failed** — `result_issue_files` ≠ Pass  
  4. **Metadata check failed** — `result_metadata` ≠ Pass  

**Multi-fail rows:** A series can fail more than one check. Treat each row as having **flags** (all_pass, sf_fail, if_fail, md_fail). A row is **visible** if *any* of its flags is still **included** by the current checkbox set, e.g.:

- `visible = (all_pass && filter_all_pass) || (sf_fail && filter_folder) || (if_fail && filter_issue) || (md_fail && filter_metadata)`  

with obvious definitions for `all_pass` and each `*_fail` from the JSON row. Unchecking “Folder” removes rows that have a folder failure from the *current* set (even if they also fail metadata). This matches “focus on one failure type” and matches **OR-with-user-selection**, not a single category per row.

- **Counts:** Per filter, show **n** of rows in the current audit dataset.

- **Styling:** Use the same classes as the issue/comic table filters: **`Downloaded`** (green) for “all passed” and **`Wanted`** (red/pink) for each failure type — from `data/interfaces/default/css/style.css` (as on `comicdetails_update.html`). Do **not** add parallel pale custom colours.
- **Per-label visibility (required):** Show a filter label **only when** that category’s count is **&gt; 0** (same as comic details’ `display:none` / `inline` on each label). When count returns to 0, hide the label again. Reset the hidden checkbox to **checked** so it does not keep excluding rows in memory.
- **Not required (explicit):** Hiding the **entire** filter bar / help row when the audit table has no series-level rows, or in “no data” states — that was an incorrect add-on; **per-label** hide when count is 0 is sufficient to avoid empty, useless filter chips.

**Feedback:** Upcoming’s wanted table uses a **separate** checkbox control region + DataTables — we should mirror that pattern. If anything feels overloaded, a **second row** of controls only for housekeeping is acceptable.

---

## §2 — Retain audit results (REQ-2) **done**

- **Implementation:** `localStorage` (key `mylar_housekeeping_audit_v1`, payload `v: 1`, `savedAt` ISO, `message`, `rows`). Restored on page load when present. **Re-run (Run audit)** replaces the snapshot on success. **Clear saved results** removes the key and returns the table to the empty state.
- **Re-run** replaces stored snapshot.
- **Clear** button removes stored snapshot and resets UI to empty/placeholder.
- **Options:**
  1. **Server-side (align with import results):** Store JSON (or normalised table) in SQLite, e.g. one-row cache table or `kv` if the project has one. **Pro:** same device from any browser session, matches “import” mental model. **Con:** small schema/migration.
  2. **Browser `localStorage`:** **Pro:** no DB change, fast. **Con:** per-browser/device only.

**Decision (2026):** Use **browser `localStorage`** (no SQLite schema) so forks stay easy to align with **upstream Mylar3**; low criticality; include a version key in the JSON.

- **Load path:** On `GET housekeeping`, return last snapshot into `audit_rows` (or a dedicated small JSON `GET housekeepingCachedAudit`) so first paint is useful without re-running the audit.

---

## §3 — Pagination (REQ-3) **done**

**Status (2026-09-01):** Delivered incidentally with **REQ-1.1** DataTables init in `housekeeping.html`. Compared to `managecomics.html` (post–v0.11.0):

| Requirement | Housekeeping | Manage Comics | Match? |
|-------------|--------------|---------------|--------|
| Top + bottom controls (`sDom`) | `'<"clear"f><"clear"lp>…<"clear"ip>'` | Same | Yes |
| “Showing _START_ to _END_ of _TOTAL_ results” | `language.info` | Same | Yes |
| Default page length | 25 | 25 | Yes |
| `stateSave` | true | true | Yes |
| `pagingType` | `simple_numbers` | `simple_numbers` | Yes |
| `lengthMenu` | 10, 25, 50, All | 10, 25, 50, 100, 200, 500, All | Partial |

**Optional polish (not blocking):** add 100 / 200 / 500 to housekeeping `lengthMenu` when aligning with Manage Comics norms. Original spec mentioned 25/50/100/200/All without 10 — current UI is fine.

---

## §4 — Audit performance (REQ-4)

- **Current:** `housekeepingAudit` runs `run_library_audit()` inside the **same CherryPy request** → browser waits; other tabs using the app may feel sluggish while Python/SQLite/disk are busy.
- **Directions (future work; no implementation until you prioritise):**
  - Run audit in a **background thread** with a **job id**; UI polls `housekeepingAuditStatus?job=…` or WebSocket (unlikely in this codebase) for progress/result.
  - **SQLite:** `PRAGMA` / index review on paths touched by audit; avoid N+1 queries inside `run_library_audit` (profile first).
  - **Chunking / incremental:** Heavier architectural change; only if profiling justifies it.

**Deliverable for “assessment” phase:** A short “Performance notes” subsection here + optional one-off timing logs behind debug flag.

---

## §5 — Rename folder + Force-Type (`Corrected_Type`) (REQ-5) **backlog**

**Problem (user report):** A series can be **Print** in metadata (`Type`) while the user sets **Force-Type** to **TPB** (stored as `Corrected_Type` in `comics`) so searching/downloads behave correctly. **Rename Folder** and expected-path logic use `mylar.filers.FileHandlers.folder_create()` to compute the directory under `FOLDER_FORMAT` (including `$Type`). If that code path uses only **`Type`**, the on-disk name may match another series in the same year (e.g. ongoing issues vs a TPB) or a forced rename can **collapse** the intended disambiguation.

**Where it lives today**

- **Rename Folder** (comic details): `webserve.comicRenameFolder` → `align_series_folder_to_format` → `FileHandlers(ComicID).folder_create()` with default args (`mylar/filers.py`, `folder_create` around lines 71–137).
- **Housekeeping** “Refresh / align” uses the same `folder_align.align_series_folder_to_format`.
- **Config UI:** `comicdetails_update.html` — “Force-Type (original: `Type`)” → `comic_config` persists `Corrected_Type` (`webserve.py`); `comic_config` already notes renames when `$Type` is in the format string.
- **Audit** compares stored `ComicLocation` to `folder_create()`’s `comlocation` — if `folder_create` ignores the override, the audit and rename **stay consistent with each other** but both disagree with the user’s “effective” type.

**Root cause (code-level)**

- In `folder_create(self, booktype=None, …)`: when **`booktype` is `None`** (the usual case for rename/align), the code sets `booktype = self.comic['Type']` only. The **Force-Type** field **`Corrected_Type` is not applied** on that branch.
- A separate block (when **`booktype is not None`**) attempts to merge caller-supplied `booktype` with `Corrected_Type`, but the default path never uses `Corrected_Type` as the effective book type for `$Type`.

**Proposed direction (for implementation; confirm in chat before coding)**

1. **Effective type for folder naming** when `booktype is None`: use **`Corrected_Type` if not null, else `Type`**, then run the existing logic (`$Type` token, `FORMAT_BOOKTYPE`, stripping for “Print” vs other types, etc.) unchanged so behaviour stays predictable.
2. **Call-site review:** Grep for `folder_create(` and any `booktype=` passed explicitly — ensure overrides remain correct and no double-application.
3. **Tests / manual cases:** two series, same year + similar `ComicName`, one `Print` + one **Force-Type TPB** — expected folders must differ when `$Type` is in `FOLDER_FORMAT`. Verify **Rename Files** if it shares the same `booktype` rules (separate code paths; only mention if a follow-up is needed).
4. **Downstream:** Once `folder_create` matches user intent, library housekeeping’s **expected path** in the audit will match as well; no separate audit change unless a different product rule is desired.

*This requirement is about **filers / folder format**, not the housekeeping table UI, but is tracked here as the same fork’s backlog.*

---

## §6 — CBZ ComicInfo validation (REQ-6) **done (6.1–6.4)**

**Problem:** Many CBZs were tagged outside Mylar (ComicTagger, Komga export, manual edits). They pass today’s **issue files** check (`.cbz` + rename match) and may contain ComicInfo, but it is unclear whether tags are **Mylar-authored** or **misaligned** with the `issues` / `comics` rows. A full-library **MetaTag** refresh is impractical due to **Comic Vine API rate limits**.

**What “metadata check” means in library housekeeping (unchanged):** `_metadata_pass()` in `contrib/mylar_housekeeping/audit.py` only validates **directory sidecars** when enabled in config (`series.json`, `cvinfo`, `cover.jpg`, `folder.jpg`). It does **not** open CBZs. CBZ validation is **on-demand per series** on comic details (see below).

**Format scope (decision):** Audit and compare logic applies **only to `.cbz` archives that contain `ComicInfo.xml`**. **CBR, CB7, and other formats are skipped** — ComicInfo is not reliably readable/writable in those paths without conversion.

### Implemented approach (no CV calls in audit path)

**REQ-6.1 — Mylar metatag stamp (in-file, not SQLite)**

- On **successful** ComicTagger completion in `cmtagmylar.run`, append or replace token `[MylarMetaTagged:ISO8601Z]` in `ComicInfo.xml` **`Notes`** inside the CBZ (`apply_mylar_metatag_stamp`).
- **CBZ only**; no schema migration.
- Pre-existing / externally tagged files lack the stamp until metatagged again by Mylar.

**REQ-6.2 — Compare helper (`contrib/mylar_housekeeping/cbz_metadata.py`)**

- `read_comicinfo_from_cbz`, `compare_cbz_metadata`, `resolve_issue_filepath`.
- **CBZ + ComicInfo.xml only**; returns `skipped_non_cbz` for other extensions.
- Compare ComicInfo to DB **without** Comic Vine:

  | ComicInfo field | Compare to | Notes |
  |-----------------|------------|-------|
  | `Notes` — `[MylarMetaTagged:…]` | — | Hard fail if missing (never Mylar-tagged) |
  | `Notes` (Issue ID / CVDB) | `issues.IssueID` | Hard fail on mismatch |
  | `Series` | `comics.ComicName` | Normalized; hard fail on mismatch |
  | `Number` | `Issue_Number` | Normalized; hard fail on mismatch |
  | `Title` | `IssueName` | **Warning only** |

- Outcomes: `ok` | `skipped_non_cbz` | `no_comicinfo` | `never_mylar_tagged` | `wrong_issue_id` | `field_mismatch` | `missing_file`.

**REQ-6.3 — Series audit endpoint + UI**

- `webserve.housekeepingSeriesMetadataAudit(ComicID)` → `audit_series_cbz_metadata` (same status exclusions as issue-files audit).
- Comic details menu: **Audit CBZ Metadata** — runs audit, stores results in `localStorage` (`mylar_cbz_audit_v1_{ComicID}`), refreshes issue tables.
- **No CBZ reads on comic details page load.**

**REQ-6.4 — Issue icon + popup**

- Downloaded/archived **CBZ** rows: blue `issueinfo` icon; **`issueinfo_red.png`** when last audit failed.
- **CBR** keeps orange icon (audit N/A).
- `IssueInfo` JSON adds `metadata_audit` when filepath is `.cbz` (compare on popup open only).

**REQ-6.5 — Library housekeeping rollup (optional, backlog)**

- Future: series-level CBZ metadata summary on housekeeping page (would still avoid full-library pass on every page load; likely cached or user-triggered).

### Dependencies and risks

- **Performance:** Per-series audit only; library-wide CBZ reads deferred to REQ-6.5 / REQ-4 if ever added.
- **External tags:** Valid ComicInfo may still fail **provenance** (no Mylar stamp) — intentional; user can selective metatag.
- **False positives:** `Title` warns only; hard fails prefer **Issue ID in Notes** and series/number.

---

## §UX — Housekeeping styling parity (REQ-UX) **backlog**

Upstream **v0.11.0** refreshed Manage Comics/Issues (`managecomics.css`, button action rows, confirm dialog, selected counter). Housekeeping intentionally kept the **pre-refactor** DataTables + checkbox filter pattern (still valid).

**Proposed alignment (cosmetic, low priority):**

| Area | Current | Align to |
|------|---------|----------|
| Control row | Fieldset + plain buttons “Run audit” / “Clear saved” | Optional `managecomics.css` button styling; keep actions audit-specific (no bulk comic select) |
| Filter bar | Comic-details `Downloaded` / `Wanted` chips | Keep — matches issue tables better than manage action buttons |
| Table chrome | `data_table.css` only | Already shared |
| Search label | `"Filter:"` | Manage Comics uses empty search label — minor consistency tweak |
| `lengthMenu` | 10/25/50/All | Add 100/200/500 (REQ-3 polish) |

**Do not copy** bulk-action confirm UX unless housekeeping gains multi-select series actions (out of scope today).

---

## Suggested order of work (one theme per commit / PR when possible)

1. **Project doc** (this file) + **REQ-1.1** — DataTables init, sortable columns, non-sortable others, re-init after audit JSON load.
2. **REQ-1.2** — Filter row, CSS, custom filter + counts, test multi-fail rows.
3. **REQ-2** — Persist + load + clear; wire `housekeeping` + optional endpoint.
4. **REQ-3** — ~~pagination~~ **done** (REQ-1.1); optional `lengthMenu` expansion only.
5. **REQ-4** — Document findings; code only if approved.
6. **REQ-5** — `folder_create` effective type = `Corrected_Type` or `Type`; test rename + collision cases.
7. ~~**REQ-6.1–6.4**~~ — CBZ metatag stamp + compare + comic-details audit UX (see §6). **REQ-6.5** library rollup optional.
8. **REQ-UX** — optional Manage Comics CSS/button polish.

(If you prefer **persistence before filters** to avoid re-filtering huge lists, swap 2 and 3.)

---

## Decisions (resolved in chat; update this table if requirements change)

| Topic | Decision |
|-------|----------|
| Special / error rows (`config_error`, `empty_library`, `series_error`) | For **REQ-1.2** filters: **not** “all passed” — treat as **outcome = fail** / failure bucket for the purpose of the green “all passed” filter (low priority; exact UX can follow when filters ship). |
| “Updated” / name sort keys | **Match Manage Comics:** same DataTables + cell behaviour; use `data-order` on sortable cells where needed (name: lowercased display string; updated: `DateAdded` as in manage). |
| DataTables `stateSave` | **Yes** for housekeeping. |
| REQ-2 cache | **`localStorage`**, for upstream alignment and low criticality. |
| Per-label vs whole-bar filter | **Required:** per-label show/hide when that category’s count is &gt; 0. **Not required (revert 2026-04-23):** hide the **entire** filter bar when there are no series-level rows. |
| REQ-6 provenance stamp | **In-CBZ** `ComicInfo.xml` **`Notes`**: `[MylarMetaTagged:ISO8601Z]` — **not** a SQLite column. |
| REQ-6 format scope | **CBZ + ComicInfo.xml only**; CBR/other formats skipped (no audit/compare). |
| REQ-6 UX scope | **Comic details** per-series audit + issue icons/popup; **not** full-library CBZ pass on housekeeping page load (6.5 optional later). |

---

## Changelog (append only)

| Date | Author | Change |
|------|--------|--------|
| 2026-04-23 | — | Initial plan, requirements table, and technical notes (no code). |
| 2026-04-23 | — | **REQ-1.1:** DataTables on housekeeping (sort: Comic Name, Status, Publisher, Updated); `stateSave`; destroy/reinit after audit; doc workflow + open-question decisions. |
| 2026-04-23 | — | **REQ-1.2:** Result filters (all passed, folder / issue / metadata fail) with counts; `mylar3-src/docs/CONTRIBUTING_GIT.md` + `.cursor/rules/git-workflow.mdc`. Commits: `0dcdbd4` (REQ-1.1), `9441ea4` (REQ-1.2). |
| 2026-04-23 | — | Filter UX: `Downloaded` / `Wanted` classes; per-label visibility by count. Commit `838237e` also hid the whole bar when no series rows — **reverted** (not required). |
| 2026-04-23 | — | **Process:** `confirm-before-coding` strengthened: “thoughts” = no implementation; confirm before any dev; optional once-off bypass if user states it. |
| 2026-04-23 | — | Revert whole-bar filter hide; this file added under `mylar3-src/docs/`. Commit: `d445ab5`. |
| 2026-04-27 | — | Revert `80893a5` (VS Code / watch script) as `508e12f`. **REQ-2:** `localStorage` key `mylar_housekeeping_audit_v1`, restore on load, clear button. Commit: `c07de4c`. |
| 2026-04-28 | — | **CI-1** backlog: GHCR image version/tag clarity (see `docs/FORK_CI_BACKLOG.md`); no workflow change. |
| 2026-04-28 | — | **Bugfix:** Result filter checkbox counts use full in-memory audit `rows` (`housekeepingAuditRows`), not `tbody` (fixes wrong counts with DataTables `deferRender` + pagination). |
| 2026-04-28 | — | **REQ-5** backlog: Rename folder / `folder_create` should use **Force-Type** (`Corrected_Type`) for `$Type`; see §5. |
| 2026-06-27 | — | Merged upstream **v0.10.0** into `ghcr-build`; no housekeeping code conflicts; smoke-test after deploy (audit, filters, localStorage, Rename Folder). |
| 2026-09-01 | — | Merged upstream **v0.11.0** into `ghcr-build`; `mylar/filers.py` and `mylar/webserve.py` auto-merged (fork path-collapse + upstream Print `$Type` dedup; housekeeping endpoints retained). Smoke-test after deploy. |
| 2026-09-01 | — | **REQ-3** marked **Done** (pagination already in DataTables init); **REQ-6** CBZ ComicInfo validation backlog added (§6); **REQ-UX** styling notes (§UX). |
| 2026-09-01 | — | **REQ-6.1–6.4:** CBZ-only ComicInfo audit — Notes stamp on metatag (`cbz_metadata.py`, `cmtagmylar.py`); `housekeepingSeriesMetadataAudit`; comic details audit button, icon tint, `IssueInfo` metadata block. |

*Agents: add a row for each merged change affecting this feature.*

---

## How to edit this document

- Change **Status** in the requirements table, add rows for new ideas, and update the **Decisions** table when scope changes.
- Keep **IDs** (`REQ-1.1`, …) stable so commits and PRs can reference `docs/HOUSEKEEPING_ENHANCEMENTS.md#req-1-1` style links.
