---
title: "Flow templates"
---

A flow template is a ready-made flow you can start from. Pick one in **New flow**, name it, and you get your own draft copy to change however you like. The template itself never changes, and your copy does not follow later updates to it.

The list shows each template's inputs and outputs and a preview of its graph. Search matches the title, summary and description, and you can narrow the list by category.

Creating a flow from a template counts toward your flow limit like any other flow (see [Limits](limits)).

## Built-in templates

| Template | Shows |
|---|---|
| Loan eligibility | A condition that splits into approve and decline |
| Lead scoring | Two conditions in a row giving three outcomes |
| Discount tier | A decision that depends on two inputs |
| Look up a record from an API | An [HTTP Request](nodes/http-request) node, reading its response in the End node, and failing the run on an error status. It calls the free JSONPlaceholder test API |

## Adding a template

Built-in templates are JSON files in `api/app/templates/data/`. Each file holds an `id`, `title`, `summary`, `description`, `category` and a `draft` (the same graph format the editor saves). Inputs, outputs and node types shown in the picker are read from the draft.

The API checks every template when it first loads them, and a test checks that each one is a valid flow within the default limits. An invalid template stops the server from listing templates, so run the API tests after adding one.

`GET /templates` returns the list. It needs sign-in, as other routes do.
