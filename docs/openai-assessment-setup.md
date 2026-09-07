# Подключение GPT для оценки интервью

В основном `interview_platform` оценка выполняется через OpenAI Responses API. Один запрос к
модели получает утверждённые критерии компетенций, связанные с ними вопросы и текстовые ответы
одного кандидата. Модель возвращает criterion assessments и итоговую рекомендацию `1/0/-1` через
строгий JSON Schema. Локальный код повторно проверяет идентификаторы и дословность всех цитат до
сохранения результата.

Официальные материалы OpenAI:

- [первый API-запрос и создание ключа](https://platform.openai.com/docs/quickstart/make-your-first-api-request);
- [Responses API](https://developers.openai.com/api/reference/cli/resources/responses/methods/create);
- [GPT-5 mini](https://developers.openai.com/api/docs/models/gpt-5-mini).

## 1. Создайте API-ключ

1. Войдите в OpenAI Platform и создайте проект.
2. Подключите billing/credits для API-проекта. Подписка ChatGPT сама по себе не является API-балансом.
3. Создайте секретный API key и скопируйте его один раз.
4. Не вставляйте ключ во frontend, исходный код, URL, скриншоты или Git.

## 2. Настройте окружение

Из корня репозитория:

```bash
cp .env.example .env
chmod 600 .env
```

Заполните `.env`:

```dotenv
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
INTERVIEW_ASSESSMENT_PROVIDER=openai
INTERVIEW_ASSESSMENT_MODEL=gpt-5-mini

INTERVIEW_RECRUITER_KEY=replace-with-a-long-local-recruiter-secret
INTERVIEW_MANAGER_KEY=replace-with-a-different-long-local-manager-secret
INTERVIEW_MANAGER_ID=hiring-manager
```

Корневое приложение не загружает `.env` автоматически, поэтому перед запуском экспортируйте файл
в текущий shell:

```bash
set -a
source .env
set +a
```

Проверьте только наличие переменной, не печатая сам секрет:

```bash
test -n "$OPENAI_API_KEY" && echo "OPENAI_API_KEY is set"
```

При необходимости проверьте доступ ключа к API:

```bash
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

## 3. Запустите LLM-демо

```bash
python -m interview_platform \
  --db-path /tmp/interview-platform-llm-demo.sqlite3 \
  --assessment-provider openai \
  --assessment-model gpt-5-mini \
  --seed-vacancy-assessment-demo
```

Seed создаёт три synthetic-интервью и вызывает модель для каждого из них. Откройте напечатанную
страницу вакансии в кабинете менеджера. В assessment card будут видны:

- модель и assessment run;
- оценки каждого критерия;
- итоговые `score`, `label` и комментарий;
- точные вопросы и цитаты, на которых основана рекомендация;
- отдельная форма человеческого решения.

Для оценки уже созданного интервью нажмите «Запустить оценку» в кабинете менеджера либо выполните
`POST /api/manager/interviews/{interview_id}/assessment-runs`.

## 4. Что отправляется модели

Модели отправляются только необходимые для оценки данные:

- роль и целевой уровень;
- утверждённые критерии, positive/negative anchors и допустимые альтернативы;
- связанные вопросы;
- текстовые ответы данного кандидата.

Alias кандидата, рейтинг, человеческое решение, аудио и видео в LLM payload не входят. Запрос
передаёт `store: false`. Тексты вакансии и кандидата помечаются как недоверенные данные, чтобы
инструкции внутри ответа не могли изменить system prompt.

## 5. Другие GPT-компоненты репозитория

FastAPI-приложение из `apps/api/` также использует `OPENAI_API_KEY` для manager-brief агента. Для
него добавьте в тот же `.env`:

```dotenv
MANAGER_BRIEF_MODEL=gpt-5-mini
MANAGER_BRIEF_MAX_ATTEMPTS=3
```

Зависимости backend устанавливаются отдельно:

```bash
python -m pip install -e ./apps/api
```

Основной `interview_platform` отправляет запрос через dependency-free HTTP-клиент и не требует
установки OpenAI SDK. Оба компонента используют один серверный `OPENAI_API_KEY`, но имеют разные
переменные выбора модели.

Research pipeline `product_engineering` использует тот же ключ, а модель задаётся CLI-флагом:

```bash
PYTHONPATH=tools/product-research python -m product_engineering "AI technical interview" --model gpt-5-mini
```

## 6. Офлайн-режим и диагностика

Для тестов без API-вызовов:

```bash
python -m interview_platform \
  --db-path /tmp/interview-platform-offline.sqlite3 \
  --assessment-provider deterministic \
  --seed-vacancy-assessment-demo
```

Типовые ошибки:

- `OPENAI_API_KEY is not configured` — файл не был экспортирован через `source`;
- HTTP `401` — ключ неверный, отозван или относится не к тому проекту;
- HTTP `429` — нет доступной квоты/credits либо достигнут rate limit;
- `assessment_provider_error` (`503`) — OpenAI временно недоступен или запрос исчерпал retries;
- `assessment_output_error` (`502`) — ответ модели прошёл JSON Schema, но не прошёл локальную
  evidence-проверку, например содержал выдуманную цитату.

Никогда не включайте автоматический fallback с LLM на эвристику для реальных assessment runs:
пользователь должен видеть ошибку, а не результат, silently рассчитанный другим evaluator.
