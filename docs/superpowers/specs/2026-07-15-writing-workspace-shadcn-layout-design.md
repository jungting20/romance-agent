# Writing Workspace shadcn Layout Design

## Goal

Improve the existing writing workspace with shadcn primitives so that its
context navigation, auxiliary panels, loading states, and error states are more
accessible and useful across mobile and desktop sizes without changing writing
domain behavior.

## Scope

The change applies to the existing writing workspace page and its focused UI
tests. It introduces or adopts these shadcn primitives:

- `Sheet` for modal auxiliary panels on smaller viewports.
- `Tabs` for the manuscript, character, and world context switcher.
- `Resizable` for adjustable desktop context, editor, and assistant regions.
- `Skeleton` for a workspace-shaped loading state.
- `Alert` for not-found, loading-error, and missing-scene states.

The existing workspace route, project loading query, manuscript editing,
autosave, navigation guard, conflict resolution, and writing-suggestion flows
remain unchanged.

## Implementation Brief

### User value and UI target

The existing `WritingWorkspacePage` is the only UI target. Mobile users must be
able to open the context content that is currently hidden, and auxiliary
panels must provide standard focus, Escape, overlay, and close behavior.
Desktop users must be able to adjust the width of the context, editor, and AI
assistant regions while retaining the current writing-focused layout.

### Persistence, API, and domain behavior

No persistence mechanism or consumer-facing API operation changes. The page
continues to consume the existing project workspace and manuscript save
operations exactly as it does today. No domain model, invariant, use case,
responsibility, or cross-domain dependency changes, so no domain-document or
OpenAPI edit is required.

### Ownership

- Page composition and responsive panel state remain in
  `src/pages/writing-workspace/`.
- Generic shadcn primitives remain in `src/components/ui/`.
- Manuscript, Story Bible, Writing Assistant, autosave, and conflict features
  retain their current ownership and public interfaces.

## Component Design

### Loading and terminal states

The pending state renders a semantic live status containing a visual skeleton
that resembles the workspace header, navigation rail, context panel, and
editor. The loading copy remains available to assistive technology.

Not-found, transient-error, and missing-active-scene states use the shared
`Alert` structure while preserving their current roles, Korean copy, and
available actions. The transient error retains its retry behavior; not-found
retains the library link.

### Context navigation and mobile context panel

The manuscript, character, and world modes are a single controlled vertical
`Tabs` interface. The icon rail uses `TabsList` and `TabsTrigger`, keeps the
existing accessible names and tooltips, and exposes the selected state through
tab semantics.

On medium and larger viewports, the selected `TabsContent` appears in the left
context panel. On smaller viewports, selecting a context tab opens a left-side
`Sheet` containing the same selected content. The same page state owns both
representations, and only the representation for the active responsive range
is exposed to assistive technology.

### AI assistant panel

On viewports below the desktop split-layout breakpoint, the AI assistant opens
in a controlled right-side `Sheet`. The sheet has a Korean accessible title,
overlay, Escape handling, focus management, and close behavior. On the desktop
split layout, it remains an inline right panel so the editor stays directly
usable while the assistant is open.

The assistant continues to receive the current scene content, selected text,
character names, apply callback, and close callback. Applying a suggestion
continues to update the manuscript only through the existing application use
case.

### Resizable desktop layout

At the desktop split-layout breakpoint, the context panel, manuscript editor,
and open assistant panel are placed in a horizontal `ResizablePanelGroup`.
Visible adjacent panels are separated by keyboard-accessible
`ResizableHandle` elements. Reasonable minimum and default sizes prevent the
editor or tools from becoming unusable. When the assistant is closed, the
editor consumes its available space without leaving an empty panel or handle.

Smaller viewports do not use resize handles; sheets overlay the editor instead.

### Scrolling

Existing native overflow behavior may remain where it already provides the
correct document scrolling. `ScrollArea` is used only for bounded auxiliary
panel content where it improves consistent panel scrolling without creating
nested editor scrolling.

## Accessibility and Interaction Requirements

- Context controls are keyboard navigable and expose tab selection semantics.
- Every icon-only control retains a Korean accessible name and visible focus
  indication.
- Mobile sheets have accessible Korean titles; close controls do not expose
  English-only labels.
- Escape closes the active auxiliary sheet without changing manuscript data.
- Loading and failure announcements retain appropriate `status` or `alert`
  semantics.
- Resize handles are keyboard operable through the underlying resizable
  primitive.
- Existing autosave and conflict announcements remain intact.

## Acceptance Criteria

1. Loading displays a workspace-shaped skeleton and the loading status remains
   discoverable by role.
2. Workspace loading errors and missing data render via `Alert`, preserving
   their copy, roles, links, and retry behavior.
3. Context controls expose tabs for manuscript, characters, and world, and
   selecting one displays the matching content.
4. A small-viewport user can open and close the selected context content in a
   left sheet.
5. A small or medium viewport opens the AI tool in a right sheet that closes by
   its control and Escape.
6. A desktop viewport presents context, editor, and the optional AI tool as
   resizable inline panels with no orphaned handles.
7. AI suggestions, manuscript editing, autosave, navigation protection, and
   conflict resolution preserve their existing observable behavior.
8. No domain contract or API contract changes are introduced.

## Testing and Verification

Focused Testing Library tests cover loading semantics, alert retry, tab
selection, sheet open/close behavior, and preserved writing-assistant flows.
Viewport-dependent behavior is tested through the project's established media
query strategy or an injected responsive boundary rather than CSS visibility
assertions alone.

After focused tests, run from `frontend/`:

```sh
mise exec -- pnpm check
mise exec -- pnpm build
```

The required Playwright planner and generator agents are invoked after the
implementation if their project-scoped definitions are available. If they are
unavailable, that repository-required E2E handoff is reported explicitly.

## Non-goals

- Replacing the workspace with the full shadcn `Sidebar` system.
- Changing project, manuscript, Story Bible, or Writing Assistant domain
  behavior.
- Changing API shapes, mock payloads, or backend behavior.
- Redesigning manuscript editor or writing-assistant product functionality.
- Persisting panel sizes or open states across sessions.
