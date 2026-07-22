/// <reference types="node" />

import fs from "node:fs";
import path from "node:path";
import * as ts from "typescript/unstable/ast";
import { createVirtualFileSystem } from "typescript/unstable/fs";
import { API } from "typescript/unstable/sync";
import { describe, expect, test } from "vitest";

type ViolationKind = "infrastructure-import" | "state-hook" | "type-assertion";

interface PageBoundaryViolation {
  kind: ViolationKind;
  detail: string;
}

const restrictedHooks = new Set(["useState", "useReducer", "useRef"]);

export function analyzePageSource(sourceText: string, fileName: string): PageBoundaryViolation[] {
  const virtualFileName = path.posix.join(
    "/virtual",
    fileName.replaceAll("\\", "/").replace(/^\/+/, ""),
  );
  const api = new API({
    cwd: "/virtual",
    fs: createVirtualFileSystem({ [virtualFileName]: sourceText }),
  });
  try {
    const snapshot = api.updateSnapshot({ openFiles: [virtualFileName] });
    try {
      const sourceFile = snapshot
        .getDefaultProjectForFile(virtualFileName)
        ?.program.getSourceFile(virtualFileName);

      if (!sourceFile) {
        throw new Error(`TypeScript could not parse ${fileName}`);
      }
      const parsedSourceFile = sourceFile;

      const localHookNames = new Map<string, string>();
      const violations: PageBoundaryViolation[] = [];

      for (const statement of parsedSourceFile.statements) {
        if (!ts.isImportDeclaration(statement) || !ts.isStringLiteral(statement.moduleSpecifier)) {
          continue;
        }

        const moduleName = statement.moduleSpecifier.text;
        if (moduleName.startsWith("@/app/infrastructure/")) {
          violations.push({
            kind: "infrastructure-import",
            detail: moduleName,
          });
        }

        if (moduleName !== "react") continue;
        const bindings = statement.importClause?.namedBindings;
        if (!bindings || !ts.isNamedImports(bindings)) continue;

        for (const element of bindings.elements) {
          const importedName = element.propertyName?.text ?? element.name.text;
          if (restrictedHooks.has(importedName)) {
            localHookNames.set(element.name.text, importedName);
          }
        }
      }

      function visit(node: ts.Node) {
        if (ts.isCallExpression(node) && ts.isIdentifier(node.expression)) {
          const hook = localHookNames.get(node.expression.text);
          if (hook) violations.push({ kind: "state-hook", detail: hook });
        }

        if (ts.isTypeAssertion(node)) {
          violations.push({ kind: "type-assertion", detail: "non-const" });
        }

        if (ts.isAsExpression(node)) {
          const isConstAssertion =
            ts.isTypeReferenceNode(node.type) &&
            ts.isIdentifier(node.type.typeName) &&
            node.type.typeName.text === "const";
          if (!isConstAssertion) {
            violations.push({ kind: "type-assertion", detail: "non-const" });
          }
        }

        node.forEachChild(visit);
      }

      visit(parsedSourceFile);
      return violations;
    } finally {
      snapshot.dispose();
    }
  } finally {
    api.close();
  }
}

// Remove this baseline when the full writing-workspace page has been extracted
// into the appropriate feature and presentation owners.
const legacyBaseline: Record<string, Record<string, number>> = {
  "writing-workspace/writing-workspace-page.tsx": {
    "infrastructure-import:@/app/infrastructure/api/api-client": 1,
    "infrastructure-import:@/app/infrastructure/api/contracts": 1,
    "state-hook:useRef": 4,
    "state-hook:useState": 3,
    "type-assertion:non-const": 1,
  },
};

function summarize(violations: PageBoundaryViolation[]): Record<string, number> {
  return violations.reduce<Record<string, number>>((counts, violation) => {
    const key = `${violation.kind}:${violation.detail}`;
    counts[key] = (counts[key] ?? 0) + 1;
    return counts;
  }, {});
}

function productionPageFiles(directory: string): string[] {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return productionPageFiles(entryPath);
    if (
      !entry.isFile() ||
      !/\.(ts|tsx)$/.test(entry.name) ||
      /\.test\.(ts|tsx)$/.test(entry.name)
    ) {
      return [];
    }
    return [entryPath];
  });
}

describe("page boundary analyzer", () => {
  test("detects restricted imports, aliased state hooks, and unsafe assertions", () => {
    const violations = analyzePageSource(
      `
        import { useState as useLocalState } from "react";
        import type { ApiError } from "@/app/infrastructure/api/contracts";
        const value = "reunion" as ApiError;
        useLocalState(value);
      `,
      "fixture.tsx",
    );

    expect(summarize(violations)).toEqual({
      "infrastructure-import:@/app/infrastructure/api/contracts": 1,
      "state-hook:useState": 1,
      "type-assertion:non-const": 1,
    });
  });

  test("allows const assertions", () => {
    expect(analyzePageSource(`const values = ["one"] as const;`, "fixture.ts")).toEqual([]);
  });

  test("allows const assertions with comments before the const type", () => {
    expect(
      analyzePageSource(`const values = ["one"] as /* explanation */ const;`, "fixture.ts"),
    ).toEqual([]);
  });
});

test("production pages match the zero-violation or frozen legacy baseline", () => {
  const pagesRoot = path.resolve(import.meta.dirname, "../pages");
  const files = productionPageFiles(pagesRoot);
  const observedLegacyFiles = new Set<string>();

  for (const file of files) {
    const relativePath = path.relative(pagesRoot, file).split(path.sep).join("/");
    const expected = legacyBaseline[relativePath] ?? {};
    if (legacyBaseline[relativePath]) observedLegacyFiles.add(relativePath);

    expect(summarize(analyzePageSource(fs.readFileSync(file, "utf8"), file)), relativePath).toEqual(
      expected,
    );
  }

  expect([...observedLegacyFiles].sort()).toEqual(Object.keys(legacyBaseline).sort());
});
