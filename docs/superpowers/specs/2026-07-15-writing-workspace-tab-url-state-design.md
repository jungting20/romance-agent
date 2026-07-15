# Writing Workspace Tab URL State Design

## Context

The writing workspace at `/projects/$projectId/write` renders three contextual
tabs: manuscript, characters, and world. The selected tab currently lives in
component-local `contextMode` state, so a direct link, reload, and browser
Back/Forward navigation cannot restore the same visible context.

The frontend's routing rules require user-visible selected subviews to derive
from validated URL search parameters. TanStack Router already provides the
file-based route and typed search APIs needed for this screen.

## Goal

Make the active contextual tab URL-owned while preserving the existing writing
workspace layout, mobile sheet behavior, manuscript autosave, and navigation
protection.

## URL Contract

The writing workspace accepts one optional search parameter:

```text
tab = manuscript | characters | world
```

Canonical URLs are:

| Visible context | Canonical URL |
| --- | --- |
| Manuscript | `/projects/silver-garden/write` |
| Characters | `/projects/silver-garden/write?tab=characters` |
| World | `/projects/silver-garden/write?tab=world` |

`manuscript` is the validated default but is omitted from the canonical URL.
The route accepts an explicit `?tab=manuscript` for compatibility, renders the
manuscript tab, and canonicalizes it to the URL without `tab` using replacement
navigation. Unknown or non-string `tab` values also replacement-navigate to the
canonical manuscript URL.

## Interaction Design

The selected tab is derived from the validated route search state; it is not
duplicated in component-local state.

When a user chooses a tab:

- choosing `characters` or `world` adds `tab` to the search state;
- choosing `manuscript` removes `tab` from the search state; and
- each user-initiated choice creates a browser history entry so Back and
  Forward replay tab selection.

On mobile, choosing a contextual tab still opens the left sheet. Closing that
sheet changes only its transient visibility state; the selected tab and URL
remain unchanged. Desktop and mobile layouts render the same selected context
from the URL.

## Architecture

The writing-workspace route owns search validation and canonical URL recovery.
The page reads the validated search value through TanStack Router and derives
the tab mode during rendering. A concise page callback performs typed search
navigation for tab clicks while preserving any future unrelated search state.

The existing `contextOpen`, AI-tool visibility, manuscript selection,
autosave, and conflict state stay local because they are transient interface
mechanics or workflow state, not selected contextual subviews.

No new API request, persistence model, domain operation, or dependency is
needed. Tab selection does not change Manuscript or Story Bible ownership.

## Error Handling

Malformed or unsupported `tab` values never cause an invalid panel to render.
They resolve to manuscript and replacement-navigate to the canonical URL. This
prevents repeated invalid history entries while preserving a predictable direct
link behavior.

## Testing

Add focused writing-workspace tests that verify:

- direct initial URLs with `tab=characters` and `tab=world` render the
  corresponding tab;
- the canonical URL without `tab` renders manuscript;
- clicking tabs updates both selected content and the expected search state;
- selecting manuscript removes `tab`;
- browser Back and Forward restore selected contexts; and
- an invalid or explicit manuscript search value is replacement-canonicalized
  to the clean manuscript URL.

Retain existing mobile-sheet coverage and extend it to confirm that a URL-owned
selection stays selected when the sheet closes.

## Scope

- Update only the writing-workspace route, page, and focused component tests.
- Add the required UI plan and implementation record for the UI behavior
  change.
- Preserve current routes, tab labels, keyboard behavior, responsive layout,
  API behavior, and domain contracts.
- Do not URL-own the AI-tool sheet, manuscript selection, autosave state, or
  conflict dialog in this change.

## Domain, API, and UI Impact

This changes frontend navigation state only. It does not change domain terms,
invariants, responsibilities, API operations, or persistence. The visible
layout and content remain the same; only tab selection becomes linkable,
reloadable, and history-aware.
