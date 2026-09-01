# Git workflow (mylar3-src)

Small, **focused commits** make history readable, `git bisect` useful, and reverts or cherry-picks safer.

## Practices

- **One logical change per commit** — e.g. one requirement ID (`REQ-1.1`, `REQ-1.2`) or one bugfix. If a follow-up is required (e.g. fix lint), it can be a second commit in the same PR.
- **Message style:** prefer a **subject line** of the form `feat(housekeeping): short description` or `fix(webserve): short description` (scope = area touched). The body can list details if needed.
- **Before committing:** `git status` / `git diff` — ensure only intended files (avoid committing `.vscode/`, local secrets, or unrelated edits).
- **Branch:** work on a feature branch when collaborating; for solo work, your existing branch (e.g. `ghcr-build`) is fine if that is your convention.

## Splitting this project’s docs

- **Tracked in this repo** (`mylar3-src/`): `docs/` and application code. Commit these with the feature they document when possible.
- **Parent folder** `mylar-mod/`: if there is no git repo at that level, `.cursor` rules and `mylar-mod/docs/` are **not** in `mylar3-src`; back them up or add a monorepo root git if you want them versioned together.

## Agents

- Prefer **a commit after each completed requirement** (or each coherent slice), with a message that references the requirement (e.g. `REQ-1.2`). Update `HOUSEKEEPING_ENHANCEMENTS.md` (if present in the tree you commit) in the same change or a small follow commit.

## Container image tags (GHCR)

- **`fork.version`** — upstream Mylar3 release last merged (e.g. `0.11.0`). Update when syncing a new upstream tag.
- **`fork.build`** — integer incremented before each publish for the **same** `fork.version`; reset to `1` after an upstream version bump.
- CI (`.github/workflows/build_feature_container.yml`) pushes `ghcr.io/<owner>/mylar3:latest` and `ghcr.io/<owner>/mylar3:<fork.version>-mod.<fork.build>`. GitHub repo remains `mylar3-mod`. See `docs/FORK_CI_BACKLOG.md`.
