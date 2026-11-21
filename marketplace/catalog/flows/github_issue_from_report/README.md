Creates an issue in a GitHub repository and returns its `number` and `url`.

## Use

1. Install the flow. It installs the GitHub connection type with it.
2. Create a GitHub connection with a token that may create issues in the repository, then start a new flow from this one and match the connection when asked.
3. Run it with `owner`, `repo`, `title` and, optionally, `body`.

The run fails when GitHub answers with an error status, such as 404 for a repository the token cannot see.
