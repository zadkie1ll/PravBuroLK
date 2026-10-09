# Graph Report - frontend  (2026-10-09)

## Corpus Check
- 29 files · ~17,906 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 215 nodes · 372 edges · 12 communities (11 shown, 1 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c3d7b64c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- hrApi.ts
- CourseDetails.tsx
- dependencies
- compilerOptions
- devDependencies
- compilerOptions
- auth.ts
- useStaffGuard
- React + TypeScript + Vite
- tsconfig.json

## God Nodes (most connected - your core abstractions)
1. `req()` - 23 edges
2. `compilerOptions` - 20 edges
3. `compilerOptions` - 18 edges
4. `authHeaders()` - 13 edges
5. `useStaffGuard()` - 12 edges
6. `jsonBody()` - 10 edges
7. `listDepartments()` - 8 edges
8. `Course` - 7 edges
9. `CourseDetails()` - 6 edges
10. `GetInfoAboutMe()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `CourseCardProps` --references--> `Course`  [EXTRACTED]
  src/components/CourseCard.tsx → src/lib/types/components.ts
- `CourseListProps` --references--> `Course`  [EXTRACTED]
  src/components/CourseList.tsx → src/lib/types/components.ts
- `RegistateUser()` --calls--> `setToken()`  [EXTRACTED]
  src/lib/auth.ts → src/lib/token.ts
- `useStaffGuard()` --calls--> `GetInfoAboutMe()`  [EXTRACTED]
  src/lib/useStaffGuard.ts → src/lib/auth.ts
- `req()` --calls--> `authHeaders()`  [EXTRACTED]
  src/lib/hrApi.ts → src/lib/token.ts

## Import Cycles
- None detected.

## Communities (12 total, 1 thin omitted)

### Community 0 - "hrApi.ts"
Cohesion: 0.13
Nodes (36): createCourse(), createMaterial(), createModule(), createOption(), createQuestion(), deleteMaterial(), deleteOption(), deleteQuestion() (+28 more)

### Community 1 - "CourseDetails.tsx"
Cohesion: 0.13
Nodes (21): CourseCardProps, CourseDetails(), LoadTest(), Module, ModuleMaterial, Question, SubmitTest(), Test (+13 more)

### Community 2 - "dependencies"
Cohesion: 0.07
Nodes (26): @emotion/react, @emotion/styled, @mui/icons-material, @mui/material, dependencies, @emotion/react, @emotion/styled, @mui/icons-material (+18 more)

### Community 3 - "compilerOptions"
Cohesion: 0.07
Nodes (26): DOM, DOM.Iterable, ES2022, src, vite/client, compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly (+18 more)

### Community 4 - "devDependencies"
Cohesion: 0.08
Nodes (25): eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, devDependencies, eslint, @eslint/js (+17 more)

### Community 5 - "compilerOptions"
Cohesion: 0.09
Nodes (22): ES2023, node, vite.config.ts, compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module (+14 more)

### Community 6 - "auth.ts"
Cohesion: 0.18
Nodes (10): App(), LoginUser(), RegistateUser(), setToken(), LoginResponse, MeResponse, RegistrationResponse, UserInterface (+2 more)

### Community 7 - "useStaffGuard"
Cohesion: 0.24
Nodes (12): createTrainee(), getTrainee(), HrDepartment, HrTraineeDetail, HrTraineeListItem, listDepartments(), listTrainees(), updateTrainee() (+4 more)

### Community 8 - "React + TypeScript + Vite"
Cohesion: 0.50
Nodes (3): Expanding the ESLint configuration, React Compiler, React + TypeScript + Vite

## Knowledge Gaps
- **84 isolated node(s):** `name`, `private`, `version`, `type`, `dev` (+79 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `devDependencies` connect `devDependencies` to `dependencies`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **Why does `authHeaders()` connect `CourseDetails.tsx` to `hrApi.ts`, `auth.ts`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **What connects `name`, `private`, `version` to the rest of the system?**
  _84 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `hrApi.ts` be split into smaller, more focused modules?**
  _Cohesion score 0.1349527665317139 - nodes in this community are weakly interconnected._
- **Should `CourseDetails.tsx` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._
- **Should `dependencies` be split into smaller, more focused modules?**
  _Cohesion score 0.07407407407407407 - nodes in this community are weakly interconnected._
- **Should `compilerOptions` be split into smaller, more focused modules?**
  _Cohesion score 0.07407407407407407 - nodes in this community are weakly interconnected._