# Visual Expert — CRP UI/UX Design System Skill

## Purpose

Use this skill whenever you are asked to design, review, or refactor the user interface of any CRP product (CRP Comply, CRP Gateway, CRP Scan, marketing site). It encodes the project's design tokens, accessibility requirements, animation rules, and component patterns so every screen stays consistent and production-ready.

## When to invoke

- Designing a new page, modal, card, form, dashboard, or landing page.
- Refactoring an existing component that looks "off" or scores poorly on a visual audit.
- Adding a new feature that needs UI (agent chat, reports, billing, onboarding).
- Reviewing accessibility, contrast, motion, or responsive behaviour.
- Converting a static HTML/CSS/JS page to React + TypeScript + Tailwind.

## Design tokens

### Color palette

All colors are defined in Tailwind as CSS custom properties in `frontend/src/index.css` and configured in `tailwind.config.js`.

| Token | Hex | Usage |
|-------|-----|-------|
| `--color-primary-500` | `#F5C518` | Primary actions, icons, highlights, accents |
| `--color-primary-400` | `#F7D147` | Hover states |
| `--color-primary-600` | `#D4A017` | Active/pressed states |
| `--color-surface-900` | `#0B0C10` | Primary backgrounds (dark mode) |
| `--color-surface-800` | `#1F2833` | Cards, panels, elevated surfaces |
| `--color-surface-700` | `#2A3646` | Borders, dividers, subtle separators |
| `--color-slate-300` | `#C5C6C7` | Body text on dark |
| `--color-slate-400` | `#66FCF1` | Teal accent for links, success, info |
| `--color-error-500` | `#EF4444` | Errors, denials, severe severity |
| `--color-warning-500` | `#F97316` | Warnings, medium severity |
| `--color-success-500` | `#22C55E` | Success, allow, healthy |

Light mode is supported by swapping the surface/text tokens. High-contrast mode doubles border contrast and uses `#000`/`#FFF` extremes.

### Typography

- Headings: `Space Grotesk`, weights 600-700.
- Body: `Inter`, weights 400-500.
- Code/mono: `JetBrains Mono`, weights 400-500.
- Never use font sizes below `0.75rem` (12 px). Minimum body size is `0.875rem` (14 px).

### Spacing & shape

- Base unit: `0.25rem` (4 px).
- Card padding: `1.5rem` (24 px).
- Border radius: `0.75rem` (12 px) for cards, `9999px` for pills.
- Shadows: `shadow-lg` for cards, `shadow-primary/20` for glowing accents.

### Animation rules

- Default transition: `transition-all duration-200 ease-out`.
- Entrance animations: `fade-in`, `slide-up`, `slide-in-right` (max 300 ms).
- Hover scale: `hover:scale-[1.02]` only on interactive cards.
- Respect `prefers-reduced-motion`: all animations collapse to `0.01ms` in `index.css`.
- Never auto-play motion that cannot be paused.

## Accessibility checklist

Every new or refactored screen MUST satisfy:

1. **Contrast**: WCAG AA for normal text (4.5:1), AAA for small text. Use the ` APCA` contrast checker if unsure.
2. **Focus**: Visible focus rings (`ring-2 ring-primary-400 ring-offset-2 ring-offset-surface-900`).
3. **Touch targets**: Minimum 24×24 CSS pixels for all clickable elements.
4. **Color not alone**: Severity/status is shown with icon + text label, never color alone.
5. **Motion safe**: Animations respect `prefers-reduced-motion`.
6. **Semantics**: Correct heading hierarchy, `aria-live` for toasts, `role="dialog"` for modals, `aria-current` for active nav items.
7. **Keyboard**: All interactive elements reachable; modals trap focus and close on Escape; return focus on close.

## Component patterns

### Cards

```tsx
<div className="rounded-xl border border-surface-700 bg-surface-800 p-6 shadow-lg">
  <h3 className="text-lg font-semibold text-slate-100">Title</h3>
  <p className="mt-2 text-slate-300">Body</p>
</div>
```

### Primary button

```tsx
<button className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary-500 px-4 py-2.5 font-medium text-surface-900 transition hover:bg-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-400 focus:ring-offset-2 focus:ring-offset-surface-900 disabled:opacity-50">
  Label
</button>
```

### Severity badge

```tsx
<span className="inline-flex items-center gap-1.5 rounded-full bg-error-500/10 px-2.5 py-1 text-sm font-medium text-error-500">
  <AlertTriangleIcon className="h-4 w-4" />
  High
</span>
```

### Form input

```tsx
<label className="block text-sm font-medium text-slate-300" htmlFor="x">
  Label
</label>
<input
  id="x"
  className="mt-1 block w-full rounded-lg border border-surface-700 bg-surface-900 px-3 py-2 text-slate-100 placeholder-slate-500 focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
/>
```

### Toast

Use the existing `ToastProvider` and `useToast()` hook. Never create ad-hoc alert banners.

## Migration rules

When migrating a static HTML/CSS/JS page to React + TypeScript + Tailwind:

1. Keep copy human-readable: clear headings, short paragraphs, bullet lists.
2. Replace custom CSS with Tailwind utility classes mapped to design tokens.
3. Replace imperative DOM manipulation with React state and effects.
4. Add TypeScript interfaces for all props and data shapes.
5. Decompose into small components (header, hero, feature grid, CTA, footer).
6. Preserve SEO meta tags via `react-helmet-async` or Vite plugin.
7. Add a `<link rel="canonical">` and OpenGraph tags for landing pages.
8. Ensure the page is responsive: mobile-first, breakpoints `sm`, `md`, `lg`, `xl`.
9. Score the result mentally against the 10-point visual audit rubric (below).

## Visual audit rubric

Use this rubric to score any page from 1–10. A production landing page must reach 9–10.

| Points | Requirement |
|--------|-------------|
| 1 | Loads without errors; content visible |
| 2 | Readable typography; no broken layouts |
| 3 | Consistent color palette |
| 4 | Clear visual hierarchy |
| 5 | Proper spacing and alignment |
| 6 | Accessible contrast and focus states |
| 7 | Responsive on mobile/tablet/desktop |
| 8 | Professional polish: shadows, rounded corners, icons |
| 9 | Motion and micro-interactions feel intentional |
| 10 | Feels like a best-in-class SaaS product |

## Anti-patterns to avoid

- Gradient text on headings (deprecated; use solid high-contrast text).
- Tiny font sizes, all-caps labels, or text-as-images.
- Color-only status indicators.
- Modal without focus trap or Escape-to-close.
- Long unbroken paragraphs of marketing copy.
- Inline styles or `!important` unless absolutely necessary.
- Hard-coded hex values; always use design tokens.

## Example prompt responses

When asked to "make the landing page look professional", respond by:

1. Auditing the current page against the rubric.
2. Proposing a component structure (Hero, Social proof, Features, How it works, Pricing, CTA, Footer).
3. Rewriting copy to be benefit-led and concise.
4. Implementing with design tokens, accessibility, and responsiveness.
5. Adding a toast/confirmation for the primary CTA.
6. Returning the score before and after.
