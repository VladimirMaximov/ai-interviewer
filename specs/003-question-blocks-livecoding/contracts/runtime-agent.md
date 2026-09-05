# Runtime Agent Contract

```json
{
  "response_id": "uuid",
  "question_id": "uuid",
  "question_text": "Расскажите про ваш проект.",
  "answer_kind": "spoken",
  "spoken_text": "Я отвечал за …",
  "source_code": null,
  "language": null
}
```

For a coding answer, `answer_kind` is `coding`, `spoken_text` is the transcript of the candidate's
verbal reasoning, and `source_code` plus `language` are set. The response retains recording offsets
for subsequent evidence review, but raw media is not in the outbound request. The accepted decision
has `confidence` from 0 to 1 and zero to two unique non-empty prompts. The current stub returns
`{"confidence": null, "follow_up_questions": []}`. Vacancy and resume never appear in this request.
