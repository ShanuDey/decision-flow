import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Markdown } from "./markdown";

const html = (source: string) => renderToStaticMarkup(createElement(Markdown, null, source));

describe("Markdown", () => {
  it("renders headings, lists and code", () => {
    const out = html("# Title\n\n1. one\n2. two\n\nUse `code` here.\n\n```\nblock\n```");
    expect(out).toContain("<h2");
    expect(out).toContain("<ol");
    expect(out).toContain("<code");
    expect(out).toContain("<pre");
  });

  it("opens a web link in a new tab without giving the page access to this one", () => {
    const out = html("[docs](https://docs.github.com/rest)");
    expect(out).toContain('href="https://docs.github.com/rest"');
    expect(out).toContain('target="_blank"');
    expect(out).toContain('rel="noopener noreferrer"');
  });

  it("drops a link that is not a web or mail link", () => {
    for (const link of ["javascript:alert(1)", "data:text/html,x", "vbscript:x", "/relative", "#anchor"]) {
      expect(html(`[x](${link})`)).not.toContain(`href="${link}"`);
    }
  });

  it("does not render raw HTML", () => {
    const out = html('<script>alert(1)</script>\n\n<img src="https://t.example/p.png" onerror="x()">\n\nText');
    expect(out).not.toContain("<script");
    expect(out).not.toContain("<img");
    expect(out).not.toContain("onerror");
    expect(out).toContain("Text");
  });

  it("does not load images", () => {
    expect(html("![pixel](https://t.example/p.png)")).not.toContain("<img");
  });
});
