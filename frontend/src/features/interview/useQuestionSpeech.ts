import { useCallback, useEffect, useRef, useState } from "react";

/** Browser-native Russian TTS keeps the MVP local and requires no media vendor. */
export function useQuestionSpeech() {
  const [speaking, setSpeaking] = useState(false);
  const audio = useRef<HTMLAudioElement | null>(null);

  const stop = useCallback(() => {
    window.speechSynthesis?.cancel();
    audio.current?.pause();
    audio.current = null;
    setSpeaking(false);
  }, []);

  const browserSpeech = useCallback((text: string) => {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "ru-RU";
    utterance.rate = 0.95;
    utterance.onstart = () => setSpeaking(true);
    utterance.onend = utterance.onerror = () => setSpeaking(false);
    const voice = window.speechSynthesis.getVoices().find((item) => item.lang.toLowerCase().startsWith("ru"));
    if (voice) utterance.voice = voice;
    window.speechSynthesis.speak(utterance);
  }, []);

  const speak = useCallback(async (text: string, speechUrl?: string) => {
    stop();
    if (speechUrl) {
      try {
        const response = await fetch(speechUrl);
        if (!response.ok) throw new Error("Local TTS is unavailable");
        const url = URL.createObjectURL(await response.blob());
        const player = new Audio(url);
        audio.current = player;
        player.onplay = () => setSpeaking(true);
        player.onended = player.onerror = () => {
          URL.revokeObjectURL(url);
          if (audio.current === player) audio.current = null;
          setSpeaking(false);
        };
        await player.play();
        return;
      } catch {
        // A local TTS outage must never prevent the interview from continuing.
      }
    }
    browserSpeech(text);
  }, [browserSpeech, stop]);

  useEffect(() => stop, [stop]);
  return { speaking, speak, stop };
}
