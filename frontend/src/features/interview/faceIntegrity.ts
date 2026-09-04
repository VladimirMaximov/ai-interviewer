export type FaceConditionKind = "face_missing" | "multiple_faces";
export type BrowserMonitoringKind =
  | FaceConditionKind
  | "face_detection_unavailable";

export type FaceIntegrityEvent = {
  kind: FaceConditionKind;
  started_at_ms: number;
  ended_at_ms: number;
  confidence?: number;
};

export type FaceIntegrityChange = {
  started?: FaceConditionKind;
  closed: FaceIntegrityEvent[];
};

type PendingCondition = { kind: FaceConditionKind; sinceMs: number };
type ActiveCondition = { kind: FaceConditionKind; observedAtMs: number };

/** Debounce frame-level detections and apply the required five-second pre-roll. */
export class FaceIntegrityTracker {
  private pending: PendingCondition | null = null;
  private active: ActiveCondition | null = null;

  constructor(
    private readonly graceMs = 750,
    private readonly preRollMs = 5_000,
  ) {}

  observe(faceCount: number, elapsedMs: number): FaceIntegrityChange {
    const kind = this.kindFor(faceCount);
    const closed: FaceIntegrityEvent[] = [];

    if (this.active && this.active.kind !== kind) {
      closed.push(this.closeActive(elapsedMs));
    }
    if (kind === null) {
      this.pending = null;
      return { closed };
    }
    if (this.active?.kind === kind) return { closed };

    if (this.pending?.kind !== kind) {
      this.pending = { kind, sinceMs: elapsedMs };
      return { closed };
    }
    if (elapsedMs - this.pending.sinceMs < this.graceMs) return { closed };

    this.active = {
      kind,
      observedAtMs: this.pending.sinceMs,
    };
    this.pending = null;
    return { started: kind, closed };
  }

  finish(elapsedMs: number): FaceIntegrityEvent[] {
    this.pending = null;
    return this.active ? [this.closeActive(elapsedMs)] : [];
  }

  reset() {
    this.pending = null;
    this.active = null;
  }

  private closeActive(elapsedMs: number): FaceIntegrityEvent {
    const active = this.active!;
    this.active = null;
    return {
      kind: active.kind,
      started_at_ms: Math.max(0, Math.round(active.observedAtMs - this.preRollMs)),
      ended_at_ms: Math.max(
        Math.round(active.observedAtMs + 1),
        Math.round(elapsedMs),
      ),
    };
  }

  private kindFor(faceCount: number): FaceConditionKind | null {
    if (faceCount === 0) return "face_missing";
    if (faceCount > 1) return "multiple_faces";
    return null;
  }
}
