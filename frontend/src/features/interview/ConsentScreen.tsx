type ConsentScreenProps = { onAccept: () => Promise<void> };

export function ConsentScreen({ onAccept }: ConsentScreenProps) {
  return <main><h1>Техническое интервью</h1><p>Записи ответов будут сохранены для команды найма и преобразованы в текст.</p><p>Во время интервью сохраняются технические события: уход страницы в фон, возврат и факт копирования внутри страницы. Содержимое буфера обмена не читается; эти события не принимают решений автоматически.</p><button onClick={() => void onAccept()}>Согласен начать</button></main>;
}
