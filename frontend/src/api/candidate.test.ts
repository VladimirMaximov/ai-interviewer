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
});
