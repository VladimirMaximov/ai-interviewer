import { describe, expect, it } from "vitest";

import { FaceIntegrityTracker } from "./faceIntegrity";

describe("FaceIntegrityTracker", () => {
  it("starts a missing-face interval five seconds before the loss", () => {
    const tracker = new FaceIntegrityTracker(500, 5_000);

    tracker.observe(1, 0);
    tracker.observe(0, 10_000);
    expect(tracker.observe(0, 10_500).started).toBe("face_missing");
    const result = tracker.observe(1, 14_000);

    expect(result.closed).toEqual([
      { kind: "face_missing", started_at_ms: 5_000, ended_at_ms: 14_000 },
    ]);
  });

  it("ignores a transient missed frame", () => {
    const tracker = new FaceIntegrityTracker(500, 5_000);

    tracker.observe(0, 2_000);
    const recovered = tracker.observe(1, 2_300);

    expect(recovered.closed).toEqual([]);
    expect(tracker.finish(3_000)).toEqual([]);
  });

  it("closes an active multiple-face interval when recording stops", () => {
    const tracker = new FaceIntegrityTracker(250, 5_000);

    tracker.observe(2, 7_000);
    tracker.observe(2, 7_250);

    expect(tracker.finish(9_000)).toEqual([
      { kind: "multiple_faces", started_at_ms: 2_000, ended_at_ms: 9_000 },
    ]);
  });
});
