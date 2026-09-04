type ConsentScreenProps = { onAccept: () => Promise<void> };

export function ConsentScreen({ onAccept }: ConsentScreenProps) {
  return <main><h1>Техническое интервью</h1><p>Записи ответов будут сохранены для команды найма и преобразованы в текст.</p><button onClick={() => void onAccept()}>Согласен начать</button></main>;
}
