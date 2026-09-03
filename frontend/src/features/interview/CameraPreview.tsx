import { useEffect, useRef } from "react";

export function CameraPreview({ stream }: { stream: MediaStream | null }) {
  const video = useRef<HTMLVideoElement>(null);
  useEffect(() => { if (video.current) video.current.srcObject = stream; }, [stream]);
  return <div className="camera-preview"><video ref={video} muted autoPlay playsInline aria-label="Предпросмотр камеры" /><span className="camera-preview__live">● LIVE</span></div>;
}
