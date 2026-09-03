import { useCallback, useEffect, useState } from "react";

/** Browser-native Russian TTS keeps the MVP local and requires no media vendor. */
export function useQuestionSpeech() {
  const [speaking, setSpeaking] = useState(false);

  const stop = useCallback(() => {
    window.speechSynthesis?.cancel();
    setSpeaking(false);
  }, []);

  const speak = useCallback((text: string) => {
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

  useEffect(() => stop, [stop]);
  return { speaking, speak, stop };
}
