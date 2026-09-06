import { useCallback, useEffect, useRef, useState } from "react";

/** Browser-native Russian TTS keeps the MVP local and requires no media vendor. */
export function useQuestionSpeech() {
  const [speaking, setSpeaking] = useState(false);
  const audio = useRef<HTMLAudioElement | null>(null);
  const finishSpeaking = useRef<(() => void) | null>(null);

  const finish = useCallback(() => {
    finishSpeaking.current?.();
    finishSpeaking.current = null;
    setSpeaking(false);
  }, []);

  const stop = useCallback(() => {
    window.speechSynthesis?.cancel();
    audio.current?.pause();
    audio.current = null;
    finish();
  }, [finish]);

  const browserSpeech = useCallback((text: string): Promise<void> => {
    if (!("speechSynthesis" in window)) return Promise.resolve();
    window.speechSynthesis.cancel();
    return new Promise((resolve) => {
      finishSpeaking.current = resolve;
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "ru-RU";
      utterance.rate = 0.95;
      utterance.onstart = () => setSpeaking(true);
      utterance.onend = utterance.onerror = finish;
      const voice = window.speechSynthesis.getVoices().find((item) => item.lang.toLowerCase().startsWith("ru"));
      if (voice) utterance.voice = voice;
      window.speechSynthesis.speak(utterance);
    });
  }, [finish]);

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
        await new Promise<void>((resolve, reject) => {
          finishSpeaking.current = resolve;
          player.onended = () => {
            URL.revokeObjectURL(url);
            if (audio.current === player) audio.current = null;
            finish();
          };
          player.onerror = () => {
            URL.revokeObjectURL(url);
            if (audio.current === player) audio.current = null;
            finishSpeaking.current = null;
            setSpeaking(false);
            reject(new Error("Local TTS playback failed"));
          };
          void player.play().catch(reject);
        });
        return;
      } catch {
        // A local TTS outage must never prevent the interview from continuing.
      }
    }
    await browserSpeech(text);
  }, [browserSpeech, finish, stop]);

  useEffect(() => stop, [stop]);
  return { speaking, speak, stop };
}
