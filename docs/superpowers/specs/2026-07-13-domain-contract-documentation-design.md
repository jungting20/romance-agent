# Domain Contract Documentation Design

## Goal

Create a technology-neutral domain documentation layer that gives frontend and future Python backend contributors a shared understanding of the system's language, responsibilities, rules, and boundaries.

## Documentation Structure

```text
docs/
├── domains/
│   ├── README.md
│   ├── projects.md
│   ├── story-design.md
│   ├── story-bible.md
│   ├── manuscript.md
│   └── writing-assistant.md
└── superpowers/
```

`docs/domains/README.md` is the entry point and context map. Each bounded context has one focused document. The current system is small enough that splitting a domain into several documents would add navigation overhead without improving clarity.

## Shared Contract Template

Each domain document uses the same sections:

1. **Purpose and responsibility** — the business capability owned by the domain.
2. **Ubiquitous language** — terms that must have the same meaning in product discussion and code.
3. **Core model** — entities, value objects, identifiers, and important states.
4. **Invariants** — rules that must remain true regardless of implementation technology.
5. **Use cases** — behaviors the domain exposes to application workflows.
6. **Inputs and outputs** — information exchanged with other domains.
7. **Out of scope** — responsibilities deliberately owned elsewhere.

The documents describe contracts, not source-file layouts, React components, persistence adapters, API routes, or framework choices. Those details change faster and belong in implementation documentation or code.

## Bounded Contexts

### Projects

Owns the identity, title, summary, selected romance trope reference, and recent-activity metadata of a writing project. It does not own story content.

### Story Design

Owns the initial story concept, romance trope selection, logline, and initial protagonist names. It validates the minimum concept needed to create a project workspace.

### Story Bible

Owns canonical character and world knowledge used while writing. It selects only the context relevant to a manuscript scene.

### Manuscript

Owns scenes, scene ordering metadata, active-scene state, prose content, text insertion, and range replacement rules. It is the only domain that owns manuscript text.

### Writing Assistant

Owns explicit writing-assistance requests and generated suggestions. It never reads or changes a manuscript without an application workflow supplying context and explicitly applying a suggestion.

## Context Map

```text
Projects
   └─ Story Design
        ├─ Story Bible
        └─ Manuscript ── Writing Assistant
```

Application workflows coordinate the boundaries:

- **Create project workspace:** combines validated Story Design input with Projects, Story Bible, and Manuscript creation.
- **Apply writing suggestion:** takes a Writing Assistant suggestion and asks Manuscript to insert or replace text.

Direct cross-domain mutation is prohibited. A source domain returns data or a decision; an application workflow passes the required information to the owning target domain.

## Documentation Quality Rules

- Use the exact domain names already present in the codebase.
- Define every specialized term on first use.
- State invariants as testable rules using “must” or “must not.”
- Avoid duplicating TypeScript interfaces line for line.
- Avoid future backend framework or API design decisions.
- Keep unresolved product expansion outside these contracts until it is approved and implemented.

## Verification

- Every current bounded context has one contract document.
- The index links to every contract and describes the dependency direction.
- Names and invariants agree with the current domain implementation and tests.
- No contract depends on React, localStorage, Vite, Python framework, database, or transport details.
