import { describe, expect, test } from "vitest";

import { ApiRequestError } from "@/app/infrastructure/api/api-client";

import {
  createProjectSetupDraft,
  projectSetupErrors,
  toCreateProjectRequest,
  updateProjectSetupDraft,
} from "./project-setup-state";

describe("project setup state", () => {
  test("creates the approved initial draft", () => {
    expect(createProjectSetupDraft("트로프 시작 문장")).toEqual({
      title: "",
      logline: "트로프 시작 문장",
      protagonistNames: ["서윤", "도현"],
    });
  });

  test("updates one protagonist without mutating the previous draft", () => {
    const previous = createProjectSetupDraft("로그라인");
    const next = updateProjectSetupDraft(previous, "firstProtagonist", "하린");

    expect(next.protagonistNames).toEqual(["하린", "도현"]);
    expect(previous.protagonistNames).toEqual(["서윤", "도현"]);
  });

  test("keeps an unchanged field error after another field changes", () => {
    const submitted = {
      title: "겹치는 제목",
      logline: "로그라인",
      protagonistNames: ["서윤", "도현"] as [string, string],
    };
    const current = updateProjectSetupDraft(submitted, "title", "새 제목");
    const error = new ApiRequestError(422, {
      code: "INVALID_PROTAGONISTS",
      message: "입력 내용을 확인해 주세요.",
      fieldErrors: [
        { path: "title", message: "이미 사용 중인 제목이에요." },
        { path: "protagonistNames", message: "두 이름을 확인해 주세요." },
      ],
    });

    expect(projectSetupErrors(error, current, submitted)).toEqual({
      protagonistNames: "두 이름을 확인해 주세요.",
    });
  });

  test("hides a form-level failure after any draft edit", () => {
    const submitted = createProjectSetupDraft("로그라인");
    const current = updateProjectSetupDraft(submitted, "title", "새 제목");
    const error = new ApiRequestError(500, {
      code: "INTERNAL_ERROR",
      message: "서버 실패",
      fieldErrors: [],
    });

    expect(projectSetupErrors(error, current, submitted)).toEqual({});
  });

  test("shows generic feedback for a non-contract failure", () => {
    const submitted = createProjectSetupDraft("로그라인");

    expect(projectSetupErrors(new Error("network failed"), submitted, submitted)).toEqual({
      form: "프로젝트를 만들지 못했어요. 잠시 후 다시 시도해 주세요.",
    });
  });

  test("serializes the typed transport request without a cast", () => {
    expect(
      toCreateProjectRequest(
        {
          title: "제목",
          logline: "",
          protagonistNames: ["서윤", "도현"],
        },
        "reunion",
      ),
    ).toEqual({
      title: "제목",
      logline: "",
      tropeId: "reunion",
      protagonistNames: ["서윤", "도현"],
    });
  });
});
