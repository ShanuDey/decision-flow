---
title: "Secrets"
---

A secret is a named value, such as an API token, that a flow can use without the value being written into the flow. Secrets belong to a workspace. They are stored encrypted, and once saved the value cannot be read back: you can replace it or delete it.

## Add a secret

1. Open **Settings → Secrets** and choose **Add secret**.
2. Enter a name and a value. The eye button next to the value shows what you typed before you save.
3. Choose **Save**.

| Part | Rule |
|---|---|
| Name | Capital letters, digits and underscores, starting with a letter, up to 64 characters, such as `STRIPE_KEY`. The form capitalizes as you type |
| Value | 8 to 4096 characters, stored exactly as typed |

Saving a name that already exists replaces its value. Deleting a secret is permanent.

## Use a secret in a flow

A node can read a secret as `{{ secrets.NAME }}`, but only in fields that say they accept one. Every other field refuses it with a `secret_not_allowed` error, so a secret cannot end up in a variable, an output or a trace by accident.

The current nodes (Start, Assign, Condition and End) accept no secrets. Nodes that call outside services will accept them in their headers and body, and never in the URL.

A flow can name a secret before it exists. Saving works, and a run that needs the missing secret stops before any node runs with a `secret_not_found` error that lists the names.

Secrets are managed from the signed-in web app only. API keys and the MCP connection cannot list, read or change them.

## Set up the encryption key

Secrets are encrypted with the key in `ENCRYPTION_KEY`, which lives on the API server and not in the database. A copy of the database alone does not reveal any secret.

- **Running from source (`make start`):** `make setup` adds a key to your `.env` the first time and never overwrites an existing one. `make secrets-setup` does only that part.
- **Docker, or a hosted service:** generate a key yourself and set `ENCRYPTION_KEY` in the environment you deploy with.

To generate a key:

```
openssl rand -base64 32 | tr '+/' '-_'
```

Without OpenSSL, `make secrets-setup ARGS=--print` prints a key from a source checkout, or in any Python environment that has the `cryptography` package:

```
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Without a key the app still runs, runs that use no secrets still work, and the Secrets page lists names. Saving a secret fails with a message that the key is missing.

**Back the key up.** If it is lost, every saved secret is unrecoverable and has to be added again. Store it somewhere other than the database backup.

### Rotate the key

`ENCRYPTION_KEY` accepts several keys, separated by commas. The first one encrypts and all of them decrypt.

1. Generate a new key and put it first: `ENCRYPTION_KEY=NEW_KEY,OLD_KEY`. Restart the API.
2. Replace each secret in **Settings → Secrets**. A replaced secret is encrypted with the new key.
3. Once every secret has been replaced, remove `OLD_KEY`.

If a run needs a secret that no listed key can decrypt, it stops with a `secret_unreadable` error naming the secret.

## What is hidden in records

Run traces, run results and error messages are checked before they are stored or returned. A stored secret's value is replaced by its name, for example `Bearer [REDACTED:STRIPE_KEY]`. This also catches the value in its JSON-escaped and URL-encoded forms.

The values of credential headers (`Authorization`, `Proxy-Authorization`, `Cookie`, `Set-Cookie`, `X-Api-Key` and `Api-Key`) are replaced by `[REDACTED]`, even when the value was typed into the flow and is not a stored secret.

This is a safety net, not a guarantee. A value that a node changes first, such as one encoded for Basic authentication, no longer matches and is not caught. The main protection is that a secret never enters flow state at all.

## Limit

| Variable | Default | Meaning |
|---|---|---|
| `MAX_SECRETS_PER_WORKSPACE` | `0` (off) | Most secrets one workspace can hold. Replacing a secret does not count against it |

See [limits](limits) for the rest.
