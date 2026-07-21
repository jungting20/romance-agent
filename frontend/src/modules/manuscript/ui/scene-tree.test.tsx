import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { addScene, createInitialManuscript } from "@/modules/manuscript";

import { SceneTree } from "./scene-tree";

test("adds, selects, and marks the active scene", async () => {
  const manuscript = addScene(createInitialManuscript("project-1"), "scene-2");
  const onAdd = vi.fn();
  const onSelect = vi.fn();
  const user = userEvent.setup();
  render(
    <SceneTree manuscript={manuscript} onAdd={onAdd} onSelect={onSelect} addDisabled={false} />,
  );

  await user.click(screen.getByRole("button", { name: "새 장면 추가" }));
  await user.click(screen.getByRole("button", { name: "1장 비가 그친 뒤의 정원" }));

  expect(onAdd).toHaveBeenCalledOnce();
  expect(onSelect).toHaveBeenCalledWith("project-1-scene-1");
  expect(screen.getByRole("button", { name: "2장 제목 없는 장면" })).toHaveAttribute(
    "aria-current",
    "true",
  );
});

test("disables only scene addition during conflict resolution", () => {
  render(
    <SceneTree
      manuscript={createInitialManuscript("p")}
      onAdd={vi.fn()}
      onSelect={vi.fn()}
      addDisabled
    />,
  );

  expect(screen.getByRole("button", { name: "새 장면 추가" })).toBeDisabled();
  expect(screen.getByRole("button", { name: /1장/ })).toBeEnabled();
});
