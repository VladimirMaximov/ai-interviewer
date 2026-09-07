# Проверка backend и контракт для frontend

Этот документ описывает три готовых пользовательских сценария:

1. рекрутёр загружает вакансию;
2. рекрутёр или кандидат загружает резюме для конкретного приглашения;
3. нанимающий менеджер вводит требования свободным текстом, проверяет разобранную форму и
   утверждает её.

Backend — FastAPI. Интерактивный OpenAPI после запуска доступен по адресу
`http://127.0.0.1:8000/docs`, JSON-схема — `http://127.0.0.1:8000/openapi.json`.

## 1. Что уже поддерживается

| Сценарий | Метод и путь | Авторизация |
|---|---|---|
| Создать вакансию из файла | `POST /recruiter/vacancies` | `X-Recruiter-Key` |
| Получить вакансии | `GET /recruiter/vacancies` | `X-Recruiter-Key` |
| Создать приглашение | `POST /recruiter/vacancies/{vacancy_id}/invitations` | `X-Recruiter-Key` |
| Получить отклики вакансии | `GET /recruiter/vacancies/{vacancy_id}/applications` | `X-Recruiter-Key` |
| Загрузить резюме рекрутёром | `POST /recruiter/vacancies/{vacancy_id}/applications/{invitation_id}/resume` | `X-Recruiter-Key` |
| Подтвердить согласие кандидата | `POST /candidate/{candidate_token}/consent` | token в URL |
| Загрузить резюме кандидатом | `POST /candidate/{candidate_token}/resume` | token в URL |
| Создать brief из требований | `POST /manager/vacancies/{vacancy_id}/brief-drafts` | `X-Manager-Key` |
| Изменить структурированные поля | `PATCH /manager/vacancies/{vacancy_id}/brief-drafts/{draft_id}` | `X-Manager-Key` |
| Утвердить требования | `POST /manager/vacancies/{vacancy_id}/brief-drafts/{draft_id}/approve` | `X-Manager-Key` |
| Получить утверждённый контекст | `GET /manager/vacancies/{vacancy_id}/approved-brief-context` | `X-Manager-Key` |

Вакансия и резюме загружаются как файл непосредственно в HTTP body. Это **не**
`multipart/form-data`. Поддерживаются UTF-8 `.txt`, Markdown, PDF и DOCX размером до 5 MiB.

Требования менеджера сейчас принимаются как **текст** в `source_text`. Отдельного backend API для
голосовой записи менеджера пока нет. Если под «сказать требования» имеется в виду буквально голос,
нужен отдельный этап распознавания речи либо временный клиентский speech-to-text с явным согласием.

## 2. Локальный запуск

Требования: Python 3.12+, Docker и Docker Compose. `jq` удобен для выполнения примеров ниже.

Из корня репозитория:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ./apps/api

cp .env.example .env
```

Минимальные переменные в `.env`:

```dotenv
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
MANAGER_BRIEF_MODEL=gpt-5-mini
MANAGER_BRIEF_MAX_ATTEMPTS=3

INTERVIEW_RECRUITER_KEY=local-recruiter-key
INTERVIEW_RECRUITER_ID=recruiter-local
INTERVIEW_MANAGER_KEY=local-manager-key
INTERVIEW_MANAGER_ID=manager-local
```

Непустой `source_text` вызывает OpenAI. Без `OPENAI_API_KEY` создание заполненного manager brief
вернёт `503`. Пустой текст создаёт пустой draft без вызова модели, но не проверяет разбор требований.

Запустить инфраструктуру, миграции и API:

```bash
docker compose up -d postgres minio
PYTHONPATH=apps/api alembic -c apps/api/alembic.ini upgrade head
PYTHONPATH=apps/api uvicorn app.main:app --reload --port 8000
```

Проверка запуска:

```bash
curl -sS http://127.0.0.1:8000/health
```

Ожидается:

```json
{"status":"ok"}
```

## 3. Полный ручной E2E-тест

### 3.1. Подготовить тестовые документы

Используйте только synthetic-данные, не добавляйте реальные резюме в Git.

```bash
mkdir -p /tmp/ai-interviewer-demo

printf '%s\n' \
  'Backend-разработчик. Python, FastAPI и PostgreSQL. Разработка API и code review.' \
  > /tmp/ai-interviewer-demo/vacancy.txt

printf '%s\n' \
  'Synthetic candidate. Python 5 лет, FastAPI 3 года, PostgreSQL 4 года.' \
  > /tmp/ai-interviewer-demo/resume.txt

export API_BASE=http://127.0.0.1:8000
export RECRUITER_KEY=local-recruiter-key
export MANAGER_KEY=local-manager-key
```

### 3.2. Загрузить вакансию

```bash
VACANCY_JSON=$(curl -sS -X POST "$API_BASE/recruiter/vacancies" \
  -H "X-Recruiter-Key: $RECRUITER_KEY" \
  -H 'X-Recruiter-Id: recruiter-local' \
  -H 'X-Vacancy-Title: Backend developer' \
  -H 'X-Document-Filename: vacancy.txt' \
  -H 'Idempotency-Key: vacancy-frontend-demo-001' \
  -H 'Content-Type: text/plain; charset=utf-8' \
  --data-binary @/tmp/ai-interviewer-demo/vacancy.txt)

printf '%s\n' "$VACANCY_JSON" | jq
export VACANCY_ID=$(printf '%s' "$VACANCY_JSON" | jq -r '.id')
```

Ожидается HTTP `201` и объект:

```json
{
  "id": "uuid",
  "title": "Backend developer",
  "status": "active",
  "source_filename": "vacancy.txt",
  "media_type": "text/plain",
  "content_hash": "sha256",
  "created_at": "2026-09-04T12:00:00Z"
}
```

Backend намеренно не возвращает извлечённый текст документа в обычном `VacancyView`.

Проверить список:

```bash
curl -sS "$API_BASE/recruiter/vacancies" \
  -H "X-Recruiter-Key: $RECRUITER_KEY" | jq
```

### 3.3. Создать приглашение кандидату

```bash
INVITATION_JSON=$(curl -sS -X POST \
  "$API_BASE/recruiter/vacancies/$VACANCY_ID/invitations" \
  -H "X-Recruiter-Key: $RECRUITER_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"candidate_alias":"synthetic-candidate-001","expires_in_hours":72}')

printf '%s\n' "$INVITATION_JSON" | jq
export INVITATION_ID=$(printf '%s' "$INVITATION_JSON" | jq -r '.invitation_id')
export CANDIDATE_TOKEN=$(printf '%s' "$INVITATION_JSON" | jq -r '.candidate_token')
```

Ожидается HTTP `201`:

```json
{
  "invitation_id": "uuid",
  "vacancy_id": "uuid",
  "candidate_token": "secret-returned-once",
  "expires_at": "2026-09-07T12:00:00Z"
}
```

`candidate_token` возвращается только при создании. Frontend должен сразу сохранить ссылку для
показа/копирования, но не отправлять token в аналитику или логи.

### 3.4. Проверить загрузку резюме рекрутёром

Этот путь работает до согласия кандидата:

```bash
curl -sS -X POST \
  "$API_BASE/recruiter/vacancies/$VACANCY_ID/applications/$INVITATION_ID/resume" \
  -H "X-Recruiter-Key: $RECRUITER_KEY" \
  -H 'X-Document-Filename: resume.txt' \
  -H 'Idempotency-Key: recruiter-resume-demo-001' \
  -H 'Content-Type: text/plain; charset=utf-8' \
  --data-binary @/tmp/ai-interviewer-demo/resume.txt | jq
```

Ожидается HTTP `201`, `uploaded_by_role: "recruiter"` и `version: 1`.

### 3.5. Проверить загрузку резюме кандидатом

Сначала проверить ссылку и записать согласие:

```bash
curl -sS "$API_BASE/candidate/$CANDIDATE_TOKEN" | jq
curl -sS -X POST "$API_BASE/candidate/$CANDIDATE_TOKEN/consent" | jq
```

Затем загрузить резюме:

```bash
curl -sS -X POST "$API_BASE/candidate/$CANDIDATE_TOKEN/resume" \
  -H 'X-Document-Filename: resume.txt' \
  -H 'Idempotency-Key: candidate-resume-demo-001' \
  -H 'Content-Type: text/plain; charset=utf-8' \
  --data-binary @/tmp/ai-interviewer-demo/resume.txt | jq
```

Если до этого файл загрузил рекрутёр, ожидаются `uploaded_by_role: "candidate"` и `version: 2`.
Без согласия candidate upload возвращает HTTP `409` и код `candidate_consent_required`.

Проверить текущую версию и отклики:

```bash
curl -sS "$API_BASE/candidate/$CANDIDATE_TOKEN/resume" | jq

curl -sS "$API_BASE/recruiter/vacancies/$VACANCY_ID/applications" \
  -H "X-Recruiter-Key: $RECRUITER_KEY" | jq
```

### 3.6. Передать требования нанимающего менеджера

```bash
BRIEF_JSON=$(curl -sS -X POST \
  "$API_BASE/manager/vacancies/$VACANCY_ID/brief-drafts" \
  -H "X-Manager-Key: $MANAGER_KEY" \
  -H 'X-Manager-Id: manager-local' \
  -H 'Idempotency-Key: manager-brief-demo-001' \
  -H 'Content-Type: application/json' \
  -d '{
    "source_text": "Ищем middle backend-разработчика. Обязательны Python, FastAPI и PostgreSQL. Нужно проектировать API, писать тесты и проводить code review. Желательно знание Kafka. На интервью хочу услышать конкретный пример выбора архитектуры и объяснение компромиссов."
  }')

printf '%s\n' "$BRIEF_JSON" | jq
export DRAFT_ID=$(printf '%s' "$BRIEF_JSON" | jq -r '.id')
export DRAFT_REVISION=$(printf '%s' "$BRIEF_JSON" | jq -r '.revision')
```

Запрос может выполняться до 60 секунд, потому что backend вызывает LLM. Frontend должен показывать
состояние `generating`, блокировать повторную отправку и повторять сетевой запрос с тем же
`Idempotency-Key`.

Основные поля ответа:

```json
{
  "id": "draft-uuid",
  "vacancy_id": "vacancy-uuid",
  "version": 1,
  "revision": 1,
  "status": "draft",
  "source_text": "исходный текст менеджера",
  "fields": [
    {
      "id": "field-uuid",
      "field_key": "seniority",
      "label": "Уровень",
      "value": "middle",
      "origin": "manager_source",
      "source_fragment_ids": ["manager-source:...:1"],
      "source_quotes": ["middle backend-разработчика"],
      "confidence": 0.98,
      "confirmation_status": "confirmed",
      "confirmed_by": "manager-local",
      "confirmed_at": "2026-09-04T12:00:00Z"
    }
  ],
  "unresolved_fields": [],
  "validation_issues": [],
  "content_hash": "sha256",
  "agent_run_id": "uuid",
  "created_by": "manager-local",
  "created_at": "2026-09-04T12:00:00Z",
  "updated_at": "2026-09-04T12:00:00Z",
  "approved_by": null,
  "approved_at": null
}
```

LLM извлекает только явно названные требования. Он не должен заполнять отсутствующие поля своими
предположениями. `source_quotes` позволяют показать менеджеру, откуда взялось каждое значение.

### 3.7. Отредактировать и утвердить brief

Типы полей:

- строки: `role`, `seniority`, `business_context`;
- массивы строк: `responsibilities`, `must_have_competencies`,
  `nice_to_have_competencies`, `expected_answer_signals`, `constraints`, `topics_to_cover`.

Пример редактирования:

```bash
UPDATED_JSON=$(curl -sS -X PATCH \
  "$API_BASE/manager/vacancies/$VACANCY_ID/brief-drafts/$DRAFT_ID" \
  -H "X-Manager-Key: $MANAGER_KEY" \
  -H 'Content-Type: application/json' \
  -d "{
    \"expected_revision\": $DRAFT_REVISION,
    \"updates\": [
      {
        \"field_key\": \"nice_to_have_competencies\",
        \"value\": [\"Kafka\", \"Docker\"],
        \"confirmation_status\": \"confirmed\"
      }
    ]
  }")

printf '%s\n' "$UPDATED_JSON" | jq
export DRAFT_REVISION=$(printf '%s' "$UPDATED_JSON" | jq -r '.revision')
```

Каждое сохранение увеличивает `revision`. Если frontend отправил устаревшую revision, backend
вернёт HTTP `409` с кодом `revision_conflict`; нужно перезагрузить draft, а не перезаписывать его.

Утверждение:

```bash
APPROVED_JSON=$(curl -sS -X POST \
  "$API_BASE/manager/vacancies/$VACANCY_ID/brief-drafts/$DRAFT_ID/approve" \
  -H "X-Manager-Key: $MANAGER_KEY" \
  -H 'Content-Type: application/json' \
  -d "{
    \"expected_revision\": $DRAFT_REVISION,
    \"confirm_no_automatic_rejection\": true
  }")

printf '%s\n' "$APPROVED_JSON" | jq
```

Ожидаются HTTP `200` и `status: "approved"`. Утверждённый draft неизменяем: для новых требований
нужно создать новый draft. Новое утверждение переводит предыдущее в `superseded`.

Проверить allowlisted-контекст:

```bash
curl -sS \
  "$API_BASE/manager/vacancies/$VACANCY_ID/approved-brief-context" \
  -H "X-Manager-Key: $MANAGER_KEY" | jq
```

Проверить объединённый контекст кандидата для дальнейших агентов:

```bash
curl -sS \
  "$API_BASE/recruiter/vacancies/$VACANCY_ID/applications/$INVITATION_ID/agent-context" \
  -H "X-Recruiter-Key: $RECRUITER_KEY" | jq
```

В нём должны быть именно эта вакансия, последняя версия резюме, утверждённый manager brief и ответы
этого кандидата. Это служебный endpoint; его не следует отображать кандидату.

## 4. Контракт для React/TypeScript

Проект уже использует React, TypeScript и Vite. Текущий Vite proxy содержит только `/candidate`.
Для локальной разработки recruiter/manager UI нужно добавить:

```ts
server: {
  proxy: {
    "/candidate": "http://127.0.0.1:8000",
    "/recruiter": "http://127.0.0.1:8000",
    "/manager": "http://127.0.0.1:8000",
    "/health": "http://127.0.0.1:8000",
  },
},
```

Минимальные типы:

```ts
type UUID = string;
type ISODateTime = string;

export interface Vacancy {
  id: UUID;
  title: string;
  status: "active" | "closed";
  source_filename: string;
  media_type: string;
  content_hash: string;
  created_at: ISODateTime;
}

export interface Resume {
  id: UUID;
  vacancy_id: UUID;
  version: number;
  source_filename: string;
  media_type: string;
  content_hash: string;
  uploaded_by_role: "candidate" | "recruiter";
  created_at: ISODateTime;
}

export interface InvitationCreated {
  invitation_id: UUID;
  vacancy_id: UUID;
  candidate_token: string;
  expires_at: ISODateTime;
}

export type BriefFieldKey =
  | "role"
  | "seniority"
  | "business_context"
  | "responsibilities"
  | "must_have_competencies"
  | "nice_to_have_competencies"
  | "expected_answer_signals"
  | "constraints"
  | "topics_to_cover";

export interface BriefField {
  id: UUID;
  field_key: BriefFieldKey;
  label: string;
  value: string | string[];
  origin: "manager_source" | "agent_suggestion" | "manager_edited";
  source_fragment_ids: string[];
  source_quotes: string[];
  confidence: number | null;
  confirmation_status: "proposed" | "confirmed" | "rejected";
  confirmed_by: string | null;
  confirmed_at: ISODateTime | null;
}

export interface ManagerBriefDraft {
  id: UUID;
  vacancy_id: UUID;
  version: number;
  revision: number;
  status: "draft" | "validation_failed" | "approved" | "superseded";
  source_text: string;
  fields: BriefField[];
  unresolved_fields: Array<{ field_key: BriefFieldKey; question: string }>;
  validation_issues: Array<{
    code: string;
    severity: string;
    field_key?: BriefFieldKey;
    message: string;
  }>;
  content_hash: string;
  agent_run_id: UUID;
  created_by: string;
  created_at: ISODateTime;
  updated_at: ISODateTime;
  approved_by: string | null;
  approved_at: ISODateTime | null;
}
```

Функция загрузки raw-файла:

```ts
async function uploadDocument<T>(
  url: string,
  file: File,
  headers: Record<string, string>,
): Promise<T> {
  if (file.size > 5 * 1024 * 1024) {
    throw new Error("Максимальный размер файла — 5 МиБ");
  }

  const response = await fetch(url, {
    method: "POST",
    headers: {
      ...headers,
      "X-Document-Filename": file.name,
      "Idempotency-Key": crypto.randomUUID(),
      "Content-Type": file.type || "application/octet-stream",
    },
    body: file,
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(
      payload?.error?.message ?? payload?.detail ?? "Не удалось загрузить файл",
    );
  }
  return payload as T;
}
```

Для retry нельзя генерировать новый `Idempotency-Key`: сохраните ключ операции в состоянии до
получения успешного ответа. Новый ключ создаётся только для новой пользовательской операции.

Пример создания manager brief:

```ts
async function createManagerBrief(
  vacancyId: string,
  sourceText: string,
  managerKey: string,
  idempotencyKey: string,
): Promise<ManagerBriefDraft> {
  const response = await fetch(`/manager/vacancies/${vacancyId}/brief-drafts`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Manager-Key": managerKey,
      "Idempotency-Key": idempotencyKey,
    },
    body: JSON.stringify({ source_text: sourceText }),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(
      payload?.error?.message ?? payload?.detail ?? "Не удалось разобрать требования",
    );
  }
  return payload as ManagerBriefDraft;
}
```

## 5. Какие экраны нужны frontend

### Экран рекрутёра: вакансии

- список из `GET /recruiter/vacancies`;
- форма: название + один файл;
- состояния `idle/uploading/success/error`;
- проверка размера и типа до отправки;
- после HTTP `201` переход на страницу вакансии.

### Экран вакансии

- данные вакансии;
- список applications;
- создание приглашения;
- одноразовый экран копирования candidate link;
- загрузка/замена резюме для выбранного `invitation_id`;
- отображение `version`, `source_filename`, `uploaded_by_role`, `created_at`.

### Экран кандидата

- разрешение приглашения через `GET /candidate/{token}`;
- consent;
- загрузка резюме после consent;
- success/error и текущая metadata резюме;
- token берётся из URL, но не пишется в telemetry.

### Экран нанимающего менеджера

- выбор существующей вакансии;
- textarea до 50 000 символов;
- `generating` во время вызова LLM;
- девять известных полей формы, даже если часть отсутствует в `fields`;
- для list-полей удобнее chips/list editor;
- показ `source_quotes`, confidence и unresolved questions;
- сохранение с текущей `revision`;
- обработка `409 revision_conflict` через reload;
- блокировка approve при blocking `validation_issues`;
- обязательный явный checkbox «Требования не используются для автоматического отказа»;
- после approve — read-only режим и действие «Создать новую версию».

## 6. Ошибки, которые должен обработать frontend

Backend использует две формы ошибки:

```json
{"detail":"Recruiter credentials are invalid."}
```

и

```json
{
  "error": {
    "code": "revision_conflict",
    "message": "draft was changed; reload it before saving",
    "details": {}
  }
}
```

Основные статусы:

- `401` — неверный staff key;
- `404` — вакансия, draft, application или candidate link не найдены;
- `409` — нет consent, конфликт idempotency/revision или объект уже изменён;
- `422` — неправильные headers/JSON, тип документа, пустой документ или запрещённое требование;
- `502` — LLM вернул ответ, который не прошёл локальную проверку;
- `503` — staff API/OpenAI не настроен или provider временно недоступен.

Frontend должен показывать пользовательское сообщение, но также сохранять `error.code` для
диагностики. На `revision_conflict` нужен отдельный UX, а не обычный retry.

## 7. Автоматическая проверка backend

```bash
PYTHONPATH=apps/api python -m unittest discover -s apps/api/tests -v
```

Сейчас набор содержит 47 тестов. Интеграционные тесты используют SQLite и fake manager agent,
поэтому не расходуют OpenAI tokens. Ручной сценарий с непустым `source_text` проверяет уже реальный
Responses API и требует настроенный ключ.

## 8. Важные ограничения перед production

1. Нельзя помещать `INTERVIEW_RECRUITER_KEY` или `INTERVIEW_MANAGER_KEY` в `VITE_*`: такие значения
   попадут в публичный JavaScript bundle. Прямые headers допустимы только для локального MVP.
   Для production нужен BFF/API gateway либо нормальная staff-аутентификация и серверная сессия.
2. CORS сейчас разрешает только `localhost:5173` и `127.0.0.1:5173`.
3. Manager brief API сейчас принимает `vacancy_id` в path, но не проверяет существование вакансии
   внутри manager-brief сервиса. UI должен выбирать ID из `GET /recruiter/vacancies`; backend-
   проверку связи нужно добавить до production.
4. Создание приглашения не имеет `Idempotency-Key`; frontend должен блокировать двойной submit.
5. Убедитесь, что ветка коллеги содержит endpoint recruiter resume upload и Alembic-миграцию
   `004_resume_uploader_audit.py`, прежде чем она начнёт интеграцию этого сценария.
