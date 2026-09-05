import { afterEach, describe, expect, it, vi } from "vitest";

import { CandidateApi } from "./candidate";

describe("CandidateApi questions", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("loads the token-scoped safe LLM question plan", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        agent_session_id: "00000000-0000-0000-0000-000000000010",
        questions: [
          {
            question_id: "00000000-0000-0000-0000-000000000011",
            prompt: "Расскажите о технической задаче.",
            kind: "baseline",
          },
        ],
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const plan = await new CandidateApi().questions("token with spaces");

    expect(fetchMock).toHaveBeenCalledWith(
      "/candidate/token%20with%20spaces/questions",
      undefined,
    );
    expect(plan.questions[0].kind).toBe("baseline");
  });

  it("loads only the published candidate feedback projection", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        status: "published",
        feedback: {
          headline: "Результат интервью",
          strengths: [],
          growth_areas: [],
          experience_alignment: [],
          alternative_vacancy: null,
          next_steps: [],
          limitations: [],
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const delivery = await new CandidateApi().feedback("candidate token");

    expect(fetchMock).toHaveBeenCalledWith(
      "/candidate/candidate%20token/feedback",
      undefined,
    );
    expect(delivery.status).toBe("published");
  });

  it("submits one live-coding solution as a completed response", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        response_id: "response-1",
        question_id: "question-1",
        status: "completed",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await new CandidateApi().submitLiveCoding(
      "candidate token",
      "question-1",
      "def solve():\n    return 42",
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "/candidate/candidate%20token/live-coding-responses",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          question_id: "question-1",
          code: "def solve():\n    return 42",
        }),
      }),
    );
    expect(result.status).toBe("completed");
  });

  it("saves a camera-presence interval against one response", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: "event-1",
        kind: "face_missing",
        started_at_ms: 5_000,
        ended_at_ms: 9_000,
        review_status: "pending",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await new CandidateApi().recordMonitoringEvent("candidate token", {
      client_event_id: "event-1",
      response_id: "response-1",
      question_id: "question-1",
      kind: "face_missing",
      started_at_ms: 5_000,
      ended_at_ms: 9_000,
      detector_name: "mediapipe_face_detector",
      detector_version: "face_presence_v1",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/candidate/candidate%20token/monitoring-events",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
