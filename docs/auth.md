# Authentication

Every API route except `/health` and `/ready` requires a bearer token. There is no switch to turn this off. If no provider is configured, the API refuses to start.

```
Authorization: Bearer <token>
```

The API only verifies tokens. It never stores passwords and never shows a login page. A token comes from an identity provider you configure, and the API checks its signature, issuer, audience and expiry.

## Configure providers

`AUTH_PROVIDERS` is a JSON list. Each entry is one of two types.

### `jwt`: signed tokens

Works with any provider that issues signed JWTs (Google, Firebase, Neon Auth, Auth0, Keycloak, Entra, Okta, or your own web server).

| Field | Meaning |
|---|---|
| `name` | Unique label, returned as `provider` by `GET /me` |
| `issuer` | The token's `iss` claim |
| `audience` | The token's `aud` claim (your client id or project id) |
| `jwks_url` | Where the provider publishes its keys. Leave empty to discover it from the issuer's OIDC metadata |
| `public_key` | A PEM public key, instead of `jwks_url`. `\n` escapes are allowed. Set one of the two, not both |
| `algorithms` | Allowed signature algorithms (default `RS256`, `ES256`). Symmetric algorithms and `none` are never accepted |

Examples:

```json
[
  {"type": "jwt", "name": "google", "issuer": "https://accounts.google.com",
   "audience": "<google-client-id>"},
  {"type": "jwt", "name": "firebase",
   "issuer": "https://securetoken.google.com/<project-id>", "audience": "<project-id>",
   "jwks_url": "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"},
  {"type": "jwt", "name": "keycloak", "issuer": "https://sso.example.com/realms/acme",
   "audience": "decision-flow"}
]
```

For Neon Auth, use the issuer, audience and JWKS URL shown in your Neon project's auth settings.

### `userinfo`: opaque tokens

For providers that issue opaque tokens instead of JWTs (GitHub). The API sends the token to the provider's user endpoint and uses the answer.

```json
{"type": "userinfo", "name": "github", "userinfo_url": "https://api.github.com/user",
 "subject_field": "id", "name_field": "login"}
```

A userinfo provider cannot check which application a token was issued for, so use it only with your own first-party app. A JWT is never sent to a userinfo endpoint.

### Several providers

The API tries `jwt` providers first, then `userinfo` ones. A client can name one with the `X-Auth-Provider` header, which avoids trying the others.

## Restrict by email domain

```
AUTH_ALLOWED_EMAIL_DOMAINS=example.com,partner.org
```

Only tokens with a **verified** email in one of these domains are accepted; anything else gets `403`. Userinfo providers never report a verified email, so the domain rule rejects them.

## Local development

`make start` runs `make auth-setup`, which appends a freshly generated key pair to your untracked `.env`. Each machine gets its own keys; nothing is shared or committed. To call the API by hand:

```
curl -H "Authorization: Bearer $(make -s auth-token)" http://localhost:8000/me
```

## Responses

| Status | Meaning |
|---|---|
| `401 unauthenticated` | Missing, malformed, expired or unknown token. Includes `WWW-Authenticate: Bearer` |
| `403 forbidden_domain` | Valid token, but the email domain is not allowed |
| `503 auth_unavailable` | The identity provider could not be reached |

`GET /me` returns the authenticated caller (`sub`, `provider`, `email`, `name`).

## Interactive docs

`/docs`, `/redoc` and `/openapi.json` list every endpoint, so they are off by default. Set `API_DOCS_ENABLED=true` to serve them for local work, and leave it unset when deployed.

## Security notes

- Treat the backend URL as public. Every request is checked, so knowing the URL gives no access beyond `/health` and `/ready`.
- Keep signing keys and client secrets in your platform's secret store, never in the repository.