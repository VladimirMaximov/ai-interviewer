export function hasRecordedInterval(startOffsetMs: number, endOffsetMs: number): boolean {
  return startOffsetMs >= 0 && endOffsetMs > startOffsetMs;
}

export function shouldAutoSubmit(
  limitSeconds: number | null,
  answerStartedAtMs: number,
  currentOffsetMs: number,
  alreadySubmitted: boolean,
): boolean {
  return Boolean(
    limitSeconds
      && !alreadySubmitted
      && currentOffsetMs - answerStartedAtMs >= limitSeconds * 1000,
  );
}

export function codingAnswerIsReady(kind: "spoken" | "coding", source: string): boolean {
  return kind !== "coding" || source.trim().length > 0;
}

export function stopMediaTracks(stream: MediaStream | null): void {
  stream?.getTracks().forEach((track) => track.stop());
}
