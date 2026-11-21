---
title: "Export and import a flow"
---

You can save a flow as a file and bring it into another workspace, or share it with someone else.

## Export

In the editor, open **More actions** and choose **Export as file**. You get a `.flow.json` file with the flow's name and its draft graph. It holds no secret values and no credentials.

## Import

In **New flow**, choose **Import file** and pick a `.flow.json` file. You get a new flow with its own copy of the graph, named as in the file (or after the file's name if it has none). Files over 5 MB are refused. A file made by a newer version of the app is refused too, with a message saying so.

Some things point at your workspace and cannot travel in a file, so the import clears them and tells you:

- **Subflow nodes** lose the flow they call. Pick the flow again in each one.
- **Connections** are matched as described below.
- **Secrets** are not in the file. A template such as `{{ secrets.API_KEY }}` still refers to a secret by name, so create a secret with that name in the new workspace.

## Connections

A request node that signs its request with a [connection](connections) refers to it by an id that only exists in the workspace that made the file. The file also records each connection's type and name, never its credentials or its hosts.

When a file uses connections you don't have, a **Match connections** window lists each one with how many nodes use it. For each, choose one of your connections of that type, or leave it empty and pick later. If you have a connection of the same type and name, or only one of that type, it is selected for you. Nothing is applied until you choose **Import flow**.

Matching is never automatic, because a connection carries your credentials. A flow you imported should not get them without you saying so.

If you have no connection of that type, the window says so. Add one under **Connections**, or install its type from the [Marketplace](marketplace) first, then import the file again.

A node you leave empty has no connection. Pick one in the node's settings before running the flow.
