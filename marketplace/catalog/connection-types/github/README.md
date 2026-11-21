Stores a GitHub token and sends it as a bearer token, only to `api.github.com`.

## Set up

1. In GitHub, create a personal access token (or use an app installation token) with the access your flow needs, for example issues write access on one repository.
2. Add a connection of this type and paste the token. It is stored encrypted and never shown again.
3. Pick the connection on an HTTP Request node that calls `api.github.com`.

The connection test calls `GET https://api.github.com/user`.
