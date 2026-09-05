import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { LiveCodingEditor } from "./LiveCodingEditor";

describe("LiveCodingEditor", () => {
  it("renders one code editor and explains that the solution is scored", () => {
    const html = renderToStaticMarkup(
      <LiveCodingEditor
        prompt="Реализуйте функцию unique."
        onSubmit={async () => undefined}
      />,
    );

    expect(html.match(/<textarea/g)).toHaveLength(1);
    expect(html).toContain("Решение будет оценено");
    expect(html).toContain("Реализуйте функцию unique.");
  });
});
