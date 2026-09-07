import { describe, expect, it } from "vitest";

import { AudioRecorder } from "./AudioRecorder";
import { RECORDING_CHUNK_MS } from "./useContinuousRecorder";
import {
  codingAnswerIsReady,
  hasRecordedInterval,
  shouldAutoSubmit,
  stopMediaTracks,
} from "./recordingPolicy";

describe("AudioRecorder", () => {
  it("exports the browser recording component", () => {
    expect(AudioRecorder).toBeTypeOf("function");
  });

  it("keeps the bounded continuous upload interval at ten seconds", () => {
    expect(RECORDING_CHUNK_MS).toBe(10_000);
  });

  it("accepts only forward recording boundaries", () => {
    expect(hasRecordedInterval(10_000, 14_000)).toBe(true);
    expect(hasRecordedInterval(14_000, 14_000)).toBe(false);
  });

  it("auto-submits once when a question reaches its limit", () => {
    expect(shouldAutoSubmit(60, 5_000, 65_000, false)).toBe(true);
    expect(shouldAutoSubmit(60, 5_000, 65_000, true)).toBe(false);
    expect(shouldAutoSubmit(null, 5_000, 500_000, false)).toBe(false);
  });

  it("requires code only for coding questions", () => {
    expect(codingAnswerIsReady("spoken", "")).toBe(true);
    expect(codingAnswerIsReady("coding", "  ")).toBe(false);
    expect(codingAnswerIsReady("coding", "return 1")).toBe(true);
  });

  it("releases every camera and microphone track", () => {
    let stopped = 0;
    const stream = { getTracks: () => [{ stop: () => stopped++ }, { stop: () => stopped++ }] } as unknown as MediaStream;
    stopMediaTracks(stream);
    expect(stopped).toBe(2);
  });
});
