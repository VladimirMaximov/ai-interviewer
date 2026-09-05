import { useEffect, useRef, useState } from "react";

export function useInterviewMediaStream(enabled: boolean, initialStream: MediaStream | null = null) {
  const [stream, setStream] = useState<MediaStream | null>(initialStream);
  const [error, setError] = useState<string | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const stop = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setStream(null);
  };
  useEffect(() => {
    if (!enabled) return;
    if (initialStream) { streamRef.current = initialStream; setStream(initialStream); return; }
    let active = true;
    navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 15, max: 15 } },
      audio: true,
    }).then((value) => {
      if (active) { streamRef.current = value; setStream(value); } else value.getTracks().forEach((track) => track.stop());
    }).catch(() => active && setError("Не удалось получить доступ к камере и микрофону."));
    return () => { active = false; stop(); };
  }, [enabled, initialStream]);
  return { stream, error, stop };
}
