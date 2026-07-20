import { describe, expect, test } from "vitest";

describe("Story design", () => {
  test.each([
    "rivals-to-lovers",
    "contract-romance",
    "reunion",
    "friends-to-lovers",
  ])("recognizes the approved trope id %s", async (tropeId) => {
    const { isTropeId } = await import("./story-concept");

    expect(isTropeId(tropeId)).toBe(true);
  });

  test.each([undefined, null, 1, "unknown-trope"])(
    "rejects an unapproved trope id %s",
    async (value) => {
      const { isTropeId } = await import("./story-concept");

      expect(isTropeId(value)).toBe(false);
    },
  );

  test("offers the four approved romance tropes", async () => {
    const { TROPE_TEMPLATES } = await import("./story-concept");

    expect(TROPE_TEMPLATES.map(({ id }) => id)).toEqual([
      "rivals-to-lovers",
      "contract-romance",
      "reunion",
      "friends-to-lovers",
    ]);
  });

  test("creates a normalized story concept from a known trope", async () => {
    const { createStoryConcept } = await import("./story-concept");

    expect(
      createStoryConcept({
        id: "concept-1",
        projectId: "project-1",
        tropeId: "reunion",
        logline: "  헤어진 두 사람이 오래된 온실에서 다시 만난다.  ",
        protagonistNames: ["  서윤 ", " 도현  "],
      }),
    ).toMatchObject({
      logline: "헤어진 두 사람이 오래된 온실에서 다시 만난다.",
      protagonistNames: ["서윤", "도현"],
    });
  });

  test("rejects an unknown trope", async () => {
    const { createStoryConcept } = await import("./story-concept");

    expect(() =>
      createStoryConcept({
        id: "concept-1",
        projectId: "project-1",
        tropeId: "unknown",
        logline: "로그라인",
        protagonistNames: ["서윤", "도현"],
      }),
    ).toThrow("선택한 로맨스 트로프를 찾을 수 없습니다.");
  });

  test("requires two protagonist names", async () => {
    const { createStoryConcept } = await import("./story-concept");

    expect(() =>
      createStoryConcept({
        id: "concept-1",
        projectId: "project-1",
        tropeId: "reunion",
        logline: "로그라인",
        protagonistNames: ["서윤", "  "],
      }),
    ).toThrow("두 주인공의 이름을 모두 입력해 주세요.");
  });
});
