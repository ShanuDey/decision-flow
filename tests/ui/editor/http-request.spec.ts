import { baseURL } from "../../support/env";
import { addNode, settingsPanel } from "../../support/editor";
import { expect, test } from "../../support/fixtures";

const sameOrigin = { origin: baseURL };

test.beforeEach(async ({ editor }) => {
  await addNode(editor, "http", /HTTP Request/);
});

test("the node is in the picker and opens its settings with a GET and no body", async ({ editor }) => {
  const panel = settingsPanel(editor);
  await expect(panel.getByRole("heading", { name: "HTTP Request", level: 2 })).toBeVisible();
  await expect(panel.getByRole("heading", { name: "Request", level: 3 })).toBeVisible();
  await expect(panel.getByLabel("URL", { exact: true })).toHaveValue("");
  await expect(panel.getByRole("button", { name: "Add header" })).toBeVisible();
  await expect(panel.getByRole("button", { name: "Add parameter" })).toBeVisible();
});

test("the URL and a header row are typed into the node card", async ({ editor }) => {
  const panel = settingsPanel(editor);
  await panel.getByLabel("URL", { exact: true }).fill("https://api.example.com/score");
  await expect(editor.locator(".react-flow__node", { hasText: "api.example.com/score" })).toBeVisible();

  await panel.getByRole("button", { name: "Add header" }).click();
  await panel.getByLabel("Name").first().fill("Accept");
  await panel.getByLabel("Value").first().fill("application/json");
  await expect(panel.getByLabel("Name").first()).toHaveValue("Accept");
});

test("a repeated or invalid header name is flagged and not saved", async ({ editor }) => {
  const panel = settingsPanel(editor);
  await panel.getByRole("button", { name: "Add header" }).click();
  await panel.getByRole("button", { name: "Add header" }).click();
  await panel.getByLabel("Name").nth(0).fill("Accept");
  await panel.getByLabel("Name").nth(1).fill("accept");
  await expect(panel.getByText("This name is already used")).toBeVisible();

  await panel.getByLabel("Name").nth(1).fill("Bad Header");
  await expect(panel.getByText("Not a valid header name")).toBeVisible();
});

test("a JSON body that is not valid says so", async ({ editor }) => {
  const panel = settingsPanel(editor);
  await panel.getByLabel("Body type").click();
  await editor.getByRole("option", { name: "JSON" }).click();
  await panel.getByLabel("JSON body").fill('{ "a": ');
  await expect(panel.getByText(/The last valid body is kept/)).toBeVisible();
  await panel.getByLabel("JSON body").fill('{ "a": "{{ input.x }}" }');
  await expect(panel.getByText(/The last valid body is kept/)).toHaveCount(0);
});

test("a body on a GET request is flagged", async ({ editor }) => {
  const panel = settingsPanel(editor);
  await panel.getByLabel("Body type").click();
  await editor.getByRole("option", { name: "Text" }).click();
  await expect(panel.getByText(/A GET request cannot have a body/)).toBeVisible();
});

test("without secrets, quick setup points to Settings", async ({ editor }) => {
  const panel = settingsPanel(editor);
  await expect(panel.getByText("Quick setup")).toBeVisible();
  await expect(panel.getByRole("link", { name: "Add one in Settings" })).toHaveAttribute(
    "href",
    /\/settings\/secrets\?from=\/flows\//,
  );
});

test("with a saved secret, quick setup adds a bearer header that uses its name", async ({
  editor,
  request,
  flow,
}) => {
  const name = "E2E_HTTP_KEY";
  const saved = await request.put(`/backend/secrets/${name}`, {
    data: { value: "e2e-value-12345" },
    headers: sameOrigin,
  });
  test.skip(saved.status() === 503, "ENCRYPTION_KEY is not set on this stack");
  expect(saved.status()).toBe(200);
  try {
    await editor.goto(flow.url);
    await addNode(editor, "http", /HTTP Request/);
    const panel = settingsPanel(editor);
    await panel.getByRole("button", { name: "Add bearer token" }).click();
    await expect(panel.getByLabel("Name").first()).toHaveValue("Authorization");
    await expect(panel.getByLabel("Value").first()).toHaveValue(`Bearer {{ secrets.${name} }}`);
    await expect(panel.getByText("e2e-value-12345")).toHaveCount(0);
  } finally {
    await request.delete(`/backend/secrets/${name}`, { headers: sameOrigin });
  }
});
