# Napoleon IT — автоматизация технического интервью

Версия 2, обновлена по stakeholder meeting transcript от 2 сентября 2026 года.

Источник интервью: [Granola meeting transcript](https://notes.granola.ai/t/464f511d-302a-4b72-b51b-0be66af4fe3e-00demib2).

## 1. Executive decision

Продукт следует проектировать как **внутренний throughput-инструмент Napoleon IT**, а не как
внешний HRTech SaaS. Его задача — объединить рекрутёрский и верхнеуровневый технический скрин в
одно асинхронное интервью, после которого человек принимает решение о допуске к финальному live
этапу.

Главная ценность:

> Дать каждому кандидату, прошедшему минимальный фильтр, возможность показать опыт и техническое
> мышление, не расходуя 1,5 часа инженера на заведомо неподходящего кандидата.

Главный критерий продукта — не скорость генерации отчёта, а качество фильтра. Если система
массово пропускает слабых кандидатов, менеджеры перестанут ей пользоваться. Поэтому MVP должен
демонстрировать воспроизводимую evaluation pipeline с evidence, состоянием
`insufficient_information` и сравнением с независимой оценкой рекрутёра и технического эксперта.

## 2. Что теперь подтверждено, а не предполагается

| Факт/решение | Статус | Продуктовое следствие |
|---|---|---|
| 6 700 откликов на developer role за неделю в пиковом кейсе | Реальный контекст компании | Нужен массовый асинхронный funnel и batch review |
| Около 700 откликов в первые дни обычной Python-вакансии | Пилотный baseline | Считать invite/start/complete/qualified конверсию от каждого этапа |
| Инженер тратит до 1,5 часа на неподходящего кандидата | Подтверждённая боль | Основная экономия — engineering hours, не только выплаты внешним экспертам |
| Первые два этапа должны со временем заменить ИИ; третий остаётся live | Product vision | MVP объединяет biography + upper-level technical screen, не заменяет финал |
| В MVP нет live coding | Scope decision | Нельзя делать сильные выводы о практическом coding ability только из речи |
| ИИ генерирует вопросы из JD, технический специалист их утверждает | Core workflow | Published interview version обязана иметь reviewer и timestamp |
| Идеальные ответы от менеджера не готовятся | Ограничение процесса | Нужны scoring anchors/rubric, генерируемые системой и проверяемые техническим reviewer |
| Human-in-the-loop обязателен | Core policy | Ни auto-reject, ни auto-invite; решение и override фиксируются |
| Цель — снизить затраты на технические интервью на 95% | Pilot business metric | Expert escalation должен стремиться к 5%, но только после прохождения quality gate |
| Ошибки обоих типов одинаково нежелательны | Error policy | Использовать balanced metrics; не оптимизировать только pass precision или recall |
| Пилотная вакансия — Python-разработчик | Scope decision | Валидировать одну роль и grade band, не «любую вакансию» в первой версии |
| Huntflow — текущая CRM | Integration context | MVP: export/deep link; полноценная интеграция после доказательства качества |
| Базовый antifraud — tab switching + video | MVP decision | Записывать события; подозрение показывать человеку, не превращать в автоматический отказ |
| Провайдер модели не определён | Architecture constraint | ASR/LLM/TTS должны подключаться через model gateway/adapters |
| Candidate feedback не входит в MVP | Scope decision | Оставить data model и статус для будущей функции, не строить UI сейчас |

## 3. Критические продуктовые развилки

### Универсальность против валидности

Архитектура может поддерживать любую вакансию, но качество нельзя доказать одновременно для всех
ролей и грейдов. Пилот нужно замкнуть на Python-разработчике и явно указать диапазон seniority.
После успешного holdout-теста новая роль добавляется как новая калибровочная область, а не просто
новый prompt.

### Нет «идеального ответа», но должна быть рубрика

Модель не должна «оценивать самостоятельно» в смысле свободного суждения. Даже без эталонного
текста необходимы:

- проверяемые компетенции и must-have критерии;
- positive/negative behavioral anchors;
- признаки конкретики и личного вклада;
- допустимые альтернативные подходы;
- правило `insufficient_information`;
- веса и пороги, которые агрегирует код.

Технический специалист ревьюит не идеальные ответы, а **компетенции, anchors и вопросы**. Это
сохраняет универсальность и делает результат проверяемым.

### Видео как evidence, а не источник скрытого score

Napoleon IT хочет сохранять живую реакцию, интонацию и уверенность и использовать видео против
подмены. В MVP видео должно быть доступно людям вместе с заметками и tab-switch events. Однако
автоматический score рекомендуется строить по содержанию ответа и явно заданным критериям, не по
эмоциям, внешности, акценту или «уверенности голоса». Так сохраняются и доверие, и возможность
объяснить вывод.

### 5% expert escalation — результат калибровки, не жёсткий лимит

Если заранее заставить систему отправлять человеку не более 5% случаев, она будет выдавать
уверенные решения при недостатке данных. Сначала нужно построить curve
`coverage ↔ quality`, выбрать порог качества, а затем измерить, приблизилась ли доля escalation к
5%. При конфликте качество важнее экономии.

### Consent нельзя откладывать для реального пилота

Для демонстрации на тестовых данных полноценный legal flow можно сократить. Для любого интервью
реального кандидата минимальный consent screen, цель записи, срок хранения, получатели и роль ИИ
являются gate к запуску, даже если расширенный self-service deletion появится позже.

## 4. Целевой end-to-end процесс

```text
Huntflow / vacancy source
  → recruiter uploads JD and grade
  → AI drafts competency blueprint, anchors and 5–7 questions
  → technical specialist reviews and publishes interview version
  → recruiter invites eligible candidate by expiring link
  → consent + camera/microphone preflight
  → biography block + verbal technical block
  → per-question video upload + tab events
  → ASR with Python/vacancy glossary
  → evidence extraction from resume and answers
  → criterion scoring + insufficient-information checks
  → deterministic aggregation and recommendation
  → recruiter review + notes + decision
  → selected candidate assigned to hiring manager
  → manager sees only assigned candidates and recruiter notes
  → live final interview covers soft skills, culture and unresolved technical gaps
```

## 5. Роли, права и ответственность

| Capability | Recruiter | Technical specialist | Hiring manager | Candidate |
|---|:---:|:---:|:---:|:---:|
| Видит все вакансии и кандидатов | Да | Только назначенные шаблоны | Нет | Нет |
| Создаёт vacancy draft | Да | Нет | Нет | Нет |
| Редактирует вопросы | Да | Да, при review | Нет | Нет |
| Публикует technical interview version | После approval | Approves | Нет | Нет |
| Получает candidate link | Отправляет | Нет | Нет | Да |
| Видит AI report и все записи | Да | При calibration/escalation | Только назначенных | Нет |
| Добавляет recruiter notes | Да | Technical review notes | Decision notes | Нет |
| Принимает финальное решение | Первичная фильтрация | Нет, кроме expert escalation | По своей команде | Нет |
| Видит общую воронку | Да | Нет | Нет | Нет |

Решение должно хранить отдельно `ai_recommendation`, `recruiter_decision` и
`hiring_manager_decision`; нельзя перезаписывать человеческим решением исходный вывод модели.

## 6. Customer Profile и JTBD

### Рекрутёр — process owner

Jobs:

- обработать сотни откликов, не потеряв сильных кандидатов с плохим резюме;
- настроить объединённый biography + technical screen;
- проверить отчёт и короткие видеофрагменты;
- направить подходящего кандидата в конкретную команду;
- сохранить уважительную и быструю коммуникацию.

Pains:

- физически невозможно вручную разобрать 700–6 700 откликов;
- существующий resume screening недостаточно точен;
- нельзя самостоятельно подтвердить технический уровень;
- black-box recommendation переносит риск на рекрутёра;
- длинное интервью или полный просмотр видео снова создают bottleneck.

Gains:

- interview opportunity для кандидатов, прошедших только минимальные требования;
- structured report с evidence и missing information;
- shortlist без просмотра всех видео;
- заметки, assignment в команду и прозрачный audit trail;
- respectful candidate journey в любое время.

Core JTBD:

> When вакансия получает сотни откликов, I want to автоматически провести единый биографический
> и технический скрин для минимально подходящих кандидатов, so I can сформировать качественный
> shortlist без участия инженера в каждом интервью.

Acceptance: не менее 80% agreement с adjudicated human label; равный контроль false pass/false
reject; recruiter review ≤5 минут на отчёт; ни одного автоматического кадрового решения.

### Технический специалист — knowledge owner

Jobs:

- проверить, что вопросы измеряют нужные Python-компетенции и соответствуют grade;
- освободиться от повторяющихся 1,5-часовых интервью;
- разбирать только ambiguous или высокорисковые случаи;
- объяснять причины расхождений и улучшать anchors.

Pains:

- время уходит на кандидатов без базового уровня;
- вопросы разных инженеров несопоставимы;
- без live coding трудно подтвердить практическую способность;
- свободное LLM-суждение может звучать убедительно, но быть технически неверным.

Core JTBD:

> When новая vacancy interview version готовится к запуску, I want to быстро проверить
> competencies, anchors и вопросы, so I can делегировать массовый скрин системе, сохранив
> технический стандарт команды.

Acceptance: question/rubric review ≤20 минут; версионирование; все спорные scores имеют evidence;
можно пометить ошибку и отправить её в calibration backlog.

### Нанимающий менеджер — decision owner

Jobs:

- получить только кандидатов, которых предварительно проверил рекрутёр;
- просмотреть ranking/scorecard, recruiter notes и нужные video clips;
- увидеть unresolved gaps и подготовить финальное live интервью;
- не видеть кандидатов других команд и общую воронку.

Core JTBD:

> When recruiter assigns a candidate to my team, I want to see a concise evidence-backed profile
> and unresolved questions, so I can decide whom to invite and use live time for depth, soft
> skills and culture fit.

Acceptance: scoped access; review ≤7 минут; каждый technical claim связан с ответом; ranking
сравнивает только кандидатов одной interview version.

### Кандидат — end user

Jobs:

- пройти интервью без ожидания календарного слота и необходимости отпрашиваться;
- компенсировать неполное резюме реальными ответами;
- понимать продолжительность, запись, antifraud и роль ИИ;
- безопасно завершить интервью даже при нестабильной сети.

Pains:

- риск негативного восприятия «разговора с машиной»;
- избыток вопросов снижает completion;
- технический сбой может уничтожить ответ;
- камера и antifraud вызывают тревогу;
- нет возможности уточнить двусмысленный вопрос.

Core JTBD:

> When my resume does not fully show my ability, I want to answer a short, clear interview at a
> convenient time, so I can demonstrate my experience fairly and know that a person makes the
> final decision.

Acceptance: 5–7 вопросов; ожидаемая длительность ≤30 минут; device check; autosave per question;
resume; transparent consent; respectful language; confirmation of completion.

## 7. Question strategy для Python-пилота

Рекомендуемый interview blueprint — **6 основных вопросов, 25–30 минут**:

1. Biography/ownership: коротко описать последний релевантный проект и личную ответственность.
2. Python fundamentals: объяснить реальный trade-off, а не дать определение из учебника.
3. Concurrency/async: выбрать подход под конкретную I/O/CPU ситуацию и объяснить ограничения.
4. Data layer: разобрать транзакционность, consistency или performance на практическом примере.
5. Debugging/operations: рассказать о сложном инциденте, диагностике и проверке исправления.
6. System thinking: предложить верхнеуровневое решение и назвать риски/компромиссы.

Для каждого вопроса генерируются:

- competency IDs и grade-specific depth;
- positive/negative anchors без одного «идеального текста»;
- обязательные признаки конкретного личного вклада;
- ожидаемые альтернативные решения;
- условия `insufficient_information`;
- один optional follow-up вида «какова была конкретно ваша роль?» для уклончивого ответа.

Вариативность строится не свободной генерацией на каждого кандидата, а item bank:

```text
competency blueprint
  → 3–5 эквивалентных question variants
  → technical review
  → random assignment with logged item IDs
```

Так можно бороться с заучиванием, не разрушая сопоставимость. Jira и кодовая база команды в MVP
не подключаются.

## 8. Формат AI report

```json
{
  "recommendation": "fit | no_fit | additional_review",
  "confidence": 0.0,
  "evidence_sufficiency": "sufficient | partial | insufficient",
  "biography": {
    "motivation": "...",
    "relevant_experience": ["..."],
    "expectations": "..."
  },
  "competencies": [
    {
      "name": "Python concurrency",
      "score": 0,
      "max_score": 4,
      "evidence": [{"question_id": "q3", "quote": "...", "start_ms": 0}],
      "counter_evidence": [],
      "missing_information": [],
      "confidence": 0.0
    }
  ],
  "strengths": [],
  "risks": [],
  "follow_up_questions": [],
  "integrity_signals": [{"type": "tab_switch", "timestamp": "..."}],
  "limitations": [],
  "rubric_version": "python-mid-v1",
  "model_versions": {"asr": "...", "judge": "..."}
}
```

Правила:

- пустой evidence не превращается в отрицательное утверждение;
- resume и interview evidence показываются отдельно;
- противоречие между резюме и ответом становится risk, но не автоматическим fraud verdict;
- integrity signal не меняет technical score кодом;
- итоговый score агрегируется детерминированно из criterion scores;
- report writer не может изменить рекомендацию агрегатора.

## 9. Обновлённый Pain Map

Шкала 1–5; priority пересчитан по формуле
`round((severity×0,4 + frequency×0,3 + reach×0,2 + confidence×0,1)×10)`.

| Pain | Evidence from transcript | S | F | R | C | Priority |
|---|---|---:|---:|---:|---:|---:|
| Recruiter cannot manually process application volume | 6 700 откликов за неделю, обычно около 700 | 5 | 5 | 5 | 5 | **50** |
| Engineer time is spent on obviously unsuitable candidates | До 1,5 часа на technical interview | 5 | 5 | 5 | 5 | **50** |
| Resume-only screening loses strong candidates and performs poorly | HH/Cooku недостаточно точны; кандидаты плохо пишут CV | 5 | 4 | 5 | 5 | **47** |
| Weak candidates passing the system will destroy trust | Explicit pilot failure criterion | 5 | 4 | 5 | 5 | **47** |
| Fixed answers may hide lack of personal contribution | Нужен вопрос «какова была конкретно твоя роль?» | 4 | 4 | 4 | 5 | **41** |
| Too many questions reduce interview completion | Explicit conversion concern | 4 | 4 | 5 | 4 | **42** |
| Questions leak and become rehearsed | Rotation requested as optional improvement | 3 | 3 | 4 | 4 | **33** |
| Provider/data constraints are unresolved | Foreign models decision open; portability requested | 5 | 3 | 5 | 5 | **44** |

## 10. Hypotheses and normalized RICE

Чтобы не выдавать неизвестное число приглашённых за факт, Reach нормализован на **100 eligible
invited candidates per pilot batch**. Это единица сравнения, а не прогноз реальной конверсии из
700 откликов.

| Rank | Hypothesis | Validation metric | R | I | C | E | RICE |
|---:|---|---|---:|---:|---:|---:|---:|
| 1 | Versioned rubric + answer evidence даст ≥80% совпадения с adjudicated human recommendation | Exact agreement, macro-F1, balanced false pass/reject | 100 | 3 | 0,65 | 3,0 | **65,0** |
| 2 | Evidence card + recruiter notes сократят human review без потери контроля | Median recruiter review ≤5 минут; 100% scored claims with evidence | 100 | 2 | 0,80 | 2,5 | **64,0** |
| 3 | `additional_review` по недостатку evidence удержит качество при сокращении expert load | Coverage-quality curve; escalation share; error rate | 100 | 3 | 0,70 | 3,5 | **60,0** |
| 4 | Шесть открытых вопросов объединят biography и technical screen с приемлемой completion | Completion ≥70% from start; median duration ≤30 минут | 100 | 2 | 0,75 | 2,5 | **60,0** |
| 5 | AI draft + technical approval обеспечат relevant questions за ≤20 минут | Review time, rejection/edit rate, post-pilot item quality | 100 | 2 | 0,75 | 2,5 | **60,0** |
| 6 | Provider-neutral model gateway позволит сменить ASR/LLM без переписывания workflow | Swap one provider in ≤1 day; same contract/evaluation suite | 100 | 1 | 0,80 | 2,0 | **40,0** |
| 7 | Video + tab events выявят базовые integrity risks без автоматического отказа | Signal capture ≥95%; human usefulness; false allegation count | 100 | 1 | 0,70 | 2,0 | **35,0** |
| 8 | Reviewed item rotation снизит повтор вопросов без потери score comparability | Duplicate exposure, item difficulty drift, agreement by variant | 100 | 1 | 0,60 | 2,5 | **24,0** |

Tie-break при одинаковом RICE: выше Impact, затем Reach, затем ниже Effort. Поэтому hypothesis 3
идёт перед 4 и 5.

## 11. Lean Canvas для внутреннего продукта

### Problem

1. Recruiter throughput не соответствует сотням и тысячам откликов.
2. Engineers теряют до 1,5 часа на нерелевантных кандидатов.
3. Resume-only filtering пропускает слабых и теряет сильных кандидатов с плохим CV.

### Existing Alternatives

- HeadHunter/Cooku resume analysis;
- recruiter interview + engineer live interview;
- Zoom/Телемост и ручной feedback;
- Huntflow как CRM без автоматического интервью;
- внешние async/AI interview platforms.

### Solution

- combined biography + verbal technical async interview;
- AI-generated, technically approved question/rubric version;
- video, transcript, evidence-based scoring and insufficient-information state;
- recruiter notes, assignment and scoped manager access;
- expert calibration on the same videos.

### Unique Value Proposition

**Из 700 откликов к команде доходят кандидаты с проверяемым technical evidence, а инженер
подключается только к сложным случаям и финалу.**

### High-Level Concept

«Асинхронный первый и второй этап найма, собранные в один проверяемый interview dossier».

### Unfair Advantage

Потенциальное, ещё не доказанное: собственный набор Napoleon IT из реальных Python-вакансий,
interview videos, recruiter/technical labels и human overrides. iTalent Hub и связка с ИТМО могут
дать дополнительный контролируемый поток для улучшения question bank, но не заменяют валидацию на
реальном найме.

### Customer Segments

- internal recruiters;
- technical reviewers/interviewers;
- hiring managers;
- eligible IT candidates;
- sponsor: HR Director / recruiting lead.

### Early Adopter

Python hiring team с высоким потоком, утверждённым grade, доступным technical reviewer и
историческими примерами для blind evaluation.

### Key Metrics

- quality: exact agreement ≥80%, macro-F1, confusion matrix, balanced error rate;
- efficiency: expert escalation, target toward 5%; engineering hours saved;
- funnel: eligible → invited → started → completed → human-approved → final;
- UX: completion, duration, device/upload failures;
- trust: overrides, disagreement reasons, evidence coverage;
- cost: cost per completed screen and avoided engineering hours.

### Channels

Для внутреннего продукта: HeadHunter/company site/Telegram/referral → Huntflow → interview invite
by email or messenger. Распространение внутри компании через одну pilot hiring team и measured
case review.

### Cost Structure

Video storage/traffic; ASR/TTS/LLM; web/backend/queue; Russian data infrastructure; security;
technical review of questions; gold-label creation; calibration and candidate support.

### Revenue / Internal Value Capture

Внешней выручки нет. Эффект измеряется стоимостью высвобождённых engineering hours, сокращением
стоимости technical screens, time-to-shortlist и снижением потерь сильных кандидатов.

## 12. Проверка категории по существующим продуктам

Категория уже подтверждена рынком, поэтому MVP не должен тратить время на доказательство того,
что асинхронное видеоинтервью технически возможно:

- [HireVue](https://www.hirevue.com/platform/online-video-interviewing-software) предлагает
  on-demand и live video interviews, записи, structured rating scales/interview guides и ATS
  integrations; отдельный [assessment product](https://www.hirevue.com/platform/assessment-software)
  включает AI-scored interviews и coding challenges.
- [Hyring AI Interviewer](https://hyring.com/ai-interviewer) описывает async/live interview,
  генерацию вопросов из job description, transcript, scored report и technical pre-screen;
  [coding interviewer](https://hyring.com/ai-coding-interviewer) вынесен в отдельный продукт.
- [Interviewer.AI](https://interviewer.ai/asynchronous-video-interviews/) использует one-way link,
  scorecard и круглосуточное прохождение; это подтверждает привычный candidate flow, но не
  доказывает качество score для Napoleon IT.

Отличие Napoleon IT должно быть не в базовой записи видео, а в локально проверенном Python
rubric, evidence-first отчёте, human decision trail, российском data/model deployment и
измеренном сравнении с экспертами. Маркетинговые claims поставщиков нельзя использовать как
baseline пилота — качество проверяется только на собственном frozen dataset.

## 13. MVP scope

### P0 — обязательно для работающего demo

1. Recruiter login, vacancy draft, grade and requirements.
2. AI question + rubric draft; technical review/approve/publish.
3. Candidate invite link with expiration.
4. Consent placeholder, camera/mic check and respectful instructions.
5. Six-question interview: biography + verbal technical; per-question video/audio.
6. Upload status, resume and completion receipt.
7. Tab visibility event log and video available to humans.
8. ASR adapter + vacancy glossary.
9. Evidence extraction, criterion score, deterministic recommendation.
10. Recruiter report, video clips, transcript, notes and decision.
11. Candidate assignment and hiring-manager scoped view.
12. Blind benchmark page: AI vs recruiter+technical expert.

### P1 — если останется время

- one specificity follow-up;
- reviewed question variants;
- candidate ranking within one interview version;
- JSON/PDF export;
- minimal Huntflow deep link or CSV import/export;
- model comparison switch in admin.

### За пределами MVP

- live coding and executable IDE;
- unrestricted adaptive interviewer;
- automated face/emotion/voice confidence scoring;
- automatic reject/invite;
- recruiter workload balancing;
- personalized candidate feedback;
- production Huntflow integration;
- universal calibration for every role and grade.

## 14. Technical architecture

```text
Next.js/React candidate + staff UI
  ├─ FastAPI application API
  ├─ PostgreSQL: vacancy, rubric, interview, decisions, audit
  ├─ S3-compatible regional object storage: video/audio
  ├─ Redis/queue workers: upload finalize, ASR, evaluation
  ├─ Model Gateway
  │    ├─ ASR adapter
  │    ├─ TTS adapter
  │    └─ LLM judge adapter
  └─ Evaluation service: frozen datasets, metrics, comparisons
```

Provider-neutral contracts:

- `transcribe(media_uri, glossary, language) -> segments[]`;
- `extract_evidence(resume, answers, rubric) -> evidence[]`;
- `score_criteria(evidence, rubric) -> criterion_scores[]`;
- `aggregate(criterion_scores, rules) -> recommendation`;
- `render_report(immutable_scores) -> report`.

Хранить `provider`, `model_id`, `prompt_hash`, `rubric_version` и response IDs для каждого run.
Смена модели должна прогонять тот же frozen evaluation set до включения в production.

## 15. Pilot evaluation

### Gold label

Одна и та же видеозапись оценивается независимо:

1. recruiter — biography, motivation, expectations and overall recruiting risk;
2. technical expert — criterion-level technical score and recommendation;
3. disagreement — adjudication по заранее заданному правилу;
4. AI не видит human labels до завершения frozen run.

Gold recommendation нельзя просто брать из одного свободного комментария: технический и
рекрутёрский блоки должны иметь отдельные structured labels.

### Quality metrics

- exact agreement по `fit / no_fit / additional_review`, target ≥80%;
- macro-F1 и balanced accuracy;
- false-pass и false-reject с одинаковым весом;
- confusion matrix;
- agreement по must-have competencies;
- evidence precision: подтверждает ли цитата заявленный вывод;
- unsupported-claim rate;
- ASR technical-term accuracy;
- inter-rater agreement humans before judging AI.

### Efficiency metrics

- share escalated to technical specialist; business target toward 5%;
- engineering hours per 100 eligible candidates before/after;
- recruiter review minutes per report;
- cost per completed interview;
- time from invite to shortlist.

### Funnel metrics

```text
applications
→ pass minimum requirements
→ invited
→ opened
→ consented
→ started
→ completed
→ AI recommendation
→ recruiter approved
→ assigned to manager
→ final interview
```

На каждом переходе нужны абсолютное число и conversion. Нельзя интерпретировать высокую
точность на 20 завершивших интервью как успех, если большинство из 700 приглашённых отказалось.

### Gate sequence

1. Recording reliability.
2. ASR sufficiency.
3. Evidence correctness.
4. Human agreement ≥80% and balanced errors.
5. Acceptable candidate completion.
6. Expert escalation approaching 5%.
7. Cost and engineering-hour reduction.

## 16. Antifraud policy

P0 signals:

- tab hidden/visible timestamps;
- camera recording for human identity continuity review;
- multiple/unexpected audio stream flag only if technically reliable;
- answer start/stop/upload audit;
- explicit candidate rules before start.

No signal independently rejects a candidate. `tab_switch_count` is context, not guilt: the
candidate may open accessibility tools, recover a connection or accidentally switch. A real
подсказчик, как в кейсе Napoleon IT, должен быть виден/слышен reviewer и отмечен вручную.

Question preparation is allowed; leaked item-specific scripts are addressed through reviewed
rotation and prompts that require concrete personal context, trade-offs and follow-up evidence.

## 17. Data and legal architecture

- Candidate consent precedes any real recording.
- Store purpose, data categories, viewers, retention and deletion policy.
- Recruiter sees full funnel; manager receives server-side scoped access, not only an unguessable
  URL.
- Encrypt transport and stored media; log every report/video access.
- Keep primary Russian candidate data in an approved Russian storage/database architecture;
  review any foreign ASR/LLM transfer before use.
- Do not make decisions solely through automated processing; store human reviewer and action.
- If face/voice is used for identity recognition rather than ordinary recording, conduct a
  separate biometric/legal assessment.

Applicable considerations include [Article 16 of 152-FZ](https://www.consultant.ru/document/cons_doc_LAW_61801/22e884a41450dcb5cb62d956583ad32abe2bbbe9/)
on solely automated decisions, [Article 18](https://www.consultant.ru/document/cons_doc_LAW_61801/cbf4e15b7c330f9372e876cdf2bc928bad7950ef/)
on data collection/localization, and [Article 11](https://www.consultant.ru/document/cons_doc_LAW_61801/7336c78762a98b5f4f698b8c3800dca1111acc16/)
when biometric data is used for identification. This is product-risk guidance, not a legal
opinion.

## 18. What to ask Napoleon IT next

Use the offered 15–20 minute interview with HR Director/recruiting lead to obtain only missing
decision-grade inputs:

1. Из 700 Python-откликов сколько проходят минимальные требования, получают invite, начинают и
   завершают интервью?
2. Какой grade Python-разработчика выбран для pilot?
3. Какие must-have competencies и что является безусловным `no_fit`?
4. Есть ли structured expert labels или только свободный текст?
5. Сколько независимых размеченных видео можно использовать для development и frozen holdout?
6. Какова фактическая стоимость engineering hour и сколько technical interviews в месяц?
7. Какой максимальный `additional_review` rate допустим до потери экономического эффекта?
8. Где разрешено хранить media и каким model providers разрешено получать transcript/media?
9. Как долго хранить отклики, видео и AI reports?
10. Кто утверждает rubric и кто adjudicates disagreement между recruiter и technical expert?

## 19. Final recommendation

На хакатоне показать не «универсального ИИ-рекрутёра», а узкий, проверяемый Python funnel:

1. одна vacancy/grade;
2. шесть reviewed вопросов;
3. реальное browser video interview;
4. отчёт с criterion evidence и missing information;
5. human decision и notes;
6. side-by-side AI vs human benchmark;
7. model switch через единый adapter contract.

Сильная демонстрация заканчивается не красивым summary, а экраном: **где ИИ и люди согласились,
где разошлись, на каком evidence и сколько инженерных часов сохраняется на 100 кандидатов**.
