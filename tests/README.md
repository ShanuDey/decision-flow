# Automation tests

Black-box tests that run against a live stack. They are separate from the unit tests in `api/tests` and `web/src/**/*.test.ts`, and are not part of `make checks` (they need the stack running).

```
tests/
  playwright.config.ts     one config, one project per kind of test
  preflight/               checks the stack is up and its rate limits allow a run
  support/
    env.ts                 .env loading, credentials, testName()
    fixtures.ts            `flow` (API-created, auto-deleted) and `editor` (flow open in the editor)
    editor.ts              editor helpers (addNode, settingsPanel, saveState)
    ui.ts                  login and the "New flow" / delete dialogs
    api.ts                 signed-in API client for api/ specs
  ui/                      browser tests (project: ui, signed in once by setup)
    setup/auth.setup.ts    signs in and saves the session to .auth/ (git-ignored)
    auth/                  login.spec.ts
    flows/                 list.spec.ts
    errors/                limits.spec.ts (429 and 409 messages, mocked in the browser)
    settings/              appearance, account, system, navigation
    editor/                top-bar, node-picker, config-panel, expand-dialog, validate, leave-guard, run
  api/                     HTTP tests through the web proxy (project: api)
    flows.spec.ts, expressions.spec.ts
```

One spec file per page or feature, grouped by folder. Specs are small and independent: each creates its own data (usually through the `flow` fixture) and cleans up after itself.

## Run

```sh
make start            # in another terminal: DB, API :8000, web :3000
make e2e-install      # once: install dependencies and the Chromium browser
make e2e              # everything
make e2e-ui           # browser tests only
make e2e-api          # API tests only
```

### Rate limits (important)

The suite makes far more requests than the default per-minute limits allow (it creates and deletes a flow per test), so a default stack answers `429`. For test runs, turn the limits off in the repo-root `.env` and restart the API:

```sh
RATE_LIMIT_IP_PER_MINUTE=0
RATE_LIMIT_USER_WRITES_PER_MINUTE=0
RATE_LIMIT_USER_RUNS_PER_MINUTE=0
```

The `preflight` project checks this first and stops the run with that exact message if a limit is still active, so you never get a wall of unrelated `429` failures. Do not turn these off on a shared or public deployment (see `docs/limits.md`).

Run a subset directly: `pnpm --dir tests exec playwright test ui/editor` or `... -g "Ctrl+S"`.

Credentials come from the repo-root `.env` (`AUTH_ADMIN_EMAIL`, `AUTH_ADMIN_PASSWORD`), or from the environment. Set `E2E_BASE_URL` to test a different web URL. The HTML report is written to `tests/playwright-report/`; open it with `pnpm --dir tests exec playwright show-report`.

## Adding tests

- **A new page or feature:** add a `*.spec.ts` in the matching folder under `ui/` (or a new folder). Use `import { test, expect } from "../../support/fixtures"` when you need a flow or the editor, or plain `@playwright/test` otherwise.
- **A new kind of test** (for example `perf/` or `a11y/`): a new folder plus a new entry in `projects`.
- **Test data:** names come from `testName("label")` and start with `e2e `, so leftovers are easy to spot and delete.
- **Signed-out tests:** add `test.use({ storageState: { cookies: [], origins: [] } })` at the top of the file (see `ui/auth/login.spec.ts`).
