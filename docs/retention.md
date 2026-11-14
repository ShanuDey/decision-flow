# Retention

Runs keep their inputs and outputs, and accounts keep an email and a name. A shared or public deployment should not keep them forever, so an in-process timer deletes old data. It is off by default: `0` keeps everything.

| Variable | Default | Meaning |
|---|---|---|
| `RUN_RETENTION_DAYS` | `0` (off) | Delete runs older than this many days, and MLflow traces older than this or `USER_RETENTION_DAYS`, whichever is shorter |
| `USER_RETENTION_DAYS` | `0` (off) | Delete accounts not seen for this many days, with their workspace, flows, runs and sign-in records |
| `RETENTION_INTERVAL_MINUTES` | `60` | How often the timer runs. The first pass runs 30 seconds after start |
| `RETENTION_KEEP_EMAILS` | empty | Comma-separated emails that are never deleted. Case does not matter |
| `RETENTION_DRY_RUN` | `false` | Log what would be deleted and delete nothing |

The timer starts only when at least one of the two day values is set. A public demo might use `7` for both.

## What is deleted

Each pass does these in order. A step that fails is logged and skipped, and the others still run.

1. Runs older than `RUN_RETENTION_DAYS`.
2. MLflow traces older than the shorter of the two day values that are set (a deleted account's traces still hold its run data). This also removes the traces of flows that were deleted.
3. Accounts inactive for `USER_RETENTION_DAYS`: their workspace and everything in it, then the account itself and its sign-in records (`auth` schema). The next sign-in with the same login starts a new account with an empty workspace.
4. Expired sign-in sessions.

An account counts as seen when it makes a request, recorded at most once an hour. Existing accounts start with a full period from the moment this feature is installed.

## Running it safely

- Start with `RETENTION_DRY_RUN=true`. The log shows how many runs, accounts and sessions a pass would delete (MLflow traces are not counted in a dry run). Turn it off when the numbers look right.
- Put your own email in `RETENTION_KEEP_EMAILS` before setting `USER_RETENTION_DAYS`, or your own account is deleted when you stay away.
- The log shows counts only: no emails, flow names or run data.

## Notes

- State lives in the rows' timestamps, so a restart, or a free-tier service waking from sleep, just runs the next pass. A service that is asleep does not run the timer.
- Two API instances never run a pass at the same time. This uses a Postgres advisory lock, which needs a direct database connection: with Neon, use the endpoint without `-pooler`.
- Sign-in records are deleted only if they live in the same database as the API (the `auth` schema). If the web app uses its own `AUTH_DATABASE_URL`, the log warns that they are left alone.
- Drafts and published flows are only deleted together with their account. Run retention never touches them.
