import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

import type { WorldEditorState } from "../world-entry-editor-state";

export function WorldEditorFeedback({
  state,
  onRetry,
  onRequestReload,
  onRequestClose,
}: {
  state: WorldEditorState;
  onRetry: () => void;
  onRequestReload: () => void;
  onRequestClose: () => void;
}) {
  const errorCount = Object.values(state.errors).reduce(
    (count, errors) => count + Number(Boolean(errors.title)) + Number(Boolean(errors.description)),
    0,
  );
  if (errorCount > 0) {
    return (
      <Alert variant="destructive">
        <AlertTitle>입력하지 않은 항목이 {errorCount}개 있어요.</AlertTitle>
        <AlertDescription>표시된 제목과 설명을 모두 입력해 주세요.</AlertDescription>
      </Alert>
    );
  }
  if (state.phase.status === "conflict") {
    return (
      <Alert variant="destructive">
        <AlertTitle>다른 곳에서 세계관이 변경되었어요.</AlertTitle>
        <AlertDescription>현재 편집 내용은 그대로 보존했어요.</AlertDescription>
        <AlertAction className="static mt-2">
          <Button type="button" variant="outline" onClick={onRequestReload}>
            최신 세계관 불러오기
          </Button>
        </AlertAction>
      </Alert>
    );
  }
  if (state.phase.status === "unavailable") {
    return (
      <Alert variant="destructive">
        <AlertTitle>이 세계관을 더 이상 편집할 수 없어요.</AlertTitle>
        <AlertDescription>현재 편집 내용은 보존되어 있어요.</AlertDescription>
        <AlertAction className="static mt-2">
          <Button type="button" variant="outline" onClick={onRequestClose}>
            세계관 보기로 돌아가기
          </Button>
        </AlertAction>
      </Alert>
    );
  }
  if (state.phase.status === "retryable-error") {
    return (
      <Alert variant="destructive">
        <AlertTitle>세계관을 저장하지 못했어요.</AlertTitle>
        <AlertDescription>편집 내용은 잃지 않았어요. 다시 시도해 주세요.</AlertDescription>
        <AlertAction className="static mt-2">
          <Button type="button" variant="outline" onClick={onRetry}>
            다시 시도
          </Button>
        </AlertAction>
      </Alert>
    );
  }
  return null;
}
