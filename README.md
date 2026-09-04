# AI Interviewer — Napoleon IT

Платформа асинхронного видеоинтервью и AI-оценки ИТ-кандидатов. Проект автоматизирует
рекрутёрский и верхнеуровневый технический скрининг, сохраняя финальное решение за рекрутёром и
нанимающим менеджером.

> Статус репозитория: продуктовая проработка и исследовательный pipeline готовы; добавлен
> архитектурный web-POC с отдельными кабинетами кандидата, рекрутёра и менеджера. Реальная видеозапись,
> транскрибация и AI-оценка пока заменены явным text stub.

## Проблема

Napoleon IT получает около 700 откликов в первые дни публикации Python-вакансии, а в пиковом
кейсе получила 6 700 откликов за неделю. Технический специалист может потратить до 1,5 часа на
интервью с кандидатом, который не соответствует базовым требованиям. Resume-only фильтрация при
этом способна потерять сильных специалистов, которые плохо составили резюме.

## Решение

```text
вакансия и требования
→ AI-черновик вопросов и scoring rubric
→ ревью техническим специалистом
→ персональная ссылка кандидату
→ видеоинтервью в удобное время
→ транскрибация и evidence extraction
→ оценка fit / no_fit / additional_review
→ решение рекрутёра
→ просмотр назначенным hiring manager
→ живое финальное интервью
```

Система не принимает кадровое решение автоматически. Каждый технический вывод должен быть связан
с цитатой или таймкодом ответа; нехватка данных фиксируется явно, а не заменяется догадкой модели.

## Пользователи

- **Рекрутёр** создаёт вакансию, приглашает кандидатов, проверяет отчёт и управляет воронкой.
- **Технический специалист** утверждает вопросы, критерии и разбирает спорные случаи.
- **Кандидат** проходит короткое интервью с камерой и микрофоном без календарной координации.
- **Нанимающий менеджер** видит только назначенных кандидатов, evidence и заметки рекрутёра.

## MVP

- одна Python-вакансия и один согласованный grade;
- 6 вопросов за 25–30 минут без live coding;
- запись каждого ответа и восстановление незавершённой загрузки;
- transcript с техническим словарём и таймкодами;
- versioned rubric, criterion scores и `insufficient_information`;
- видео, transcript, сильные стороны, риски и вопросы на финал;
- tab-switch events как сигнал для человека, но не основание для автоматического отказа;
- раздельные `ai_recommendation`, `recruiter_decision` и `hiring_manager_decision`;
- заменяемые ASR, TTS и LLM adapters.

## Метрики пилота

Главный quality gate — не менее 80% совпадения рекомендации системы с независимой оценкой
рекрутёра и технического эксперта на отложенной выборке. Дополнительно измеряются macro-F1,
balanced accuracy, false pass/false reject, точность evidence, completion rate, время проверки
отчёта и сэкономленные инженерные часы. Цель 95% сокращения live technical screens применяется
только после подтверждения качества.

## Структура репозитория

```text
product_engineering/                 # воспроизводимый research pipeline
interview_platform/                  # domain/application/infrastructure/web слои POC
tests/                               # unit tests pipeline
specs/                               # спецификация, архитектурный план и API-контракт
interview/                           # материалы stakeholder research
research/                            # исследования конкурентов
deliverables/ai-technical-interview/ # продуктовый отчёт и JSON-результаты
```

Основные документы:

- [`napoleon-it-report.md`](deliverables/ai-technical-interview/napoleon-it-report.md) — полный
  product brief, JTBD, Pain Map, RICE, Lean Canvas, MVP и evaluation plan;
- [`napoleon-it-result.json`](deliverables/ai-technical-interview/napoleon-it-result.json) —
  машиночитаемая версия;
- [`xenia-ai-competitor-analysis.md`](research/xenia-ai-competitor-analysis.md) — анализ прямого
  конкурента и продуктовые выводы.
- [`candidate-segmentation-ai-interview.md`](research/candidate-segmentation-ai-interview.md) —
  evidence-backed сегментация кандидатов, гипотезы и план исследования senior-трека.

## Архитектурный POC платформы

POC реализован как модульный монолит: `domain` хранит state machine и evidence-правила,
`application` — пользовательские сценарии и порты, `infrastructure` — SQLite и text capture stub,
`web` — отдельные HTML/JSON-проекции кандидата, рекрутёра и менеджера. Кандидат входит по
персональному токену, который хранится только как digest. Рекрутёр видит всю воронку, создаёт
приглашения, публикует фидбэк и назначает менеджера. Менеджер видит только назначенных ему
кандидатов и сохраняет своё решение отдельно. Два staff-кабинета защищены разными секретами.

```bash
export INTERVIEW_RECRUITER_KEY='local-recruiter-secret'
export INTERVIEW_MANAGER_KEY='local-manager-secret'
python -m interview_platform --db-path /tmp/interview-platform-poc.sqlite3 --seed-demo
```

Команда напечатает главную страницу и три точки входа. Для `/recruiter` используйте имя
`recruiter` и `INTERVIEW_RECRUITER_KEY`; для `/manager` — имя `manager` и
`INTERVIEW_MANAGER_KEY`. Кандидат открывает одноразово показанную ссылку. Менеджер сначала увидит
пустой список: кандидат появится у него только после завершения интервью и назначения рекрутёром.
Демоданные имеют alias `synthetic-candidate-001`; raw token, реальные данные, записи и транскрипты
в репозиторий не добавляются.

Архитектурные артефакты находятся в
[`specs/001-interview-platform-architecture/`](specs/001-interview-platform-architecture/), полный
API-контракт — в
[`contracts/openapi.yaml`](specs/001-interview-platform-architecture/contracts/openapi.yaml).

## Оценка с контекстом вакансии

Новый поток отделяет два результата: `corporate_competency` берётся из нормализованной матрицы
Napoleon IT, а `vacancy_fit` — только из утверждённых менеджером ожиданий конкретной вакансии.
Полнота evidence хранится третьим показателем и не превращается в оценку. Ранжирование работает
лишь для assessment runs одного snapshot, не меняет статус кандидата и не создаёт отказ.

Менеджер может добавить короткую фразу, вставленный текст, UTF-8 `.txt`/`.md` либо уже готовую
расшифровку речи. Материал сохраняется как provenance-bearing data, превращается в редактируемые
критерии и начинает влиять на интервью только после явного утверждения профиля. Snapshot фиксирует
матрицу, роль, уровень, критерии, вопросы и политики; последующие изменения вакансии его не
перезаписывают.

Запустить полный синтетический сценарий на трёх кандидатах:

```bash
export INTERVIEW_MANAGER_KEY='local-manager-secret'
export INTERVIEW_RECRUITER_KEY='local-recruiter-secret'
python -m interview_platform \
  --db-path /tmp/interview-platform-vacancy.sqlite3 \
  --seed-vacancy-assessment-demo
```

Откройте напечатанный URL `/manager/vacancies/...`, чтобы проверить требования и assessment
context. Создание обычных приглашений и управление кандидатами выполняется в `/recruiter`, а
менеджер рассматривает только назначенных ему рекрутёром кандидатов. В vacancy-aware timeline
кандидат видит только опубликованные область оценки, сильные стороны, зоны роста, пробелы evidence,
ограничения и следующие шаги; внутренние scores, ранги, заметки и решения не сериализуются.

JSON API описан в
[`specs/002-vacancy-fit-assessment/contracts/openapi.yaml`](specs/002-vacancy-fit-assessment/contracts/openapi.yaml),
а пошаговая проверка — в
[`specs/002-vacancy-fit-assessment/quickstart.md`](specs/002-vacancy-fit-assessment/quickstart.md).
Текущий evaluator является детерминированным text-only stub: он нужен для проверки архитектуры,
не валидирован как модель качества найма и не должен использоваться для реальных кандидатов.

## Локальная проверка

Требуется Python 3.12+.

```bash
python -m product_engineering "AI technical interview" --dry-run
python -m unittest discover -s tests -v
python -m compileall -q product_engineering interview_platform
```

Для полного research run задайте `OPENAI_API_KEY` через переменную окружения. Не добавляйте в Git
API-ключи, персональные данные кандидатов, видео, аудио и неанонимизированные транскрипты.

## Принципы продукта

- Human-in-the-Loop: только человек приглашает или отказывает.
- Evidence-first: оценки проверяемы по исходному ответу.
- Content-only scoring: внешность, эмоции, акцент и уверенность голоса не оцениваются моделью.
- Provider portability: смена модели проходит через единый adapter и повторный frozen evaluation.
- Candidate respect: понятная длительность, согласие на запись, восстановление после сбоя и
  спокойный интерфейс без давления.
