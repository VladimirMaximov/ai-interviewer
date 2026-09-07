import { FaceDetector, FilesetResolver } from "@mediapipe/tasks-vision";
import { useEffect, useRef } from "react";

import { BrowserMonitoringEventKind } from "../../api/candidate";

export type FaceInterval = {
  kind: BrowserMonitoringEventKind;
  started_at_ms: number;
  ended_at_ms: number;
};

const WASM_URL = import.meta.env.VITE_MEDIAPIPE_WASM_URL
  ?? "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/wasm";
const MODEL_URL = import.meta.env.VITE_FACE_DETECTOR_MODEL_URL
  ?? "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite";

export function useFaceIntegrityMonitor(
  stream: MediaStream | null,
  recording: boolean,
  offset: () => number,
) {
  const detectorRef = useRef<FaceDetector | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const intervalsRef = useRef<FaceInterval[]>([]);
  const activeRef = useRef<{ kind: BrowserMonitoringEventKind; since: number } | null>(null);
  const pendingRef = useRef<{ kind: BrowserMonitoringEventKind; since: number } | null>(null);
  const availableRef = useRef(true);
  const offsetRef = useRef(offset);
  offsetRef.current = offset;

  useEffect(() => {
    if (!stream || !recording) return;
    let cancelled = false;
    let frame = 0;
    let lastDetection = 0;
    const video = document.createElement("video");
    video.muted = true;
    video.playsInline = true;
    video.srcObject = stream;
    videoRef.current = video;

    const observe = (count: number, at: number) => {
      const kind = count === 0 ? "face_missing" : count > 1 ? "multiple_faces" : null;
      const active = activeRef.current;
      if (active && active.kind !== kind) {
        intervalsRef.current.push({ kind: active.kind, started_at_ms: active.since, ended_at_ms: Math.max(active.since + 1, at) });
        activeRef.current = null;
      }
      if (!kind) { pendingRef.current = null; return; }
      if (activeRef.current?.kind === kind) return;
      if (pendingRef.current?.kind !== kind) { pendingRef.current = { kind, since: at }; return; }
      if (at - pendingRef.current.since >= 700) {
        activeRef.current = { kind, since: pendingRef.current.since };
        pendingRef.current = null;
      }
    };

    const start = async () => {
      try {
        await video.play();
        const fileset = await FilesetResolver.forVisionTasks(WASM_URL);
        detectorRef.current = await FaceDetector.createFromOptions(fileset, {
          baseOptions: { modelAssetPath: MODEL_URL }, runningMode: "VIDEO",
          minDetectionConfidence: 0.35, minSuppressionThreshold: 0.2,
        });
        const scan = (now: number) => {
          if (cancelled) return;
          if (now - lastDetection >= 300 && video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
            lastDetection = now;
            try { observe(detectorRef.current!.detectForVideo(video, now).detections.length, offsetRef.current()); }
            catch { availableRef.current = false; }
          }
          frame = requestAnimationFrame(scan);
        };
        frame = requestAnimationFrame(scan);
      } catch {
        availableRef.current = false;
      }
    };
    void start();
    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
      detectorRef.current?.close();
      detectorRef.current = null;
      video.srcObject = null;
    };
  }, [recording, stream]);

  const takeForAnswer = (startedAt: number, endedAt: number): FaceInterval[] => {
    if (!availableRef.current) return [{ kind: "face_detection_unavailable", started_at_ms: startedAt, ended_at_ms: Math.max(startedAt + 1, endedAt) }];
    const active = activeRef.current;
    const all = [...intervalsRef.current];
    intervalsRef.current = [];
    if (active) {
      all.push({ kind: active.kind, started_at_ms: active.since, ended_at_ms: Math.max(active.since + 1, endedAt) });
      activeRef.current = { ...active, since: endedAt };
    }
    return all
      .filter((item) => item.ended_at_ms > startedAt && item.started_at_ms < endedAt)
      .map((item) => ({ ...item, started_at_ms: Math.max(startedAt, item.started_at_ms), ended_at_ms: Math.min(endedAt, item.ended_at_ms) }));
  };

  return { takeForAnswer };
}
