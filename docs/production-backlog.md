# Production backlog

Этот backlog описывает работы, которые остаются после текущего hackathon-прототипа до
условно продовой версии сервиса. Порядок — от блокирующих рисков к улучшениям. Задачи
не означают, что автоматическое кадровое решение будет передано модели: финальное решение
остаётся за рекрутёром и нанимающим менеджером.

## Текущее состояние

- Приложение развёрнуто на выделенном сервере `212.41.11.31`.
- Docker Compose поднимает PostgreSQL, MinIO, Redis, API, CPU worker, два UI и Nginx gateway.
- Кабинет рекрутёра создаёт вакансию, три блока вопросов и ссылку кандидата.
- Кандидатский UI поддерживает spoken/coding вопросы, непрерывную запись, чанки, таймер,
  код, транскрипцию и результаты.
- Приглашения и результаты сохраняются в PostgreSQL, медиа — в MinIO.
- MuseTalk/XTTS сейчас выключены; предусмотрен геометрический/static fallback.
- Публичный адрес пока HTTP; live-камера и микрофон на удалённом домене без HTTPS не работают.

## P0 — блокирует продовую эксплуатацию

- [ ] **TLS и домен.** Завершить идентификацию домена `napoleonit-career.ru`, убедиться, что
  `A @` и `A www` указывают на `212.41.11.31`, выпустить Let’s Encrypt-сертификат, настроить
  HTTP→HTTPS, HSTS после проверки и открыть TCP/443.
- [ ] **Аутентификация и секреты.** Убрать demo-ключ рекрутёра из клиентского bundle; сделать
  серверную staff-сессию/OIDC, ротацию секретов и отдельные ключи для окружений. Секреты хранить
  только в Secret Manager или защищённом `.env` на сервере.
- [ ] **Авторизация данных.** Проверить tenant/role isolation для вакансий, приглашений,
  медиа, транскриптов, кода и результатов; подписанные URL сделать короткоживущими.
- [ ] **Надёжное завершение интервью.** Гарантировать идемпотентность submit/finish, resume
  после перезагрузки, повторную отправку чанков и атомарную фиксацию границы ответа.
- [ ] **Очереди и фоновые задачи.** Добавить retry с backoff, dead-letter/replay, метрики
  длительности и алерты для ASR, TTS, оценки и медиа-композиции.
- [ ] **Резервное копирование.** Настроить ежедневные backup PostgreSQL и MinIO, проверить
  восстановление на чистом окружении и зафиксировать RPO/RTO.
- [ ] **Наблюдаемость.** Централизованные структурированные логи, correlation/session ID,
  health/readiness, error tracking, дашборд CPU/RAM/GPU/disk/Redis/PostgreSQL/MinIO.
- [ ] **Privacy/legal gate.** Экран согласия, политика хранения и удаления, экспорт/удаление
  данных кандидата, журнал доступа к медиа. Не логировать PII, токены и содержимое записей.
- [ ] **Release/rollback.** CI с lint, typecheck, unit/integration/E2E, миграциями в dry-run,
  immutable image tags, staging smoke test и documented rollback.

## P1 — необходимо для качественного продукта

- [ ] **Реальный ASR.** Запустить gigaAM локально в отдельном CPU/GPU worker, добавить контроль
  качества, словарь терминов, таймкоды и повторную обработку failed-аудио.
- [ ] **Runtime TTS/avatar.** Подключить проверенный XTTS и MuseTalk на T4 с warm-cache,
  лимитами очереди, audio-first fallback и тестом деградации при отключённой модели.
- [ ] **Адаптивные вопросы.** Реализовать контракт runtime evaluation: вопрос, текстовый ответ,
  confidence, 0/1/2 follow-up; ограничить глубину двумя вопросами и сохранять версии решений.
- [ ] **Рекрутерский UX.** Исправить все состояния загрузки/ошибок, убрать запросы с `undefined`,
  добавить подтверждение сохранения, повтор и понятную валидацию конфигурации.
- [ ] **Candidate UX/accessibility.** Проверка устройств до начала, восстановление сессии,
  понятный offline/error state, клавиатурная навигация, WCAG-проверка и адаптивность.
- [ ] **Нагрузочное тестирование.** Проверить часовые интервью, 720p, 10-секундные чанки,
  параллельные кандидаты, заполнение диска и поведение GPU worker при очереди.
- [ ] **Data lifecycle.** Зафиксировать retention policy, lifecycle MinIO, контроль размера,
  очистку временных файлов и защиту от повторной загрузки одного чанка.
- [ ] **API governance.** Версионирование контрактов, OpenAPI validation, idempotency keys,
  backward-compatible migrations и contract tests для обоих UI.

## P2 — после стабилизации

- [ ] Менеджерский кабинет, назначение кандидатов и human review workflow.
- [ ] Полноценный live-coding editor с подсветкой, тестами и безопасным sandbox execution.
- [ ] Frozen evaluation set для ASR/оценки, quality dashboard и сравнение провайдеров.
- [ ] Multi-tenant billing/quotas, rate limiting и WAF/CDN.
- [ ] Blue/green или canary deployment и автоматический rollback.

## Доступ к серверу для команды

Подключение выполняется по SSH-ключу, пароль и приватный ключ в репозиторий не помещаются.

```bash
ssh -i ~/.ssh/selectel_ai_interviewer root@212.41.11.31
```

Параметры:

- Host: `212.41.11.31`
- User: `root`
- SSH private key (локальный путь владельца): `~/.ssh/selectel_ai_interviewer`
- Проект на сервере: `/opt/ai-interviewer`
- Compose-файл: `/opt/ai-interviewer/deploy/docker-compose.prototype.yml`
- HTTP cabinet: `http://212.41.11.31/`
- HTTP candidate UI: `http://212.41.11.31/interview/`
- API health: `http://212.41.11.31/api/health`
- API readiness: `http://212.41.11.31/api/ready`

Базовые команды диагностики:

```bash
cd /opt/ai-interviewer
docker compose -f deploy/docker-compose.prototype.yml ps
docker compose -f deploy/docker-compose.prototype.yml logs --tail=100 api
docker compose -f deploy/docker-compose.prototype.yml logs --tail=100 gateway
```

Перед выдачей доступа каждому сокоманднику нужно передать публичный ключ через панель
провайдера/`authorized_keys`. Пароль от сервера не фиксируем в документации и не передаём через
Git или чат; при необходимости его следует получить/сменить в панели Selectel.

## Definition of Done для production

Сервис считается готовым только после прохождения TLS smoke test, backup restore test,
authz/security review, полного CI, нагрузочного теста часового интервью и ручного сквозного
сценария: вакансия → приглашение → spoken/coding ответы → ASR → follow-up → результаты в кабинете.
