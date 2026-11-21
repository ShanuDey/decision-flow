---
title: "Marketplace"
---

The Marketplace lists connection types and request templates you can add to a workspace. Each one is a small file of settings. It holds no code and no credentials.

## Install something

1. Open **Marketplace** in the sidebar, or choose **Browse the Marketplace** in the Add connection list or the HTTP Request node's template list. Those links open it on top of what you are doing.
2. Search, or filter by **Connections** or **Templates**.
3. Choose **Install**.

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

## What this server offers

Which items work on a server depends on its settings. A server that turns off the HTTP Request node (`DISABLED_NODE_TYPES`) does not offer request templates, and one with an allowed-host list (`HTTP_ALLOWED_HOSTS`) leaves out templates it could not run.
