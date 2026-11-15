---
title: "Data deletion"
---

`DELETE_MODE` decides what happens when someone deletes a flow, and when a flow's oldest versions fall out of the `MAX_VERSIONS_PER_FLOW` window (see [limits](/docs/limits)).

| `DELETE_MODE` | Default | Effect |
|---|---|---|
| `hard` | | The flow and its runs are removed for good. Versions older than the window are removed. A shared public deployment usually picks this to keep storage bounded. |
| `soft` | yes | Nothing is removed. The row gets `deleted_at` and `deleted_by` and disappears from every list and endpoint. |

## Soft mode

- A deleted flow answers `404` everywhere, like a missing one, and no longer counts against `MAX_FLOWS_PER_USER`.
- Its versions are hidden with it. Versions that leave the window are marked deleted too, by the person whose publish pushed them out. Version numbers still keep counting up.
- Its runs stay in the Runs list and on the run page, shown under the flow's name with a **Deleted flow** tag. They are not linked to the flow, because it can no longer be opened.
- There is no restore in the app yet. An operator can clear `deleted_at` and `deleted_by` in the database.

## Switching modes

Switching from `soft` to `hard` does not purge rows that were already soft-deleted. They stay hidden until `USER_RETENTION_DAYS` removes the workspace or an operator deletes them.

## What soft mode does not keep

[Retention](/docs/retention) is separate. `RUN_RETENTION_DAYS` still deletes old runs, and `USER_RETENTION_DAYS` still deletes an inactive person's workspace with everything in it, including rows that were soft-deleted.

`GET /config` returns the current `delete_mode`, which the web app uses to word the delete dialog. If it cannot be reached, the dialog uses the `hard` wording.
