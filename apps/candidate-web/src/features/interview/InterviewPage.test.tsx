import { describe, expect, it } from "vitest";

import {
  COMPLETION_BODY,
  COMPLETION_NEXT_STEP,
  COMPLETION_TITLE,
  initialInterviewMessage,
  shouldShowQuestion,
} from "./interviewPresentation";

describe("InterviewPage presentation contract", () => {
  it("does not reveal a question before continuous recording starts", () => {
    expect(shouldShowQuestion(false)).toBe(false);
    expect(shouldShowQuestion(true)).toBe(true);
  });

  it("reuses a granted preflight stream without stale permission copy", () => {
    expect(initialInterviewMessage(true)).not.toContain("Разрешите доступ");
    expect(initialInterviewMessage(true)).toContain("первый вопрос");
  });

  it("shows a recruiter-facing next step instead of processing internals", () => {
    expect(`${COMPLETION_TITLE} ${COMPLETION_BODY} ${COMPLETION_NEXT_STEP}`).not.toMatch(
      /расшифров|очеред|модел/i,
    );
    expect(COMPLETION_NEXT_STEP).toContain("рекрутера");
  });
});
