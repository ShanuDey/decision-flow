Stores a Slack bot token and sends it as a bearer token, only to `slack.com`.

## Set up

1. Create a Slack app and add the bot scope your flow needs, for example `chat:write`.
2. Install the app in your workspace and copy the bot token (it starts with `xoxb-`).
3. Add a connection of this type and paste the token. It is stored encrypted and never shown again.
4. Invite the bot to any channel it should post in.
