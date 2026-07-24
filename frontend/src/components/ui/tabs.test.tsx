import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "./tabs";

test("preserves horizontal orientation and arrow-key behavior by default", async () => {
  const user = userEvent.setup();

  render(
    <Tabs defaultValue="first">
      <TabsList aria-label="horizontal tabs">
        <TabsTrigger value="first">First</TabsTrigger>
        <TabsTrigger value="second">Second</TabsTrigger>
      </TabsList>
      <TabsContent value="first">First content</TabsContent>
      <TabsContent value="second">Second content</TabsContent>
    </Tabs>,
  );

  const tablist = screen.getByRole("tablist", { name: "horizontal tabs" });
  const firstTab = screen.getByRole("tab", { name: "First" });
  const secondTab = screen.getByRole("tab", { name: "Second" });

  expect(tablist).toHaveAttribute("aria-orientation", "horizontal");
  firstTab.focus();
  await user.keyboard("{ArrowRight}");

  expect(secondTab).toHaveFocus();
  expect(secondTab).toHaveAttribute("aria-selected", "true");
  expect(screen.getByText("Second content")).toBeInTheDocument();
});
