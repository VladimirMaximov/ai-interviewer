export const COMPLETION_TITLE = "Интервью записано";
export const COMPLETION_BODY = "Спасибо за ответы. Видео, аудио и материалы coding-задач сохранены.";
export const COMPLETION_NEXT_STEP = "Ожидайте дальнейшей информации от рекрутера.";

export function initialInterviewMessage(hasGrantedStream: boolean): string {
  return hasGrantedStream
    ? "Подготавливаем защищённую запись и первый вопрос…"
    : "Подготавливаем камеру и микрофон…";
}

export function shouldShowQuestion(recording: boolean): boolean {
  return recording;
}
