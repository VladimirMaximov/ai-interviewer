import { describe, expect, it } from "vitest";

import { AudioRecorder } from "./AudioRecorder";

describe("AudioRecorder", () => {
  it("exports the browser recording component", () => {
    expect(AudioRecorder).toBeTypeOf("function");
  });
});
