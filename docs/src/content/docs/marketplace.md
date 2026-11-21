---
title: "Marketplace"
---

The Marketplace lists connection types and request templates you can add to a workspace. Each one is a small file of settings. It holds no code and no credentials.

## Install something

1. Open **Marketplace** in the sidebar, or choose **Browse the Marketplace** in the Add connection list or the HTTP Request node's template list. Those links open it on top of what you are doing.
2. Search, or filter by **Connections** or **Templates**. Search looks at names, descriptions and tags, matches the start of a word, forgives a small typo, and lists the best matches first.
3. Choose **Details** on a card to read its notes, such as how to get a token or what the connection test calls. The notes show as plain text and links only, with no images or scripts. Choose **Install** on the card or in the details.

Installing copies the item into your workspace. It then appears under **Installed** in the pickers:

- An installed **connection type** is offered when you add a connection, next to the built-in ones.
- An installed **template** is offered under **Use a template** in an HTTP Request node. See [Start from a request template](nodes/http-request#start-from-a-request-template).

A template can need a connection type. Installing the template installs that type too, and the card says so ("Also installs GitHub").

## Open it from these docs

The catalog pages have an **Open in your app** button. The first time, enter the address of your own Decision Flow app, such as `https://flows.example.com`. It is saved in this browser only and is never sent anywhere. After that the button goes straight to your app. To change the address, choose **Use a different app address** under the button.

When you read these docs from inside the app, there is nothing to enter: the button already opens that app.

## Update or remove

When the Marketplace lists a newer version of something you installed, its card shows **Update**. Choose it to replace your copy.

**Remove** takes an item out of the workspace. Things you already made from it keep their settings, because applying a template copies it. You cannot remove a connection type while connections of that type exist, or while an installed template needs it. The error says which.

## Where the list comes from

The list is read from a public folder on GitHub (see `CATALOG_URL` in [configuration](configuration#marketplace-source)), so it can change without upgrading the app. The page shows when the list was last updated and has a **Refresh** button. If the list cannot be loaded, the Marketplace says it is unavailable; items you installed keep working. The full list is also on the [catalog pages](catalog).

## Health checks

Every night the project reads the published list the way your server does: it fetches each file, checks it against the list, and checks that the current version of the app can still read it. An item that fails two nights in a row is marked **Broken**.

- A broken item shows a **Broken** badge and the reason, and **Install** and **Update** are paused for it, and for any template that needs it. The server checks again when you install, so a stale page cannot get around it.
- Something you already installed keeps working. Its card says the item is reported broken upstream, and **Remove** is still available.
- It clears by itself: the first night an item passes again, the badge goes away.
- If the report cannot be reached, is older than three days, or is switched off, every item is shown as healthy. A missing report never blocks an install.

A server that uses its own `CATALOG_URL` does not read this project's report. See `CATALOG_HEALTH_URL` in [configuration](configuration#marketplace-source) to use one of your own.

## What this server offers

Which items work on a server depends on its settings. A server that turns off the HTTP Request node (`DISABLED_NODE_TYPES`) does not offer request templates, and one with an allowed-host list (`HTTP_ALLOWED_HOSTS`) leaves out templates it could not run.
