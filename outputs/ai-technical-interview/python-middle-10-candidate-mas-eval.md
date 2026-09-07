# Полный MAS-прогон: 10 synthetic-кандидатов на Python Middle+

- Дата: `2026-09-06T13:57:44.990996+00:00`
- Данные: `synthetic`; реальные аккаунты и персональные данные не использовались
- Модель всех LLM-агентов: `openai/gpt-4.1-mini` через VseGPT
- Dataset hash: `8ac0a7d2cfe5f16aa72de648cac19c62cb964f7b05890fb5723d84bd204efa2b`
- Завершили полный конвейер: **0/10**
- Целевая accuracy: **≥ 80%**
- Полученная accuracy: **0%** (0/10)
- Macro-F1: **0.000**
- Цель достигнута: **нет**

> `Подходит / не подходит / следует уточнить` — тестовая проекция по зафиксированному правилу, а не автоматическое решение о найме. Финальный профиль, рейтинг и фидбэк остаются отдельными артефактами; фидбэк не публикуется без проверки человеком.

## Итоговая таблица

| ID | Synthetic-профиль | Эталон | MAS-прогноз | Верно | Балл / 10 | Tech | Fit | Покрытие | Вопросы | Уточнения | Feedback |
|---|---|---|---|:---:|---:|---:|---:|---:|---:|---:|---|
| PY-001 | Сильный event-driven backend | подходит | — | ✗ | — | — | — | — | — | — | failed |
| PY-002 | Django/FastAPI platform engineer | подходит | — | ✗ | — | — | — | — | — | — | failed |
| PY-003 | Высоконагруженные интеграции | подходит | — | ✗ | — | — | — | — | — | — | failed |
| PY-004 | Надёжные Python-микросервисы | подходит | — | ✗ | — | — | — | — | — | — | failed |
| PY-005 | Начинающий разработчик с ошибками в надёжности | не подходит | — | ✗ | — | — | — | — | — | — | failed |
| PY-006 | Frontend/PHP профиль без Python production | не подходит | — | ✗ | — | — | — | — | — | — | failed |
| PY-007 | Data analyst без backend-инженерии | не подходит | — | ✗ | — | — | — | — | — | — | failed |
| PY-008 | Сильные заявления без деталей | следует уточнить | — | ✗ | — | — | — | — | — | — | failed |
| PY-009 | Смежный RabbitMQ/Docker опыт | следует уточнить | — | ✗ | — | — | — | — | — | — | failed |
| PY-010 | Неподтверждённые заявления резюме | следует уточнить | — | ✗ | — | — | — | — | — | — | failed |

## Метрики классификации

- Accuracy: **0.0%**.
- Macro-F1: **0.000**.
- Recall класса `следует уточнить`: **0.0%**.
- Ложное продвижение `не подходит → подходит`: **0**.
- Ложный отсев `подходит → не подходит`: **0**.

Строки confusion matrix — эталон, столбцы — MAS-прогноз:

```json
{
  "подходит": {
    "подходит": 0,
    "не подходит": 0,
    "следует уточнить": 0
  },
  "не подходит": {
    "подходит": 0,
    "не подходит": 0,
    "следует уточнить": 0
  },
  "следует уточнить": {
    "подходит": 0,
    "не подходит": 0,
    "следует уточнить": 0
  }
}
```

## Уточняющие вопросы

- Сессий с уточнением: **0**.
- Максимум уточнений в одной сессии: **0**.
- Ограничение 1–2 соблюдено: **да**.
- Precision/recall ниже сравнивают сам факт уточнения с заранее помеченной неоднозначностью профиля; это диагностическая, а не hiring-метрика.
- Follow-up precision: **не определён**.
- Follow-up recall: **0.0%**.
- Сессий с live coding: **0**.

## Фактические вызовы MAS и стоимость

- LLM-вызовов: **83**; неуспешных попыток: **65**.
- По ролям: `{"alternative_vacancy_match":1,"answer_assessment":8,"candidate_feedback":7,"integrity_check":1,"question_plan":2,"resume_relevance":64}`.
- Оценённый вход: **1,595,346** символов.
- Фактический JSON-выход: **74,239** символов.
- Расчётная стоимость: **113.54 ₽** по тарифу 0,06/0,24 ₽ за 1000 входных/выходных символов.
- Это расчёт по объёму запросов; окончательное списание нужно сверять в активности VseGPT.

## Методика и ограничения

- Каждая строка — отдельная локальная synthetic-заявка с приглашением, резюме, интервью-сессией и артефактами агентов.
- Полный путь: resume relevance → question plan → answer assessment → conditional follow-up/live coding → integrity → conditional alternative vacancy match → candidate feedback draft.
- План ограничен 0 персонализированным вопросом; четыре сопоставимых baseline-вопроса сохранены.
- Классификация берётся только из оценки отдельного baseline-вопроса о соответствии вакансии: decisive negative имеет приоритет, пробелы ведут к `следует уточнить`, подтверждённые technical и vacancy-fit — к `подходит`.
- Датасет использовался в предыдущей калибровке правила, поэтому это регрессионная проверка, не независимый holdout и не доказательство качества на реальных кандидатах.
- Synthetic-интервью не являются customer validation. Для продуктовой метрики нужен отдельный замороженный holdout и слепая разметка минимум двумя техническими интервьюерами.

## Уточняющие вопросы по кандидатам

## Ошибки незавершённых заявок

```json
[
  {
    "candidate_id": "PY-001",
    "errors": [
      "MultiAgentProviderError: candidate_feedback provider request failed",
      "BadRequestError: Error code: 400 - {'error': {'message': \"You have only -2.050900 on account - it's equal to 0 or below it. Please, add some money to balance to proceed: https://vsegpt.ru/User/Money (6518132148)\", 'code': 400}}",
      "HTTPStatusError: Client error '400 Bad Request' for url 'https://api.vsegpt.ru/v1/chat/completions'\nFor more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/400"
    ]
  },
  {
    "candidate_id": "PY-002",
    "errors": [
      "MultiAgentProviderError: resume_relevance provider request failed",
      "BadRequestError: Error code: 400 - {'error': {'message': \"You have only -2.050900 on account - it's equal to 0 or below it. Please, add some money to balance to proceed: https://vsegpt.ru/User/Money (6518132148)\", 'code': 400}}",
      "HTTPStatusError: Client error '400 Bad Request' for url 'https://api.vsegpt.ru/v1/chat/completions'\nFor more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/400"
    ]
  },
  {
    "candidate_id": "PY-003",
    "errors": [
      "MultiAgentProviderError: resume_relevance provider request failed",
      "BadRequestError: Error code: 400 - {'error': {'message': \"You have only -2.050900 on account - it's equal to 0 or below it. Please, add some money to balance to proceed: https://vsegpt.ru/User/Money (6518132148)\", 'code': 400}}",
      "HTTPStatusError: Client error '400 Bad Request' for url 'https://api.vsegpt.ru/v1/chat/completions'\nFor more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/400"
    ]
  },
  {
    "candidate_id": "PY-004",
    "errors": [
      "MultiAgentProviderError: resume_relevance provider request failed",
      "BadRequestError: Error code: 400 - {'error': {'message': \"You have only -2.050900 on account - it's equal to 0 or below it. Please, add some money to balance to proceed: https://vsegpt.ru/User/Money (6518132148)\", 'code': 400}}",
      "HTTPStatusError: Client error '400 Bad Request' for url 'https://api.vsegpt.ru/v1/chat/completions'\nFor more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/400"
    ]
  },
  {
    "candidate_id": "PY-005",
    "errors": [
      "MultiAgentProviderError: resume_relevance provider request failed",
      "BadRequestError: Error code: 400 - {'error': {'message': \"You have only -2.050900 on account - it's equal to 0 or below it. Please, add some money to balance to proceed: https://vsegpt.ru/User/Money (6518132148)\", 'code': 400}}",
      "HTTPStatusError: Client error '400 Bad Request' for url 'https://api.vsegpt.ru/v1/chat/completions'\nFor more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/400"
    ]
  },
  {
    "candidate_id": "PY-006",
    "errors": [
      "MultiAgentProviderError: resume_relevance provider request failed",
      "BadRequestError: Error code: 400 - {'error': {'message': \"You have only -2.050900 on account - it's equal to 0 or below it. Please, add some money to balance to proceed: https://vsegpt.ru/User/Money (6518132148)\", 'code': 400}}",
      "HTTPStatusError: Client error '400 Bad Request' for url 'https://api.vsegpt.ru/v1/chat/completions'\nFor more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/400"
    ]
  },
  {
    "candidate_id": "PY-007",
    "errors": [
      "MultiAgentProviderError: resume_relevance provider request failed",
      "BadRequestError: Error code: 400 - {'error': {'message': \"You have only -2.050900 on account - it's equal to 0 or below it. Please, add some money to balance to proceed: https://vsegpt.ru/User/Money (6518132148)\", 'code': 400}}",
      "HTTPStatusError: Client error '400 Bad Request' for url 'https://api.vsegpt.ru/v1/chat/completions'\nFor more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/400"
    ]
  },
  {
    "candidate_id": "PY-008",
    "errors": [
      "MultiAgentProviderError: resume_relevance provider request failed",
      "BadRequestError: Error code: 400 - {'error': {'message': \"You have only -2.050900 on account - it's equal to 0 or below it. Please, add some money to balance to proceed: https://vsegpt.ru/User/Money (6518132148)\", 'code': 400}}",
      "HTTPStatusError: Client error '400 Bad Request' for url 'https://api.vsegpt.ru/v1/chat/completions'\nFor more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/400"
    ]
  },
  {
    "candidate_id": "PY-009",
    "errors": [
      "MultiAgentProviderError: resume_relevance provider request failed",
      "BadRequestError: Error code: 400 - {'error': {'message': \"You have only -2.050900 on account - it's equal to 0 or below it. Please, add some money to balance to proceed: https://vsegpt.ru/User/Money (6518132148)\", 'code': 400}}",
      "HTTPStatusError: Client error '400 Bad Request' for url 'https://api.vsegpt.ru/v1/chat/completions'\nFor more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/400"
    ]
  },
  {
    "candidate_id": "PY-010",
    "errors": [
      "MultiAgentProviderError: resume_relevance provider request failed",
      "BadRequestError: Error code: 400 - {'error': {'message': \"You have only -2.050900 on account - it's equal to 0 or below it. Please, add some money to balance to proceed: https://vsegpt.ru/User/Money (6518132148)\", 'code': 400}}",
      "HTTPStatusError: Client error '400 Bad Request' for url 'https://api.vsegpt.ru/v1/chat/completions'\nFor more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/400"
    ]
  }
]
```

