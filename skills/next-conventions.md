---
name: next-conventions
description: "Next.js conventions: TypeScript, components, routing, data fetching, error handling, styling, testing, linting, project structure, code review"
globs: ["**/*.ts", "**/*.tsx", "**/*.jsx"]
---

**These are MANDATORY conventions. ALL Next.js / TypeScript code MUST follow these rules without exception.**

---

# 1. Code Style / TypeScript

## Strict Mode

- MUST enable `strict: true` in `tsconfig.json`
- MUST NEVER use `any` — use `unknown` and narrow, or define a proper type
- MUST NEVER use `@ts-ignore` or `@ts-expect-error` without a comment explaining why

## Return Types

- MUST add explicit return types to all exported functions and helpers
- Page/layout components and Server Actions may rely on inference

## Interface vs Type

- MUST use `interface` for object shapes that may be extended
- MUST use `type` for unions, intersections, and mapped types
- MUST name component prop interfaces as `{ComponentName}Props`

```typescript
interface UserCardProps {
  name: string;
  email: string;
  role?: "admin" | "member";
}

type ApiResponse<T> = { data: T; error: null } | { data: null; error: string };
```

## Exports

- MUST use named exports for all components and utilities
- Default exports are ONLY allowed for Next.js file conventions (`page.tsx`, `layout.tsx`, `loading.tsx`, `error.tsx`, `not-found.tsx`, `route.ts`)
- NEVER use default exports outside of Next.js file conventions

## Import Ordering

- MUST follow this order, separated by blank lines:
    1. React / Next.js (`react`, `next/*`)
    2. Third-party packages (`zod`, `clsx`, etc.)
    3. Project aliases (`@/components/*`, `@/lib/*`, etc.)
    4. Relative imports (`./`, `../`)

```typescript
import { Suspense } from "react";
import Link from "next/link";

import { z } from "zod";

import { Button } from "@/components/ui/button";
import { fetchUser } from "@/lib/actions/user";

import { UserAvatar } from "./user-avatar";
```

## Path Aliases

- MUST configure and use `@/` path alias for all non-relative imports
- NEVER use deep relative paths like `../../../lib/utils`

## Constants

- MUST use `UPPER_SNAKE_CASE` for all constants
- MUST define constants in a dedicated file or at the top of the module, after imports
- NEVER use magic numbers or magic strings — extract them into named constants

```typescript
const MAX_ITEMS_PER_PAGE = 20;
const DEFAULT_REVALIDATION_SECONDS = 60;

// NEVER do this:
if (items.length > 20) { ... }

// MUST do this:
if (items.length > MAX_ITEMS_PER_PAGE) { ... }
```

---

# 2. Component Patterns

## Server Components by Default

- MUST use Server Components by default — they render on the server with zero client JS
- MUST ONLY add `"use client"` when the component needs browser APIs, event handlers, hooks (`useState`, `useEffect`, etc.), or context providers
- NEVER add `"use client"` "just in case" or to an entire page

## Composition Pattern

- MUST use the composition pattern: Server Components fetch data and pass it to Client Components as props
- NEVER fetch data inside Client Components when it can be fetched on the server

```typescript
// app/dashboard/page.tsx (Server Component — fetches data)
import { DashboardChart } from "@/components/dashboard-chart";
import { fetchMetrics } from "@/lib/actions/metrics";

export default async function DashboardPage() {
  const metrics = await fetchMetrics();
  return <DashboardChart data={metrics} />;
}

// components/dashboard-chart.tsx (Client Component — handles interactivity)
"use client";

import { useState } from "react";

interface DashboardChartProps {
  data: MetricsData;
}

export function DashboardChart({ data }: DashboardChartProps) {
  const [range, setRange] = useState<"week" | "month">("week");
  // interactive chart rendering
}
```

## Props

- MUST define a `{ComponentName}Props` interface for every component that accepts props
- MUST NEVER use `any` for prop types
- MUST destructure props in the function signature

## Component Naming

- MUST use PascalCase for component names and their files
- MUST colocate component-specific types in the same file

---

# 3. Routing & App Router

## File Conventions

- MUST use the App Router file conventions:
  - `page.tsx` — Route UI
  - `layout.tsx` — Shared layout (wraps children)
  - `loading.tsx` — Loading UI (Suspense fallback)
  - `error.tsx` — Error boundary (MUST be a Client Component)
  - `not-found.tsx` — 404 UI
  - `route.ts` — API Route Handler (NEVER colocate with `page.tsx`)

## Route Groups

- MUST use route groups `(groupName)` for organizing routes without affecting the URL
- Example: `app/(auth)/login/page.tsx`, `app/(dashboard)/overview/page.tsx`

## Dynamic Routes

- MUST use `[param]` for dynamic segments, `[...param]` for catch-all, `[[...param]]` for optional catch-all
- MUST validate dynamic params with Zod before use

## Metadata

- MUST use `generateMetadata` or static `metadata` export for SEO on every page
- NEVER hardcode titles — use templates in the root layout

```typescript
// app/layout.tsx
export const metadata: Metadata = {
  title: {
    template: "%s | My App",
    default: "My App",
  },
};

// app/about/page.tsx
export const metadata: Metadata = {
  title: "About", // Renders as "About | My App"
};
```

## Route Handlers

- MUST use Route Handlers (`route.ts`) for API endpoints — NEVER use the legacy `pages/api/` directory
- MUST use proper HTTP method exports (`GET`, `POST`, `PUT`, `DELETE`)
- MUST validate request bodies with Zod

---

# 4. Data Fetching

## Server-Side Fetching

- MUST fetch data in async Server Components or Server Actions — NEVER use client-side `fetch` or `useEffect` for data that is available on the server
- MUST use `fetch` with appropriate caching options or direct database/ORM calls in Server Components

```typescript
// Server Component — direct async fetch
export default async function UsersPage() {
  const users = await db.user.findMany();
  return <UserList users={users} />;
}
```

## Server Actions

- MUST use Server Actions (`"use server"`) for all data mutations
- MUST validate ALL inputs with Zod before processing
- MUST return typed results, NEVER throw from Server Actions (return error objects instead)
- MUST place shared Server Actions in `lib/actions/`

```typescript
"use server";

import { z } from "zod";

const CreateUserSchema = z.object({
  name: z.string().min(1),
  email: z.string().email(),
});

type ActionResult = { success: true; id: string } | { success: false; error: string };

export async function createUser(formData: FormData): Promise<ActionResult> {
  const parsed = CreateUserSchema.safeParse({
    name: formData.get("name"),
    email: formData.get("email"),
  });

  if (!parsed.success) {
    return { success: false, error: parsed.error.issues[0].message };
  }

  try {
    const user = await db.user.create({ data: parsed.data });
    return { success: true, id: user.id };
  } catch (e) {
    return { success: false, error: "Failed to create user" };
  }
}
```

## Caching & Revalidation

- MUST use `revalidatePath` or `revalidateTag` after mutations
- MUST set appropriate `revalidate` intervals for cached data
- NEVER rely on stale data after a mutation — always revalidate

## Suspense Boundaries

- MUST wrap async data-fetching components in `<Suspense>` with meaningful fallbacks
- MUST use `loading.tsx` for route-level loading states

---

# 5. Error Handling

## Error Boundaries

- MUST create `error.tsx` in route segments that can fail (MUST be a Client Component)
- MUST create `app/global-error.tsx` as a top-level catch-all
- MUST provide a user-friendly message and a retry mechanism

```typescript
"use client";

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function Error({ error, reset }: ErrorProps) {
  return (
    <div>
      <h2>Something went wrong</h2>
      <button onClick={reset}>Try again</button>
    </div>
  );
}
```

## Server Action Error Returns

- MUST return typed error objects from Server Actions — NEVER throw unhandled exceptions
- MUST use discriminated unions for action results

```typescript
type ActionResult<T = void> =
  | { success: true; data: T }
  | { success: false; error: string };
```

## Route Handlers

- MUST use try/catch in all Route Handlers
- MUST return appropriate HTTP status codes with `NextResponse.json()`
- MUST NEVER expose internal error details to the client

## 404 Handling

- MUST use `notFound()` from `next/navigation` for missing resources — NEVER return empty UI

---

# 6. Styling (Tailwind CSS)

## Utility-First

- MUST use Tailwind utility classes for all styling
- NEVER write custom CSS unless Tailwind cannot express it (e.g., complex animations)
- NEVER use inline `style` attributes for things Tailwind can handle

## cn() Helper

- MUST use a `cn()` helper combining `clsx` and `tailwind-merge` for conditional/merged classes
- MUST place the helper in `lib/utils.ts`

```typescript
// lib/utils.ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

## Design Tokens

- MUST define colors, spacing, and fonts in `tailwind.config.ts` using design tokens
- NEVER hardcode hex colors or pixel values in class names — use the theme

## Responsive Design

- MUST use Tailwind responsive prefixes (`sm:`, `md:`, `lg:`, `xl:`, `2xl:`) — mobile-first approach
- NEVER use CSS media queries when Tailwind prefixes suffice

## Component Extraction

- MUST extract repeated class strings into reusable components rather than duplicating long class lists
- A set of utility classes appearing 3+ times MUST be extracted into a component

---

# 7. Testing

## Unit & Component Tests

- MUST use Vitest + React Testing Library for component and unit tests
- MUST test behavior, not implementation details — assert what the user sees, NOT internal state
- NEVER test implementation details (internal state, private methods, component internals)

## End-to-End Tests

- MUST use Playwright for e2e tests covering critical user flows
- MUST test against realistic data and scenarios

## Test File Location

- MUST colocate test files next to the code they test: `component.tsx` → `component.test.tsx`
- MUST use the `.test.ts` / `.test.tsx` suffix

## Test Coverage

- MUST include tests for:
  - Normal operation (happy path)
  - Edge cases (empty states, boundary values, null/undefined)
  - Error conditions (invalid inputs, failed fetches)
- MUST test Server Actions with mocked dependencies
- ALL new functionality MUST have passing tests before code review

---

# 8. Linting & Formatting

## Tools

- MUST use ESLint with `eslint-config-next` for Next.js-specific rules
- MUST use Prettier for code formatting
- MUST run `next lint` before committing

## Configuration

- MUST extend `next/core-web-vitals` in ESLint config
- MUST configure Prettier in `.prettierrc` or `package.json`

```json
// .eslintrc.json
{
  "extends": ["next/core-web-vitals", "next/typescript"]
}
```

## Rules

- MUST resolve ALL ESLint warnings and errors before committing
- NEVER disable ESLint rules inline without a comment explaining why
- MUST use `eslint-plugin-import` for import ordering enforcement

---

# 9. Project Structure

When creating a new Next.js project, MUST use this structure. When working in an existing project, MUST follow its existing structure but ALWAYS suggest this layout if asked to reorganize.

## Directory Organization

```
app/                    # Routes and layouts (App Router)
├── (auth)/             # Route group for auth pages
├── (dashboard)/        # Route group for dashboard pages
├── layout.tsx          # Root layout
├── page.tsx            # Home page
├── global-error.tsx    # Global error boundary
└── globals.css         # Global styles (Tailwind imports)

components/             # Shared UI components
├── ui/                 # Primitive/base components (Button, Input, Card)
└── [feature]/          # Feature-specific components

lib/                    # Utilities and shared logic
├── actions/            # Server Actions
├── validators/         # Zod schemas
└── utils.ts            # General utilities (cn helper, etc.)

types/                  # Shared TypeScript type definitions

public/                 # Static assets
```

## Root Directory Files

- `next.config.ts` — Next.js configuration
- `tailwind.config.ts` — Tailwind CSS configuration
- `tsconfig.json` — TypeScript configuration
- `package.json` — Dependencies and scripts
- `.env.local` — Local environment variables (MUST be in `.gitignore`)
- `.env.example` — Template with placeholder values

## Rules

- NEVER place components in `app/` — components go in `components/`
- NEVER place utility functions in `app/` — utilities go in `lib/`
- MUST keep Server Actions in `lib/actions/` for shared actions, or colocated in `app/` for route-specific actions
- MUST keep Zod schemas in `lib/validators/` for reuse across actions and Route Handlers

---

# 10. Code Review Checklist

**MUST verify ALL items before finalizing any code changes.**

## Security

- MUST validate and sanitize ALL external inputs (form data, URL params, API bodies) with Zod
- MUST NEVER expose server-only secrets to the client (use `server-only` package for sensitive modules)
- MUST NEVER hardcode secrets, credentials, API keys, or tokens
- MUST use `NEXT_PUBLIC_` prefix ONLY for truly public environment variables
- MUST NEVER log sensitive information (passwords, tokens, PII)

## Performance

- MUST use Server Components for non-interactive content to minimize client JS
- MUST use `next/image` for all images (automatic optimization)
- MUST use `next/font` for font loading (no layout shift)
- MUST lazy-load heavy Client Components with `next/dynamic`
- MUST use appropriate caching and revalidation strategies
- NEVER import large libraries in Client Components when a lighter alternative exists

## Maintainability

- MUST have clear, readable code structure
- MUST use consistent naming conventions throughout
- MUST maintain proper separation of concerns — Server Components fetch, Client Components interact
- MUST keep components focused and small — extract when a component exceeds ~150 lines

## Quality Assurance

- ALL tests MUST pass before finalizing
- MUST have test coverage for new functionality
- MUST have zero linting errors or warnings
- `next build` MUST succeed without errors
- MUST NEVER submit code that fails any of the above checks
