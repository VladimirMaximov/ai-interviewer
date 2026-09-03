"""Candidate-safe and manager-safe JSON/HTML projections."""

from __future__ import annotations

from html import escape

from interview_platform.domain.models import (
    Interview,
    InterviewStatus,
    PublicationStatus,
)


STATUS_LABELS = {
    "invited": "Приглашён",
    "in_progress": "В процессе",
    "submitted": "На проверке",
    "reviewed": "Проверено",
}


def _iso(value):
    return value.isoformat() if value is not None else None


def interview_summary(interview: Interview) -> dict:
    return {
        "id": interview.id,
        "candidate_alias": interview.candidate_alias,
        "position_title": interview.position_title,
        "status": interview.status.value,
        "evidence_type": interview.evidence_type,
        "created_at": _iso(interview.created_at),
        "updated_at": _iso(interview.updated_at),
    }


def _questions(interview: Interview) -> list[dict]:
    return [
        {
            "id": question.id,
            "prompt": question.prompt,
            "position": question.position,
            "required": question.required,
            "answer": interview.answers[question.id].content
            if question.id in interview.answers
            else None,
        }
        for question in interview.questions
    ]


def candidate_interview(
    interview: Interview,
    capture,
    *,
    published_feedback: dict | None = None,
    role_feedback_enabled: bool = False,
) -> dict:
    result = interview_summary(interview)
    result.update(
        {
            "questions": _questions(interview),
            "capture": {
                "kind": capture.kind,
                "available": True,
                "message": capture.message,
            },
            "feedback": None,
        }
    )
    if role_feedback_enabled:
        result["feedback"] = published_feedback
    elif interview.feedback and (
        interview.feedback.publication_status is PublicationStatus.PUBLISHED
    ):
        result["feedback"] = candidate_feedback(interview)
    return result


def candidate_feedback(interview: Interview) -> dict | None:
    feedback = interview.feedback
    if feedback is None or feedback.publication_status is not PublicationStatus.PUBLISHED:
        return None
    return {
        "candidate_summary": feedback.candidate_summary,
        "strengths": list(feedback.strengths),
        "next_steps": feedback.next_steps,
        "published_at": _iso(feedback.published_at),
        "version": feedback.version,
    }


def manager_interview(interview: Interview) -> dict:
    result = interview_summary(interview)
    result.update({"questions": _questions(interview), "feedback": None})
    if interview.feedback:
        feedback = interview.feedback
        result["feedback"] = {
            "id": feedback.id,
            "interview_id": feedback.interview_id,
            "candidate_summary": feedback.candidate_summary,
            "strengths": list(feedback.strengths),
            "risks": list(feedback.risks),
            "next_steps": feedback.next_steps,
            "internal_notes": feedback.internal_notes,
            "ai_recommendation": feedback.ai_recommendation,
            "recruiter_decision": feedback.recruiter_decision,
            "manager_decision": feedback.manager_decision.value,
            "publication_status": feedback.publication_status.value,
            "evidence": [
                {
                    "id": item.id,
                    "kind": item.kind.value,
                    "question_id": item.question_id,
                    "excerpt": item.excerpt,
                    "note": item.note,
                }
                for item in feedback.evidence
            ],
            "version": feedback.version,
            "published_at": _iso(feedback.published_at),
            "updated_at": _iso(feedback.updated_at),
        }
    return result


def _layout(*, title: str, portal: str, content: str) -> str:
    manager_navigation = (
        '<nav><a href="/manager">Интервью</a> · '
        '<a href="/manager/vacancies">Вакансии и критерии</a></nav>'
        if portal == "manager"
        else ""
    )
    recruiter_navigation = (
        '<nav><a href="/recruiter">Воронка</a></nav>'
        if portal == "recruiter"
        else ""
    )
    home = {"manager": "/manager", "recruiter": "/recruiter"}.get(portal, "/")
    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} · AI Interviewer</title>
  <link rel="stylesheet" href="/static/styles.css">
</head>
<body class="portal-{escape(portal)}">
  <header class="topbar">
    <a class="brand" href="{home}">AI Interviewer</a>
    {manager_navigation}{recruiter_navigation}
    <span class="portal-pill">{escape(portal)}</span>
  </header>
  <main class="shell">{content}</main>
  <footer>POC архитектуры · только synthetic-данные · без автоматических кадровых решений</footer>
</body>
</html>"""


def candidate_page(
    interview: Interview,
    token: str,
    capture,
    *,
    timeline: dict | None = None,
    published_feedback: dict | None = None,
    role_feedback_enabled: bool = False,
) -> str:
    answered = len(interview.answers)
    total = len(interview.questions)
    parts = [
        '<section class="hero candidate-hero">',
        '<span class="eyebrow">Кабинет кандидата</span>',
        f"<h1>{escape(interview.position_title)}</h1>",
        f'<p>Профиль: <strong>{escape(interview.candidate_alias)}</strong></p>',
        f'<div class="status"><span>{STATUS_LABELS[interview.status.value]}</span>'
        f"<span>{answered} / {total} ответов</span></div>",
        "</section>",
        f'<aside class="notice"><strong>Режим POC</strong><br>{escape(capture.message)}</aside>',
    ]
    if interview.status is InterviewStatus.INVITED:
        parts.append(
            f"""<section class="card action-card">
<h2>Перед началом</h2>
<p>Ответы будут сохранены для первичной проверки рекрутером. Видеозапись и анализ голоса не выполняются.</p>
<form method="post" action="/candidate/{escape(token)}/start">
  <label class="check"><input type="checkbox" name="consent" value="yes" required>
  Я согласен(на) на сохранение демонстрационных ответов</label>
  <button type="submit">Начать интервью</button>
</form>
</section>"""
        )
    elif interview.status is InterviewStatus.IN_PROGRESS:
        parts.append('<section class="stack"><h2>Вопросы интервью</h2>')
        for question in interview.questions:
            current = interview.answers.get(question.id)
            parts.append(
                f"""<article class="card question-card">
<div class="question-number">Вопрос {question.position}{' · обязательный' if question.required else ''}</div>
<h3>{escape(question.prompt)}</h3>
<form method="post" action="/candidate/{escape(token)}/answers/{escape(question.id)}">
  <textarea name="content" maxlength="10000" required placeholder="Текстовая имитация видеоответа">{escape(current.content if current else '')}</textarea>
  <button type="submit" class="secondary">Сохранить ответ</button>
</form>
</article>"""
            )
        parts.append(
            f"""<form class="submit-panel" method="post" action="/candidate/{escape(token)}/complete">
<p>Завершение заблокирует редактирование ответов.</p>
<button type="submit">Отправить на проверку</button>
</form></section>"""
        )
    else:
        parts.append('<section class="stack"><h2>Ваши ответы</h2>')
        for question in interview.questions:
            answer = interview.answers.get(question.id)
            parts.append(
                f'<article class="card"><div class="question-number">Вопрос {question.position}</div>'
                f'<h3>{escape(question.prompt)}</h3><p class="answer">'
                f'{escape(answer.content) if answer else "Нет ответа"}</p></article>'
            )
        parts.append("</section>")
    if timeline is not None and timeline.get("feedback_entries"):
        parts.append(_candidate_timeline_html(timeline))
    elif role_feedback_enabled:
        parts.append(_published_feedback_html(published_feedback))
    elif timeline is not None:
        parts.append(_candidate_timeline_html(timeline))
    else:
        parts.append(_candidate_feedback_html(interview))
    return _layout(title="Интервью", portal="candidate", content="".join(parts))


def _candidate_feedback_html(interview: Interview) -> str:
    feedback = candidate_feedback(interview)
    return _published_feedback_html(feedback)


def _published_feedback_html(feedback: dict | None) -> str:
    if feedback is None:
        return """<section class="card feedback pending">
<span class="eyebrow">Фидбэк</span><h2>Проверка продолжается</h2>
<p>Когда рекрутер опубликует результат, он появится здесь.</p></section>"""
    strengths = "".join(f"<li>{escape(item)}</li>" for item in feedback["strengths"])
    return f"""<section class="card feedback published">
<span class="eyebrow">Опубликованный фидбэк · версия {feedback['version']}</span>
<h2>Итог проверки</h2><p>{escape(feedback['candidate_summary'])}</p>
<h3>Сильные стороны</h3><ul>{strengths or '<li>Не указаны</li>'}</ul>
<h3>Следующие шаги</h3><p>{escape(feedback['next_steps'])}</p>
</section>"""


def _candidate_timeline_html(timeline: dict) -> str:
    entries = timeline.get("feedback_entries", [])
    if not entries:
        return """<section class="card feedback pending">
<span class="eyebrow">Фидбэк</span><h2>Проверка продолжается</h2>
<p>После проверки и ручной публикации здесь появится обратная связь.</p></section>"""
    cards = []
    stage_labels = {
        "post_async_assessment": "После асинхронной оценки",
        "post_human_review": "После проверки экспертом",
    }
    for entry in entries:
        sections = []
        for key, label in (
            ("assessment_scope", "Что оценивалось"),
            ("strengths", "Сильные стороны"),
            ("growth_areas", "Зоны роста"),
            ("evidence_gaps", "Чего не хватило в ответах"),
            ("limitations", "Ограничения оценки"),
        ):
            values = entry.get(key, [])
            if values:
                sections.append(
                    f"<h3>{label}</h3><ul>"
                    + "".join(f"<li>{escape(value)}</li>" for value in values)
                    + "</ul>"
                )
        correction = (
            '<p class="notice compact">Это уточняющая публикация.</p>'
            if entry.get("correction_of_revision_id")
            else ""
        )
        cards.append(
            f"""<article class="card feedback published">
<span class="eyebrow">{escape(stage_labels.get(entry['stage'], entry['stage']))}</span>
{correction}{''.join(sections)}<h3>Следующие шаги</h3>
<p>{escape(entry['next_steps'])}</p></article>"""
        )
    return '<section class="stack"><h2>История обратной связи</h2>' + "".join(cards) + "</section>"


def manager_list_page(interviews: list[Interview]) -> str:
    rows = "".join(
        f"""<tr><td><a href="/manager/interviews/{escape(item.id)}">{escape(item.candidate_alias)}</a></td>
<td>{escape(item.position_title)}</td><td><span class="state state-{item.status.value}">{STATUS_LABELS[item.status.value]}</span></td>
<td>{escape(item.updated_at.strftime('%d.%m %H:%M'))}</td></tr>"""
        for item in interviews
    ) or '<tr><td colspan="4">Интервью ещё нет</td></tr>'
    content = f"""<section class="hero manager-hero"><span class="eyebrow">Кабинет менеджера</span>
<h1>Интервью кандидатов</h1><p>Ответы, доказательства и ручные решения — отдельно от AI.</p>
<p><a class="button secondary" href="/manager/vacancies">Настроить вакансии и критерии →</a></p></section>
<section class="dashboard-grid"><div class="card table-card"><h2>Воронка</h2>
<div class="table-scroll"><table><thead><tr><th>Кандидат</th><th>Позиция</th><th>Статус</th><th>Обновлено</th></tr></thead>
<tbody>{rows}</tbody></table></div></div>
<div class="card create-card"><h2>Новое приглашение</h2>
<form method="post" action="/manager/interviews">
<label>Синтетический alias<input name="candidate_alias" maxlength="120" required placeholder="synthetic-candidate-002"></label>
<label>Позиция<input name="position_title" maxlength="120" required placeholder="Python Developer"></label>
<label>Вопросы, по одному в строке<textarea name="questions" required placeholder="Расскажите о сложном проекте&#10;Как вы тестируете код?"></textarea></label>
<button type="submit">Создать приглашение</button></form></div></section>"""
    return _layout(title="Кабинет менеджера", portal="manager", content=content)


def vacancy_list_page(vacancies: list[dict], framework: dict) -> str:
    rows = "".join(
        f"""<tr><td><a href="/manager/vacancies/{escape(item['id'])}">{escape(item['title'])}</a></td>
<td>{escape(item['role_key'])}</td><td>{escape(item['target_level_key'])}</td>
<td><span class="state">{escape(item['status'])}</span></td></tr>"""
        for item in vacancies
    ) or '<tr><td colspan="4">Вакансий ещё нет</td></tr>'
    role_options = "".join(
        f'<option value="{escape(role["role_key"])}:{escape(level)}">'
        f'{escape(role["display_name"])} · {escape(level)}</option>'
        for role in framework.get("role_profiles", [])
        for level in role.get("level_keys", [])
    )
    content = f"""<section class="hero manager-hero"><span class="eyebrow">Контекст оценки</span>
<h1>Вакансии и отдельные критерии</h1>
<p>Корпоративная матрица и ожидания вакансии оцениваются независимо.</p></section>
<section class="dashboard-grid"><div class="card table-card"><h2>Вакансии</h2>
<div class="table-scroll"><table><thead><tr><th>Название</th><th>Роль</th><th>Уровень</th><th>Статус</th></tr></thead>
<tbody>{rows}</tbody></table></div></div><div class="card create-card"><h2>Новая вакансия</h2>
<form method="post" action="/manager/vacancies">
<label>Название<input name="title" required placeholder="Python Developer"></label>
<label>Профиль роли и целевой уровень<select name="role_level">{role_options}</select></label>
<button type="submit">Создать вакансию</button></form></div></section>"""
    return _layout(title="Вакансии", portal="manager", content=content)


def vacancy_detail_page(
    vacancy: dict,
    sources: list[dict],
    profiles: list[dict],
    snapshots: list[dict],
    assignments: list[dict],
    rankings: list[dict],
    *,
    can_invite: bool = True,
) -> str:
    source_items = "".join(
        f"<li><strong>{escape(item['display_name'])}</strong> · {escape(item['source_type'])}"
        f"<br><small>{escape(item['extracted_text'][:240])}</small></li>"
        for item in sources
    ) or "<li>Источников пока нет</li>"
    profile_cards = []
    for profile in profiles:
        criteria = "".join(
            f"<li><strong>{escape(item['display_name'])}</strong> · вес {item['weight']} · "
            f"{escape(item['category'])}<br><small>{escape(item['description'])}</small></li>"
            for item in profile.get("criteria", [])
        )
        approve = ""
        if profile["status"] in {"draft", "validation_failed"}:
            approve = f"""<form method="post" action="/manager/vacancies/{escape(vacancy['id'])}/profiles/{escape(profile['id'])}/approve">
<button type="submit">Подтвердить и утвердить версию</button></form>"""
        profile_cards.append(
            f"""<article class="card"><span class="eyebrow">Версия {profile['version']} · {escape(profile['status'])}</span>
<p>{escape(profile['summary'])}</p><h3>Отдельные критерии вакансии</h3><ol>{criteria}</ol>{approve}</article>"""
        )
    assignment_items = "".join(
        f'<li><a href="/manager/interviews/{escape(item["interview_id"])}">'
        f'{escape(item["interview_id"])}</a></li>'
        for item in assignments
    ) or "<li>Назначений пока нет; создать их можно через API после snapshot.</li>"
    invitation_form = ""
    if snapshots and can_invite:
        snapshot_options = "".join(
            f'<option value="{escape(item["id"])}">profile v{item["profile_version"]} · '
            f'{escape(item["context_hash"][:10])}</option>'
            for item in snapshots
        )
        invitation_form = f"""<form method="post" action="/manager/vacancies/{escape(vacancy['id'])}/interviews">
<label>Assessment snapshot<select name="snapshot_id">{snapshot_options}</select></label>
<label>Синтетический alias<input name="candidate_alias" required placeholder="synthetic-candidate"></label>
<button type="submit">Создать приглашение по вакансии</button></form>"""
    elif snapshots:
        invitation_form = (
            "<p>Приглашение создаёт рекрутёр; менеджер управляет критериями, "
            "оценкой и своим решением.</p>"
        )
    active_actions = ""
    if vacancy.get("active_profile_version_id"):
        active_actions = f"""<form method="post" action="/manager/vacancies/{escape(vacancy['id'])}/snapshot">
<button type="submit" class="secondary">Зафиксировать assessment snapshot</button></form>"""
    draft_action = (
        f"""<form method="post" action="/manager/vacancies/{escape(vacancy['id'])}/draft">
<button type="submit">Сформировать черновик из всех источников</button></form>"""
        if sources
        else ""
    )
    ranking_cards = []
    for ranking in rankings:
        rows = "".join(
            f"<tr><td>{item['rank'] if item['rank'] is not None else 'review'}</td>"
            f"<td>{escape(item['candidate_alias'])}</td><td>{item.get('primary_value')}</td>"
            f"<td>{item.get('secondary_value')}</td><td>{item.get('evidence_coverage')}</td></tr>"
            for item in ranking.get("entries", [])
        )
        ranking_cards.append(
            f"""<article class="card" id="ranking-{escape(ranking['id'])}"><span class="eyebrow">Неизменяемый ranking snapshot</span>
<div class="table-scroll"><table><thead><tr><th>Ранг</th><th>Кандидат</th><th>Vacancy fit</th><th>Компетенции</th><th>Coverage</th></tr></thead><tbody>{rows}</tbody></table></div>
<p><small>Порядок не является кадровым решением.</small></p></article>"""
        )
    ranking_form = ""
    if snapshots:
        options = "".join(
            f'<option value="{escape(item["id"])}">profile v{item["profile_version"]} · {escape(item["context_hash"][:10])}</option>'
            for item in snapshots
        )
        ranking_form = f"""<form method="post" action="/manager/vacancies/{escape(vacancy['id'])}/ranking">
<label>Сравнимый assessment snapshot<select name="context_snapshot_id">{options}</select></label>
<button type="submit" class="secondary">Построить рейтинг завершённых оценок</button></form>"""
    content = f"""<a class="back" href="/manager/vacancies">← Все вакансии</a>
<section class="hero manager-hero"><span class="eyebrow">{escape(vacancy['role_key'])} · {escape(vacancy['target_level_key'])}</span>
<h1>{escape(vacancy['title'])}</h1><p>Статус: {escape(vacancy['status'])}</p>{active_actions}</section>
<section class="dashboard-grid"><div class="card"><h2>Добавить ожидания менеджера</h2>
<form method="post" action="/manager/vacancies/{escape(vacancy['id'])}/sources">
<label>Тип<select name="source_type"><option value="phrase">Короткая фраза</option><option value="pasted_text">Текст</option><option value="speech_transcript">Расшифровка речи</option></select></label>
<label>Название<input name="display_name" value="Бриф менеджера" required></label>
<label>Что важно для этой вакансии<textarea name="text" required placeholder="Нужен опыт эволюции API без остановки клиентов"></textarea></label>
<button type="submit">Добавить источник</button></form>
<hr><form method="post" enctype="multipart/form-data" action="/manager/vacancies/{escape(vacancy['id'])}/sources">
<label>Или UTF-8 .txt/.md файл<input type="file" name="file" accept=".txt,.md,.markdown" required></label>
<button type="submit" class="secondary">Загрузить файл</button></form></div>
<div class="card"><h2>Проверенные источники</h2><ul>{source_items}</ul>{draft_action}</div></section>
<section class="stack"><h2>Версии профиля</h2>{''.join(profile_cards) or '<p>Создайте источник и сформируйте черновик.</p>'}</section>
<section class="card"><h2>Назначенные интервью</h2><ul>{assignment_items}</ul>{invitation_form}</section>
<section class="stack"><h2>Сравнение кандидатов</h2>{ranking_form}{''.join(ranking_cards)}</section>"""
    return _layout(title=vacancy["title"], portal="manager", content=content)


def manager_detail_page(
    interview: Interview,
    *,
    vacancy_aware: bool = False,
    assessment_runs: list[dict] | None = None,
    decisions: list[dict] | None = None,
    feedback_entries: list[dict] | None = None,
) -> str:
    answer_cards = []
    for question in interview.questions:
        answer = interview.answers.get(question.id)
        answer_cards.append(
            f"""<article class="card evidence-card"><div class="question-number">Вопрос {question.position}</div>
<h3>{escape(question.prompt)}</h3><pre>{escape(answer.content) if answer else 'Недостаточно информации: ответ отсутствует'}</pre></article>"""
        )
    feedback = interview.feedback
    first_evidence = feedback.evidence[0] if feedback and feedback.evidence else None
    options = "".join(
        f'<option value="{escape(question.id)}"'
        f'{" selected" if first_evidence and first_evidence.question_id == question.id else ""}>'
        f'Вопрос {question.position}</option>'
        for question in interview.questions
    )
    selected_decision = feedback.manager_decision.value if feedback else "hold"
    decision_options = "".join(
        f'<option value="{value}"{" selected" if value == selected_decision else ""}>{label}</option>'
        for value, label in (("advance", "Продолжить"), ("hold", "Нужна доп. проверка"), ("reject", "Не продолжать"))
    )
    evidence_kind = first_evidence.kind.value if first_evidence else "answer_excerpt"
    feedback_form = ""
    if interview.status in {InterviewStatus.SUBMITTED, InterviewStatus.REVIEWED}:
        draft_button = (
            '<button name="publish" value="no" class="secondary">Сохранить черновик</button>'
            if interview.status is InterviewStatus.SUBMITTED
            else ""
        )
        feedback_form = f"""<section class="card review-form"><h2>Ручной фидбэк</h2>
<p class="notice compact">Каждый вывод должен ссылаться на точный фрагмент ответа или явно фиксировать нехватку данных.</p>
<form method="post" action="/manager/interviews/{escape(interview.id)}/feedback">
<label>Итог для кандидата<textarea name="candidate_summary" required>{escape(feedback.candidate_summary if feedback else '')}</textarea></label>
<label>Сильные стороны, по одной в строке<textarea name="strengths">{escape(chr(10).join(feedback.strengths) if feedback else '')}</textarea></label>
<label>Риски, только для менеджера<textarea name="risks">{escape(chr(10).join(feedback.risks) if feedback else '')}</textarea></label>
<label>Следующие шаги<textarea name="next_steps" required>{escape(feedback.next_steps if feedback else '')}</textarea></label>
<label>Внутренняя заметка<textarea name="internal_notes">{escape(feedback.internal_notes if feedback else '')}</textarea></label>
<label>Ручное решение<select name="manager_decision">{decision_options}</select></label>
<fieldset><legend>Доказательство</legend>
<label>Вопрос<select name="question_id">{options}</select></label>
<label>Тип<select name="evidence_kind">
<option value="answer_excerpt"{' selected' if evidence_kind == 'answer_excerpt' else ''}>Точный фрагмент ответа</option>
<option value="insufficient_information"{' selected' if evidence_kind == 'insufficient_information' else ''}>Недостаточно информации</option></select></label>
<label>Фрагмент ответа<textarea name="excerpt">{escape(first_evidence.excerpt if first_evidence and first_evidence.excerpt else '')}</textarea></label>
<label>Что подтверждает / чего не хватает<textarea name="evidence_note" required>{escape(first_evidence.note if first_evidence else '')}</textarea></label>
</fieldset><div class="button-row">{draft_button}
<button name="publish" value="yes">Опубликовать кандидату</button></div></form></section>"""
    vacancy_sections = ""
    if vacancy_aware:
        vacancy_sections = _vacancy_assessment_html(
            interview,
            assessment_runs or [],
            decisions or [],
            feedback_entries or [],
        )
    content = f"""<a class="back" href="/manager">← Все интервью</a>
<section class="hero manager-hero"><span class="eyebrow">{escape(interview.candidate_alias)}</span>
<h1>{escape(interview.position_title)}</h1><div class="status"><span>{STATUS_LABELS[interview.status.value]}</span>
<span>{len(interview.answers)} / {len(interview.questions)} ответов</span></div></section>
<section class="stack"><h2>Evidence</h2>{''.join(answer_cards)}</section>{vacancy_sections}{feedback_form}"""
    return _layout(title=interview.candidate_alias, portal="manager", content=content)


def _vacancy_assessment_html(
    interview: Interview,
    assessment_runs: list[dict],
    decisions: list[dict],
    feedback_entries: list[dict],
) -> str:
    assessment_cards = []
    for run in assessment_runs:
        dimensions = []
        for summary in run.get("dimension_summaries", []):
            label = (
                "Корпоративные компетенции"
                if summary["dimension"] == "corporate_competency"
                else "Соответствие конкретной вакансии"
            )
            dimensions.append(
                f"<li><strong>{label}:</strong> {summary.get('score')} / 100 · "
                f"покрытие evidence {summary.get('evidence_coverage')}</li>"
            )
        evidence = "".join(
            f"<li><strong>{escape(item.get('criterion_title', item['criterion_id']))}</strong> · "
            f"{escape(item['label'])}<br><small>{escape(item['evidence'][0].get('excerpt') or item['evidence'][0]['note'])}</small></li>"
            for item in run.get("criterion_assessments", [])
        )
        signals = run.get("integrity_signals", [])
        signal_html = (
            "<h3>Integrity-события (не влияют на score)</h3><ul>"
            + "".join(
                f"<li>{escape(str(item.get('kind', 'event')))}: "
                f"{escape(str(item.get('note', '')))}</li>"
                for item in signals
            )
            + "</ul>"
            if signals
            else "<p><small>Integrity-событий не зафиксировано; они не входят в score.</small></p>"
        )
        assessment_cards.append(
            f"""<article class="card"><span class="eyebrow">Assessment run {run['run_number']}</span>
<p>Два независимых измерения; coverage не является оценкой кандидата.</p>
<ul>{''.join(dimensions)}</ul>{signal_html}<details><summary>Критерии и доказательства</summary><ol>{evidence}</ol></details></article>"""
        )
    assessment_action = ""
    if interview.status in {InterviewStatus.SUBMITTED, InterviewStatus.REVIEWED}:
        assessment_action = f"""<form method="post" action="/manager/interviews/{escape(interview.id)}/assessment-runs">
<button type="submit">{'Повторить оценку' if assessment_runs else 'Запустить оценку'}</button></form>"""
    decision_items = "".join(
        f"<li><strong>{escape(item['actor_role'])}: {escape(item['decision'])}</strong> — "
        f"{escape(item['reason'])}</li>"
        for item in decisions
    ) or "<li>Решений нет. Рейтинг не принимает решение автоматически.</li>"
    decision_form = f"""<form method="post" action="/manager/interviews/{escape(interview.id)}/decisions">
<label>Роль<select name="actor_role"><option value="hiring_manager">Hiring manager</option><option value="technical_expert">Technical expert</option><option value="recruiter">Recruiter</option></select></label>
<label>Решение<select name="decision"><option value="hold">Нужна проверка</option><option value="advance">Продолжить</option><option value="request_more_evidence">Запросить evidence</option><option value="reject">Не продолжать</option></select></label>
<label>Обоснование<textarea name="reason" required></textarea></label><button type="submit">Добавить человеческое решение</button></form>"""
    feedback_history = "".join(
        f"<li><strong>{escape(item['stage'])}</strong> · "
        f"{escape(item['revisions'][-1]['status'])} · ревизий {len(item['revisions'])}</li>"
        for item in feedback_entries
    ) or "<li>Публикаций ещё нет</li>"
    feedback_form = f"""<form method="post" action="/manager/interviews/{escape(interview.id)}/feedback-entries">
<input type="hidden" name="stage" value="post_human_review">
<label>Что оценивалось<textarea name="assessment_scope" required></textarea></label>
<label>Сильные стороны<textarea name="strengths"></textarea></label>
<label>Зоны роста<textarea name="growth_areas"></textarea></label>
<label>Пробелы в evidence<textarea name="evidence_gaps"></textarea></label>
<label>Ограничения оценки<textarea name="limitations"></textarea></label>
<label>Следующие шаги<textarea name="next_steps" required></textarea></label>
<label>Внутренняя заметка<textarea name="internal_notes"></textarea></label>
<div class="button-row"><button class="secondary" name="publish" value="no">Черновик</button>
<button name="publish" value="yes">Опубликовать кандидату</button></div></form>"""
    return f"""<section class="stack"><h2>Оценка по вакансии</h2>{''.join(assessment_cards) or '<p>Assessment ещё не запускался.</p>'}{assessment_action}</section>
<section class="dashboard-grid"><div class="card"><h2>Решения людей</h2><ul>{decision_items}</ul>{decision_form}</div>
<div class="card"><h2>Двухэтапный feedback</h2><ul>{feedback_history}</ul>{feedback_form}</div></section>"""


def invitation_created_page(candidate_url: str, *, portal: str = "manager") -> str:
    safe_url = escape(candidate_url)
    back_url = "/recruiter" if portal == "recruiter" else "/manager"
    content = f"""<section class="card success-card"><span class="eyebrow">Приглашение создано</span>
<h1>Скопируйте ссылку сейчас</h1><p>Raw-токен больше не будет показан в кабинете.</p>
<code>{safe_url}</code><div class="button-row"><a class="button" href="{safe_url}">Открыть как кандидат</a>
<a class="button secondary" href="{back_url}">Вернуться в кабинет</a></div></section>"""
    return _layout(title="Приглашение создано", portal=portal, content=content)


def error_page(message: str, status: int) -> str:
    content = f"""<section class="card error-card"><span class="eyebrow">Ошибка {status}</span>
<h1>Не удалось выполнить действие</h1><p>{escape(message)}</p><a class="button secondary" href="/">На главную</a></section>"""
    return _layout(title="Ошибка", portal="candidate", content=content)


def recruiter_review_dict(review) -> dict | None:
    if review is None:
        return None
    return {
        "id": review.id,
        "interview_id": review.interview_id,
        "candidate_summary": review.candidate_summary,
        "strengths": list(review.strengths),
        "risks": list(review.risks),
        "next_steps": review.next_steps,
        "internal_notes": review.internal_notes,
        "recruiter_decision": review.recruiter_decision.value,
        "assigned_manager": review.assigned_manager,
        "publication_status": review.publication_status.value,
        "evidence": [
            {
                "id": item.id,
                "kind": item.kind.value,
                "question_id": item.question_id,
                "excerpt": item.excerpt,
                "note": item.note,
            }
            for item in review.evidence
        ],
        "version": review.version,
        "published_at": _iso(review.published_at),
        "updated_at": _iso(review.updated_at),
    }


def manager_review_dict(review) -> dict | None:
    if review is None:
        return None
    return {
        "id": review.id,
        "interview_id": review.interview_id,
        "manager_id": review.manager_id,
        "manager_decision": review.manager_decision.value,
        "notes": review.notes,
        "reviewed_at": _iso(review.reviewed_at),
    }


def staff_interview(interview: Interview, recruiter_review, manager_review) -> dict:
    result = interview_summary(interview)
    result.update(
        {
            "questions": _questions(interview),
            "ai_recommendation": None,
            "recruiter_review": recruiter_review_dict(recruiter_review),
            "manager_review": manager_review_dict(manager_review),
        }
    )
    return result


def portal_landing_page() -> str:
    content = """<section class="hero candidate-hero"><span class="eyebrow">AI Interviewer</span>
<h1>Три роли — три отдельных кабинета</h1><p>Каждый участник видит только свой этап процесса.</p></section>
<section class="role-grid">
<article class="card"><span class="eyebrow">Кандидат</span><h2>Пройти интервью</h2>
<p>Доступ только по персональной ссылке из приглашения.</p></article>
<article class="card"><span class="eyebrow">Рекрутер</span><h2>Управлять воронкой</h2>
<p>Создание приглашений, проверка ответов, фидбэк и назначение менеджера.</p>
<a class="button" href="/recruiter">В кабинет рекрутера</a></article>
<article class="card"><span class="eyebrow">Менеджер</span><h2>Рассмотреть назначенных</h2>
<p>Только назначенные кандидаты и отдельное решение менеджера.</p>
<a class="button" href="/manager">В кабинет менеджера</a></article></section>"""
    return _layout(title="Выбор роли", portal="public", content=content)


def recruiter_list_page(interviews: list[Interview], reviews: dict[str, object]) -> str:
    rows = "".join(
        f"""<tr><td><a href="/recruiter/interviews/{escape(item.id)}">{escape(item.candidate_alias)}</a></td>
<td>{escape(item.position_title)}</td><td><span class="state state-{item.status.value}">{STATUS_LABELS[item.status.value]}</span></td>
<td>{escape((reviews[item.id].assigned_manager if reviews.get(item.id) else None) or 'Не назначен')}</td></tr>"""
        for item in interviews
    ) or '<tr><td colspan="4">Интервью ещё нет</td></tr>'
    content = f"""<section class="hero recruiter-hero"><span class="eyebrow">Кабинет рекрутера</span>
<h1>Воронка интервью</h1><p>Приглашения, первичный review, фидбэк кандидату и передача менеджеру.</p></section>
<section class="dashboard-grid"><div class="card table-card"><h2>Все кандидаты</h2>
<div class="table-scroll"><table><thead><tr><th>Кандидат</th><th>Позиция</th><th>Статус</th><th>Менеджер</th></tr></thead>
<tbody>{rows}</tbody></table></div></div>
<div class="card create-card"><h2>Новое приглашение</h2>
<form method="post" action="/recruiter/interviews">
<label>Синтетический alias<input name="candidate_alias" maxlength="120" required placeholder="synthetic-candidate-002"></label>
<label>Позиция<input name="position_title" maxlength="120" required placeholder="Python Developer"></label>
<label>Вопросы, по одному в строке<textarea name="questions" required></textarea></label>
<button type="submit">Создать приглашение</button></form></div></section>"""
    return _layout(title="Кабинет рекрутера", portal="recruiter", content=content)


def _answer_cards(interview: Interview) -> str:
    cards = []
    for question in interview.questions:
        answer = interview.answers.get(question.id)
        cards.append(
            f"""<article class="card evidence-card">
<div class="question-number">Вопрос {question.position}</div>
<h3>{escape(question.prompt)}</h3>
<pre>{escape(answer.content) if answer else 'Недостаточно информации: ответ отсутствует'}</pre>
</article>"""
        )
    return "".join(cards)


def recruiter_detail_page(interview: Interview, review, manager_review, manager_id: str) -> str:
    first_evidence = review.evidence[0] if review and review.evidence else None
    question_options = "".join(
        f'<option value="{escape(question.id)}">'
        f"Вопрос {question.position}</option>"
        for question in interview.questions
    )
    current_decision = review.recruiter_decision.value if review else "hold"
    decision_options = "".join(
        f'<option value="{value}"'
        f'{" selected" if value == current_decision else ""}>{label}</option>'
        for value, label in (
            ("advance", "Передать дальше"),
            ("hold", "Нужна дополнительная проверка"),
            ("reject", "Не продолжать"),
        )
    )
    review_form = ""
    if interview.status in {InterviewStatus.SUBMITTED, InterviewStatus.REVIEWED}:
        draft_button = (
            '<button name="publish" value="no" class="secondary">'
            "Сохранить черновик</button>"
            if not review or review.publication_status is not PublicationStatus.PUBLISHED
            else ""
        )
        review_form = f"""<section class="card review-form">
<h2>Review рекрутера</h2>
<p class="notice compact">Фидбэк рекрутера и решение менеджера хранятся отдельно.</p>
<form method="post" action="/recruiter/interviews/{escape(interview.id)}/review">
<label>Итог для кандидата<textarea name="candidate_summary" required>{escape(review.candidate_summary if review else '')}</textarea></label>
<label>Сильные стороны<textarea name="strengths">{escape(chr(10).join(review.strengths) if review else '')}</textarea></label>
<label>Риски для команды<textarea name="risks">{escape(chr(10).join(review.risks) if review else '')}</textarea></label>
<label>Следующие шаги<textarea name="next_steps" required>{escape(review.next_steps if review else '')}</textarea></label>
<label>Внутренняя заметка<textarea name="internal_notes">{escape(review.internal_notes if review else '')}</textarea></label>
<label>Решение рекрутера<select name="recruiter_decision">{decision_options}</select></label>
<label>Назначенный менеджер<input name="assigned_manager" value="{escape(review.assigned_manager if review and review.assigned_manager else manager_id)}"></label>
<fieldset><legend>Evidence</legend>
<label>Вопрос<select name="question_id">{question_options}</select></label>
<label>Тип<select name="evidence_kind">
<option value="answer_excerpt">Точный фрагмент ответа</option>
<option value="insufficient_information">Недостаточно информации</option>
</select></label>
<label>Фрагмент ответа<textarea name="excerpt">{escape(first_evidence.excerpt if first_evidence and first_evidence.excerpt else '')}</textarea></label>
<label>Что подтверждает evidence<textarea name="evidence_note" required>{escape(first_evidence.note if first_evidence else '')}</textarea></label>
</fieldset>
<div class="button-row">{draft_button}
<button name="publish" value="yes">Опубликовать кандидату</button></div>
</form></section>"""
    manager_state = (
        f"<p><strong>{escape(manager_review.manager_decision.value)}</strong> — "
        f"{escape(manager_review.notes)}</p>"
        if manager_review
        else "<p>Менеджер ещё не оставил решение.</p>"
    )
    content = f"""<a class="back" href="/recruiter">← Вся воронка</a>
<section class="hero recruiter-hero"><span class="eyebrow">{escape(interview.candidate_alias)}</span>
<h1>{escape(interview.position_title)}</h1>
<div class="status"><span>{STATUS_LABELS[interview.status.value]}</span>
<span>{len(interview.answers)} / {len(interview.questions)} ответов</span></div></section>
<section class="stack"><h2>Ответы кандидата</h2>{_answer_cards(interview)}</section>
{review_form}
<section class="card feedback"><h2>Независимый review менеджера</h2>{manager_state}</section>"""
    return _layout(title=interview.candidate_alias, portal="recruiter", content=content)


def assigned_manager_list_page(interviews: list[Interview], manager_id: str) -> str:
    rows = "".join(
        f"""<tr>
<td><a href="/manager/interviews/{escape(item.id)}">{escape(item.candidate_alias)}</a></td>
<td>{escape(item.position_title)}</td>
<td><span class="state state-{item.status.value}">{STATUS_LABELS[item.status.value]}</span></td>
</tr>"""
        for item in interviews
    ) or '<tr><td colspan="3">Рекрутер пока не назначил вам кандидатов</td></tr>'
    content = f"""<section class="hero manager-hero">
<span class="eyebrow">Кабинет менеджера · {escape(manager_id)}</span>
<h1>Назначенные кандидаты</h1>
<p>Здесь нет создания приглашений и управления воронкой — только hiring review.</p>
</section>
<section class="card table-card"><h2>Мои кандидаты</h2>
<div class="table-scroll"><table><thead><tr>
<th>Кандидат</th><th>Позиция</th><th>Статус</th>
</tr></thead><tbody>{rows}</tbody></table></div></section>"""
    return _layout(title="Кабинет менеджера", portal="manager", content=content)


def assigned_manager_detail_page(interview: Interview, recruiter_review, manager_review) -> str:
    review_html = "<p>Рекрутер ещё не завершил review.</p>"
    if recruiter_review:
        evidence = "".join(
            f"""<li><strong>{escape(item.kind.value)}</strong>:
{escape(item.excerpt or 'Недостаточно информации')} — {escape(item.note)}</li>"""
            for item in recruiter_review.evidence
        )
        review_html = f"""<p>{escape(recruiter_review.candidate_summary)}</p>
<p><strong>Решение рекрутера:</strong> {escape(recruiter_review.recruiter_decision.value)}</p>
<p><strong>Внутренняя заметка:</strong> {escape(recruiter_review.internal_notes or 'Нет')}</p>
<h3>Evidence</h3><ul>{evidence}</ul>"""
    current_decision = manager_review.manager_decision.value if manager_review else "hold"
    options = "".join(
        f'<option value="{value}"'
        f'{" selected" if value == current_decision else ""}>{label}</option>'
        for value, label in (
            ("advance", "Продолжить"),
            ("hold", "Нужна дополнительная проверка"),
            ("reject", "Не продолжать"),
        )
    )
    content = f"""<a class="back" href="/manager">← Мои кандидаты</a>
<section class="hero manager-hero"><span class="eyebrow">{escape(interview.candidate_alias)}</span>
<h1>{escape(interview.position_title)}</h1></section>
<section class="stack"><h2>Ответы кандидата</h2>{_answer_cards(interview)}</section>
<section class="card feedback"><h2>Review рекрутера</h2>{review_html}</section>
<section class="card review-form"><h2>Отдельное решение менеджера</h2>
<form method="post" action="/manager/interviews/{escape(interview.id)}/decision">
<label>Решение<select name="manager_decision">{options}</select></label>
<label>Комментарий<textarea name="notes" required>{escape(manager_review.notes if manager_review else '')}</textarea></label>
<button type="submit">Сохранить решение менеджера</button>
</form></section>"""
    return _layout(title=interview.candidate_alias, portal="manager", content=content)
