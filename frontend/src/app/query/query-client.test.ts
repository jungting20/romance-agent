import { describe, expect, test } from "vitest";

import { ApiRequestError } from "@/app/infrastructure/api/api-client";

import { createAppQueryClient } from "./query-client";

describe("createAppQueryClient", () => {
  test("does not retry typed 4xx API request errors", async () => {
    expect(
      await countQueryAttempts(
        new ApiRequestError(404, {
          code: "PROJECT_NOT_FOUND",
          message: "프로젝트를 찾을 수 없습니다.",
          fieldErrors: [],
        }),
      ),
    ).toBe(1);
  });

  test("retries a typed 5xx API request error once", async () => {
    expect(
      await countQueryAttempts(
        new ApiRequestError(500, {
          code: "INTERNAL_ERROR",
          message: "서버 오류",
          fieldErrors: [],
        }),
      ),
    ).toBe(2);
  });

  test("retries a network error once", async () => {
    expect(await countQueryAttempts(new TypeError("Failed to fetch"))).toBe(2);
  });
});

async function countQueryAttempts(error: Error): Promise<number> {
  const queryClient = createAppQueryClient();
  let attempts = 0;

  await queryClient
    .fetchQuery({
      queryKey: ["retry-policy", error.name, error.message],
      queryFn: () => {
        attempts += 1;
        return Promise.reject(error);
      },
      retryDelay: 0,
    })
    .catch(() => undefined);
  queryClient.clear();

  return attempts;
}
