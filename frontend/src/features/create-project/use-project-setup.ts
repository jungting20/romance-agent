import { useState } from "react";

import { useCreateProjectMutation } from "@/features/project-persistence";
import type { TropeId } from "@/modules/story-design";

import {
  createProjectSetupDraft,
  type ProjectSetupDraft,
  type ProjectSetupErrors,
  type ProjectSetupField,
  projectSetupErrors,
  toCreateProjectRequest,
  updateProjectSetupDraft,
} from "./project-setup-state";

export interface UseProjectSetupOptions {
  tropeId: TropeId;
  starterLogline: string;
  onCreated: (projectId: string) => void | Promise<void>;
}

export interface ProjectSetupController {
  draft: ProjectSetupDraft;
  errors: ProjectSetupErrors;
  isPending: boolean;
  updateField: (field: ProjectSetupField, value: string) => void;
  submit: () => Promise<void>;
}

export function useProjectSetup({
  tropeId,
  starterLogline,
  onCreated,
}: UseProjectSetupOptions): ProjectSetupController {
  const createProject = useCreateProjectMutation();
  const [draft, setDraft] = useState(() => createProjectSetupDraft(starterLogline));
  const [submittedDraft, setSubmittedDraft] = useState<ProjectSetupDraft | null>(null);

  return {
    draft,
    errors: projectSetupErrors(createProject.error, draft, submittedDraft),
    isPending: createProject.isPending,
    updateField: (field, value) => {
      setDraft((current) => updateProjectSetupDraft(current, field, value));
    },
    submit: async () => {
      if (createProject.isPending) return;

      const snapshot: ProjectSetupDraft = {
        ...draft,
        protagonistNames: [draft.protagonistNames[0], draft.protagonistNames[1]],
      };
      setSubmittedDraft(snapshot);

      try {
        const workspace = await createProject.mutateAsync(
          toCreateProjectRequest(snapshot, tropeId),
        );
        await onCreated(workspace.project.id);
      } catch {
        // The controller projects mutation errors into field and form feedback.
      }
    },
  };
}
