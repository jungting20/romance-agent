import { ApiRequestError } from "@/app/infrastructure/api/api-client";
import type { CreateProjectRequest } from "@/app/infrastructure/api/contracts";
import type { TropeId } from "@/modules/story-design";

export interface ProjectSetupDraft {
  title: string;
  logline: string;
  protagonistNames: [string, string];
}

export type ProjectSetupField =
  | "title"
  | "logline"
  | "firstProtagonist"
  | "secondProtagonist";

export interface ProjectSetupErrors {
  title?: string;
  logline?: string;
  protagonistNames?: string;
  form?: string;
}

const genericCreateProjectError =
  "프로젝트를 만들지 못했어요. 잠시 후 다시 시도해 주세요.";

export function createProjectSetupDraft(starterLogline: string): ProjectSetupDraft {
  return {
    title: "",
    logline: starterLogline,
    protagonistNames: ["서윤", "도현"],
  };
}

export function updateProjectSetupDraft(
  draft: ProjectSetupDraft,
  field: ProjectSetupField,
  value: string,
): ProjectSetupDraft {
  if (field === "title" || field === "logline") {
    return { ...draft, [field]: value };
  }

  return {
    ...draft,
    protagonistNames:
      field === "firstProtagonist"
        ? [value, draft.protagonistNames[1]]
        : [draft.protagonistNames[0], value],
  };
}

export function toCreateProjectRequest(
  draft: ProjectSetupDraft,
  tropeId: TropeId,
): CreateProjectRequest {
  return {
    title: draft.title,
    logline: draft.logline,
    tropeId,
    protagonistNames: draft.protagonistNames,
  };
}

export function projectSetupErrors(
  error: unknown,
  draft: ProjectSetupDraft,
  submittedDraft: ProjectSetupDraft | null,
): ProjectSetupErrors {
  if (!submittedDraft || !error) {
    return {};
  }

  const draftChanged = !sameDraft(draft, submittedDraft);

  if (!(error instanceof ApiRequestError)) {
    return draftChanged ? {} : { form: genericCreateProjectError };
  }

  if (error.status !== 422) {
    return draftChanged ? {} : { form: genericCreateProjectError };
  }

  const fieldErrors = error.error.fieldErrors;
  const title = sameTitle(draft, submittedDraft)
    ? fieldErrors.find(({ path }) => path === "title")?.message
    : undefined;
  const logline = sameLogline(draft, submittedDraft)
    ? fieldErrors.find(({ path }) => path === "logline")?.message
    : undefined;
  const protagonistNames = sameProtagonists(draft, submittedDraft)
    ? fieldErrors.find(({ path }) => path === "protagonistNames")?.message
    : undefined;
  const hasUnmappedField =
    fieldErrors.length === 0 ||
    fieldErrors.some(
      ({ path }) => !["title", "logline", "protagonistNames"].includes(path),
    );

  return compactErrors({
    title,
    logline,
    protagonistNames,
    form: hasUnmappedField && !draftChanged ? error.error.message : undefined,
  });
}

function sameDraft(left: ProjectSetupDraft, right: ProjectSetupDraft): boolean {
  return sameTitle(left, right) && sameLogline(left, right) && sameProtagonists(left, right);
}

function sameTitle(left: ProjectSetupDraft, right: ProjectSetupDraft): boolean {
  return left.title === right.title;
}

function sameLogline(left: ProjectSetupDraft, right: ProjectSetupDraft): boolean {
  return left.logline === right.logline;
}

function sameProtagonists(left: ProjectSetupDraft, right: ProjectSetupDraft): boolean {
  return (
    left.protagonistNames[0] === right.protagonistNames[0] &&
    left.protagonistNames[1] === right.protagonistNames[1]
  );
}

function compactErrors(errors: ProjectSetupErrors): ProjectSetupErrors {
  const compacted: ProjectSetupErrors = {};
  if (errors.title) compacted.title = errors.title;
  if (errors.logline) compacted.logline = errors.logline;
  if (errors.protagonistNames) compacted.protagonistNames = errors.protagonistNames;
  if (errors.form) compacted.form = errors.form;
  return compacted;
}
