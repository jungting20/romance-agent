import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiRequestError } from "@/app/infrastructure/api/api-client";
import type {
  ApiCharacter,
  ApiStoryBible,
  StoryBibleSnapshot,
} from "@/app/infrastructure/api/contracts";
import {
  useCreateCharacterMutation,
  useUpdateCharacterMutation,
} from "@/features/story-bible-persistence";
import {
  emptyCharacterDraft,
  normalizeCharacterDraft,
  type CharacterDraftErrors,
  type CharacterDraftValue,
  validateCharacterDraft,
} from "@/modules/story-bible";

export type CharacterEditorMode = "create" | "edit";
export type CharacterDiscardIntent = "close" | "navigation";

export interface CharacterCardEditorState {
  mode: CharacterEditorMode;
  character?: ApiCharacter;
  draft: CharacterDraftValue;
  errors: CharacterDraftErrors;
  saveError?: ApiRequestError;
  isSaving: boolean;
  isDirty: boolean;
  canSave: boolean;
  unavailable: boolean;
  discardIntent?: CharacterDiscardIntent;
}

export function useCharacterCardEditor({
  projectId,
  bible,
  open,
  mode,
  characterId,
  onSaved,
  onClose,
}: {
  projectId: string;
  bible: ApiStoryBible;
  open: boolean;
  mode: CharacterEditorMode;
  characterId?: string;
  onSaved: (snapshot: StoryBibleSnapshot, characterName: string) => void;
  onClose: () => void;
}) {
  const createMutation = useCreateCharacterMutation();
  const updateMutation = useUpdateCharacterMutation();
  const character =
    mode === "edit" ? bible.characters.find(({ id }) => id === characterId) : undefined;
  const baseline = useMemo<CharacterDraftValue>(
    () => (character ? toDraft(character) : { ...emptyCharacterDraft }),
    [character],
  );
  const editorKey = `${mode}:${characterId ?? "new"}`;
  const [activeKey, setActiveKey] = useState(editorKey);
  const [draft, setDraft] = useState(baseline);
  const [errors, setErrors] = useState<CharacterDraftErrors>({});
  const [saveError, setSaveError] = useState<ApiRequestError>();
  const [isSaving, setIsSaving] = useState(false);
  const [mutationUnavailable, setMutationUnavailable] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const [discardIntent, setDiscardIntent] = useState<CharacterDiscardIntent>();
  const navigationResolution = useRef<((confirmed: boolean) => void) | null>(null);
  const navigationBypass = useRef(false);
  const previousOpen = useRef(open);

  useEffect(() => {
    if (!open || activeKey === editorKey) return;
    setActiveKey(editorKey);
    setDraft(baseline);
    setErrors({});
    setSaveError(undefined);
    setMutationUnavailable(false);
    setDiscardIntent(undefined);
  }, [activeKey, baseline, editorKey, open]);

  useEffect(() => {
    if (open && !previousOpen.current) setAnnouncement("");
    previousOpen.current = open;
  }, [open]);

  const effectiveDraft = activeKey === editorKey ? draft : baseline;
  const normalizedDraft = normalizeCharacterDraft(effectiveDraft);
  const normalizedBaseline = normalizeCharacterDraft(baseline);
  const isDirty = characterFields.some(
    (field) => normalizedDraft[field] !== normalizedBaseline[field],
  );
  const unavailable = (open && mode === "edit" && !character) || mutationUnavailable;
  const canSave = mode === "create" || isDirty;

  const changeField = useCallback((field: keyof CharacterDraftValue, value: string) => {
    setDraft((current) => ({ ...current, [field]: value }));
    if (field === "name") setErrors((current) => ({ ...current, name: undefined }));
  }, []);

  const save = useCallback(async () => {
    if (isSaving || unavailable) return;
    const validation = validateCharacterDraft(effectiveDraft);
    if (!validation.value) {
      setErrors(validation.errors);
      return;
    }
    setErrors({});
    setSaveError(undefined);
    setMutationUnavailable(false);
    setIsSaving(true);
    try {
      const snapshot =
        mode === "create"
          ? await createMutation.mutateAsync({
              projectId,
              request: validation.value,
            })
          : await updateMutation.mutateAsync({
              projectId,
              characterId: character?.id ?? "",
              request: changedFields(normalizedBaseline, validation.value),
            });
      const savedCharacter =
        mode === "create"
          ? snapshot.storyBible.characters.at(-1)
          : snapshot.storyBible.characters.find(({ id }) => id === character?.id);
      setDraft(
        mode === "create"
          ? { ...emptyCharacterDraft }
          : savedCharacter
            ? toDraft(savedCharacter)
            : validation.value,
      );
      navigationBypass.current = true;
      setAnnouncement(`${savedCharacter?.name ?? validation.value.name} 인물을 저장했어요.`);
      onSaved(snapshot, savedCharacter?.name ?? validation.value.name);
    } catch (error) {
      const requestError =
        error instanceof ApiRequestError
          ? error
          : new ApiRequestError(500, {
              code: "INTERNAL_ERROR",
              message: "인물을 저장하지 못했어요.",
              fieldErrors: [],
            });
      setSaveError(requestError);
      if (isUnavailableError(requestError)) setMutationUnavailable(true);
      const nameError = requestError.error.fieldErrors.find(({ path }) => path === "name");
      if (nameError) setErrors({ name: nameError.message });
    } finally {
      setIsSaving(false);
    }
  }, [
    baseline,
    character,
    createMutation,
    effectiveDraft,
    isSaving,
    mode,
    normalizedBaseline,
    onSaved,
    projectId,
    unavailable,
    updateMutation,
  ]);

  const requestClose = useCallback(() => {
    if (isDirty) setDiscardIntent("close");
    else onClose();
  }, [isDirty, onClose]);

  return {
    state: {
      mode,
      character,
      draft: effectiveDraft,
      errors,
      saveError,
      isSaving,
      isDirty,
      canSave,
      unavailable,
      discardIntent,
    } satisfies CharacterCardEditorState,
    changeField,
    save,
    requestClose,
    cancelDiscard: () => {
      navigationResolution.current?.(false);
      navigationResolution.current = null;
      setDiscardIntent(undefined);
    },
    confirmDiscard: () => {
      if (discardIntent === "navigation") {
        navigationResolution.current?.(true);
        navigationResolution.current = null;
        setDiscardIntent(undefined);
      } else if (discardIntent === "close") {
        setDraft(normalizedBaseline);
        setErrors({});
        setSaveError(undefined);
        navigationBypass.current = true;
        setDiscardIntent(undefined);
        onClose();
      }
    },
    confirmNavigationDiscard: () => {
      if (navigationBypass.current) {
        navigationBypass.current = false;
        return Promise.resolve(true);
      }
      if (!isDirty) return Promise.resolve(true);
      setDiscardIntent("navigation");
      return new Promise<boolean>((resolve) => {
        navigationResolution.current = resolve;
      });
    },
    announcement,
    requiresDiscardConfirmation: open && isDirty,
  };
}

const characterFields = Object.keys(emptyCharacterDraft) as Array<keyof CharacterDraftValue>;

function toDraft(character: ApiCharacter): CharacterDraftValue {
  const { id: _id, ...draft } = character;
  return draft;
}

function changedFields(
  baseline: CharacterDraftValue,
  draft: CharacterDraftValue,
): Partial<CharacterDraftValue> {
  return Object.fromEntries(
    characterFields
      .filter((field) => baseline[field] !== draft[field])
      .map((field) => [field, draft[field]]),
  );
}

function isUnavailableError(error: ApiRequestError): boolean {
  return (
    error.status === 404 &&
    (error.error.code === "CHARACTER_NOT_FOUND" || error.error.code === "STORY_BIBLE_NOT_FOUND")
  );
}
