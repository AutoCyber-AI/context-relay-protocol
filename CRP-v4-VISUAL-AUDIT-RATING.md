# CRP v4 Visual & Accessibility Audit — Harsh Critic Rating

**Date:** 2026-06-05  
**Audited from the perspective of:**
- A user with **low vision** (needs WCAG AA+ contrast, large fonts, visible focus)
- A user with **motor impairment** (needs 44×44px touch targets, no precision required)
- A user with **cognitive impairment** (needs clear hierarchy, simple language, consistent patterns)
- A user with **vestibular disorder** (needs reduced motion, no unexpected movement)
- A **screen reader user** (needs proper labels, landmarks, live regions, heading hierarchy)
- A **harsh design critic** (expects pixel-perfect polish, zero broken affordances)

---

## Overall Verdict

| Product | Before | After | Delta |
|---------|--------|-------|-------|
| **Gateway Console** | 3/10 | **7.5/10** | +4.5 |
| **Comply Frontend** | 4/10 | **8/10** | +4.0 |

**Neither is a 10/10 yet.** Both have made dramatic leaps from "barely usable for disabled users" to "solidly accessible with remaining polish gaps." The Comply frontend edges ahead due to its component-system architecture making systematic fixes easier.

---

## Gateway Console — 7.5/10

### What Got Fixed (The Good)

| Category | Fix | Impact |
|----------|-----|--------|
| **Skip link** | Added `#skip-link` — first Tab press jumps to main content | Keyboard users save 15+ Tab presses on every load |
| **Landmarks** | `<main>`, `<nav role="tablist">`, `<h1 class="visually-hidden">` | Screen reader users can now navigate by landmark and heading |
| **Focus** | Solid 2px accent outline with 3px offset, never removed on inputs | Visible to everyone, including low-vision users |
| **Labels** | ALL 12 inputs now have `for`/`id` associations | Screen readers announce "Name, edit text" instead of "edit text, blank" |
| **Touch targets** | Min 44px height on buttons, rail links, menu toggle | Motor-impaired users can tap without precision |
| **Button IDs** | `sys-btn`, `prov-btn`, `pg-btn`, `doc-btn`, `bill-dev`, `bill-team` | `setLoading()` actually works; no more double-submit or stuck buttons |
| **Error resilience** | All 5 async handlers use `try/finally` | Network errors no longer leave buttons permanently disabled |
| **aria-live** | Auth status, all 4 result `<pre>` blocks, toast region | Screen readers announce "System registered" and "Network error" |
| **Mobile rail** | Backdrop overlay, Escape-to-close, focus moves to first tab | No more trapping behind open menu; dismissible 3 ways |
| **Tables** | `overflow-x:auto` wrappers, `<caption>`, `scope="col"` | Mobile doesn't force page scroll; screen readers know table context |
| **Deceptive UI** | "Drag blocks" → "read-only preview", "Live stream" → "Recent calls" | Cognitive users no longer attempt impossible interactions |
| **Disabled stubs** | Save Pipeline / Test buttons are visibly disabled with `title` | Users know these aren't broken, just not ready |
| **Noscript** | Fallback warning if JS fails | At least users know *why* nothing works |
| **Contrast** | Red lightened to `#ff6b7a`, text-dim brightened, placeholder opacity 0.85 | Previously failing elements now pass WCAG AA |

### What Still Sucks (The Bad)

| Issue | Severity | Why It Matters |
|-------|----------|----------------|
| **Dark mode ONLY** | Medium | Users with astigmatism, photophobia, or certain visual field defects need light themes. No `prefers-color-scheme: light`. |
| **No high-contrast mode** | Medium | `prefers-contrast: more` is ignored. Faint borders (`rgba(255,255,255,0.08)`) disappear for users who need strong boundaries. |
| **Raw JSON dumps** | Medium | Result blocks are unformatted JSON. Overwhelming for screen reader users (reads every brace and quote) and cognitively dense for everyone. |
| **No confirmation dialogs** | Medium | Delete/revoke actions in the Comply console have confirmations, but Gateway has none for provider removal or system deletion. One accidental click = data loss. |
| **No session timeout** | Low | A console managing API keys and billing should warn before session expiry. |
| **Charts are placeholders** | Low | "Calls Over Time" is still text. No actual chart, no data table alternative. |
| **Landing page untouched** | Low | `_LANDING_HTML` still has the same issues (animated signal line without reduced-motion gate for the sweep animation, though body-level reduce would catch it). |
| **Focus trap incomplete** | Low | Mobile rail focuses first tab on open, but doesn't *trap* focus. A keyboard user can Tab out of the open menu into the background. Escape and backdrop click work, though. |
| **No `aria-invalid`** | Low | Form validation errors show toasts but don't mark the offending input with `aria-invalid="true"` or link error text via `aria-describedby`. |

### Harsh Critic Notes

> "The console went from 'designer portfolio piece that ignores disabled users' to 'actually functional for a screen reader.' The tablist role on the rail is correct. The skip link works. But it's still a dark-only interface with raw JSON vomit for output. If I'm a low-vision user trying to register a system, I shouldn't have to listen to `{\"system_id\":\"sys_abc\",\"name\":...}` read character-by-character. Format the damn output. Add a light theme. Then we'll talk about 9/10."

### Score Breakdown

| Criterion | Score | Notes |
|-----------|-------|-------|
| Perceivable (contrast, size) | 8/10 | Contrast fixed, fonts 16px+, but dark-only excludes some users |
| Operable (keyboard, touch) | 8/10 | Skip link, 44px targets, Escape works, but focus trap incomplete |
| Understandable (cognitive) | 7/10 | No more deceptive UI, but raw JSON is cognitively hostile |
| Robust (screen readers) | 7/10 | Landmarks, labels, live regions work, but no aria-invalid |
| Visual Polish | 7/10 | Clean dark UI, but no light theme, no high-contrast, charts are fake |
| **Overall** | **7.5/10** | Solid B+. Not an A yet. |

---

## Comply Frontend — 8/10

### What Got Fixed (The Good)

| Category | Fix | Impact |
|----------|-----|--------|
| **Brand contrast** | `text-brand-900` on ALL brand backgrounds | White-on-yellow (~1.4:1) → dark-on-yellow (~7:1). Every badge, CTA, hero text now passes WCAG AA |
| **Focus ring** | Solid `#9DAB34` outline, no opacity | Previously invisible to low-vision users; now unmistakable |
| **aria-current** | Every `NavLink` announces "current page" | Screen reader users know where they are |
| **Reduced motion** | `@media (prefers-reduced-motion: reduce)` kills ALL animations | Users with vestibular disorders are safe |
| **Font sizes** | All `text-[9px]`/`[10px]`/`[11px]` → `text-xs` (12px+) | No more illegible 6.75pt badges; respects browser font prefs |
| **Input labels** | API key name, filter select, onboarding textarea all properly labeled | Screen readers announce field purpose |
| **Icon buttons** | `aria-label` on copy, revoke, delete buttons | Screen reader users know what the icon does |
| **Alert regions** | `role="alert"` on errors, `role="status"` on successes | Dynamic feedback is announced automatically |
| **Table a11y** | `<caption className="sr-only">`, `scope="col"` on headers | Screen readers associate cells with headers |
| **Mobile public nav** | Hamburger menu with `aria-expanded`/`aria-controls` | Mobile users can actually reach Pricing, Docs, etc. |
| **Dark mode** | PublicLayout respects `dark:` classes | Public pages no longer flashbang dark-mode users |
| **Route announcements** | `aria-live` region announces page title on navigation | Screen reader users know the page changed |
| **Toggle** | `role="switch"` + `aria-checked` | Screen readers announce "toggle button, pressed/not pressed" |
| **Mobile drawer** | Focus moves to close button on open, Escape closes | Keyboard users aren't lost in the drawer |
| **Touch targets** | Sidebar `py-3`, icon buttons `h-10 w-10`, sticky nav `py-2` | 44px minimum largely met |
| **Gray contrast** | `text-gray-400` → `text-gray-600` across 40+ files | Previously failing captions now pass AA |
| **Hardcoded status** | "passed" → "pending" in v2 Dashboard | No longer lies to users |

### What Still Sucks (The Bad)

| Issue | Severity | Why It Matters |
|-------|----------|----------------|
| **Brand color is still yellow-green** | High (design constraint) | `#D4E84A` fundamentally cannot carry white text. We fixed this by using dark text, but it limits the palette. Any designer who wants white text on a CTA is blocked. The brand itself is the problem. |
| **Tables still horizontally scroll** | Medium | `overflow-x-auto` is better than page scroll, but horizontal scrolling in tables is still hard for motor-impaired users. No card-flipping alternative view. |
| **No confirmation dialogs** | Medium | Delete report, revoke API key, remove provider — all instant. A tremor or accidental Enter keypress is irreversible. |
| **Keyboard shortcuts** | Medium | Vim-style "G ?" chords in AppShell still conflict with NVDA/JAWS navigation shortcuts. No way to disable them. |
| **Charts lack alternatives** | Medium | ComplianceRing SVG, quality distribution bars — no `aria-label` describing the data values. The numbers are visible, but the SVG graphic itself is unlabeled. |
| **Dark mode on public pages is basic** | Low | Just `bg-white dark:bg-gray-900`. Marketing pages weren't fully redesigned for dark mode — images, gradients, and some components may look off. |
| **Some `text-[11px]` may remain** | Low | Edge cases in external components or deeply nested files might have been missed. The regex sweep was broad but not exhaustive. |
| **Disabled buttons removed from tab order** | Low | `disabled` attribute removes buttons from keyboard navigation. Users can't tab to them to discover *why* they're disabled. `aria-disabled` with tooltips would be better. |
| **No breadcrumbs** | Low | Users with cognitive impairments have no hierarchical orientation. |

### Harsh Critic Notes

> "The Comply frontend made the bigger leap because it had more to fix and a component system to make it systematic. The white-on-brand fix alone saves the entire experience for low-vision users. But let's be real: the brand color is still a design trap. You can't put white text on it. Ever. That means every 'highlighted' CTA, every badge, every promo banner is forced into dark-text-on-yellow, which looks fine but limits expressiveness. And the tables — yeah, they scroll horizontally now instead of breaking the page, but try scrolling a table with Parkinson's. You need a card view. Also, deleting a report with no confirmation? In a compliance product? That's a lawsuit waiting to happen. Fix those three things and this is a 9.5."

### Score Breakdown

| Criterion | Score | Notes |
|-----------|-------|-------|
| Perceivable (contrast, size) | 9/10 | Brand contrast fixed, fonts readable, focus visible, but brand color is a permanent constraint |
| Operable (keyboard, touch) | 8/10 | 44px targets, skip link, mobile nav, but no confirmation dialogs and shortcut conflicts remain |
| Understandable (cognitive) | 8/10 | Clear labels, no deceptive UI, but tables need card view and breadcrumbs are missing |
| Robust (screen readers) | 8/10 | aria-current, live regions, table scope, but charts lack full alternatives |
| Visual Polish | 8/10 | Professional, consistent, but dark mode on public pages is superficial |
| **Overall** | **8/10** | Solid A-. Close to excellent. |

---

## Side-by-Side: Before vs. After

| Scenario | Before | After |
|----------|--------|-------|
| Screen reader user opens Gateway | "Link, Dashboard. Link, Systems. Link, Providers..." (no landmarks, no headings, no skip link) | "Navigation region, Console sections. Tab, Dashboard, selected. Tab, Systems, not selected..." (proper tablist, skip link, h1) |
| Low-vision user reads "Best value" badge | White text on yellow-green (~1.4:1) — invisible | Dark text on yellow-green (~7:1) — crisp and clear |
| Motor-impaired user taps "Register System" | Button is ~28px tall, misses, double-taps | Button is 44px tall, taps successfully |
| User with tremor tries to delete API key | No confirmation, instantly revoked | **Still no confirmation** — instant revoke |
| Screen reader user submits form with error | Error appears silently; user doesn't know | "Alert: System name is required" announced immediately |
| Vestibular disorder user opens mobile nav | Sidebar slides in with animation, no way to stop | **No animation** if `prefers-reduced-motion` is set |
| Keyboard-only user navigates Comply | Taps through 12 nav items every page load | Skip link jumps straight to content |
| Colorblind user checks connection status | Green dot only, no text label | Green dot + "Connected" text + role=status |

---

## Path to 10/10

### Gateway Console (needs +2.5 points)
1. **Add light theme** (`prefers-color-scheme: light`) — +0.5
2. **Add high-contrast mode** (`prefers-contrast: more`) — +0.5
3. **Format JSON results as human-readable HTML** instead of raw `<pre>` dumps — +0.5
4. **Add confirmation dialogs** for destructive actions — +0.5
5. **Implement actual charts** with data table alternatives — +0.5

### Comply Frontend (needs +2.0 points)
1. **Add confirmation dialogs** for all destructive actions — +0.5
2. **Add card view alternative** to horizontally-scrolling tables — +0.5
3. **Fix keyboard shortcut conflicts** or add disable option — +0.3
4. **Add chart text alternatives** (aria-label with data summary) — +0.3
5. **Full dark mode redesign** of public/marketing pages — +0.4

---

*Rating by Kimi Code CLI, 2026-06-05. Both products have been materially improved but require the remaining items above to reach true 10/10 accessibility and visual excellence.*
