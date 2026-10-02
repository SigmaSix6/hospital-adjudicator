# Reviewer UI: Colour Tokens and Usage

The reviewer UI (`ui/`) is an extra on top of the required API. It follows the supplied design
brief: a calm healthcare palette using Siloam-style blue and yellow.

> **Proposed tokens, not verified brand values.** The hex values below come from the design
> brief as a starting point. They have not been checked against official Siloam Hospitals brand
> guidelines. Replace them with official values if those are available.

## Token Table

| Token | Hex | Role |
|---|---|---|
| `--brand-blue` | `#1456A0` | Primary actions, links, focus ring, selected case border |
| `--brand-blue-hover` | `#10457F` | Hover/pressed state of primary actions |
| `--brand-blue-subtle` | `#EAF3FC` | Selected list item, rule-ID tags, secondary surfaces |
| `--brand-navy` | `#16324F` | Header bar, text on yellow/blue tints, raw JSON panel |
| `--brand-yellow` | `#F5C542` | Restrained accent only: header underline, policy-quote rule, live indicator dot |
| `--brand-yellow-subtle` | `#FFF7D6` | "Requires human review" chip, highlighted evidence rows, uncertainty note |
| `--brand-teal` | `#168C8C` | Reserved for charts/large accents (not used for body text, see contrast) |
| `--surface-page` | `#F7F9FC` | Page background |
| `--surface-card` | `#FFFFFF` | Cards, tables |
| `--text-primary` | `#1D2939` | Body text |
| `--text-secondary` | `#667085` | Secondary text, captions |
| `--border-default` | `#E4E7EC` | Decorative dividers and card borders |
| `--input` | `#8A94A6` | Form-control boundaries (switch track); adjusted from the brief's neutral so it meets 3:1 |
| `--status-success` / `-subtle` | `#18794E` / `#ECFDF3` | "No issues found", passed checks |
| `--status-warning` / `-subtle` | `#A15C00` / `#FFFAEB` | "Needs review", medium severity, undetermined checks |
| `--status-error` / `-subtle` | `#B42318` / `#FEF3F2` | High severity, failed checks, blank values, API offline |
| `--status-info` / `-subtle` | `#175CD3` / `#EFF8FF` | Low severity (informational) |

The CSS custom properties are defined in `ui/src/app/globals.css`. They are mapped to the shadcn/ui
semantic variables (`--primary`, `--secondary`, `--border`, ...) and exposed to Tailwind v4
through `@theme inline` as `bg-brand-blue`, `text-warning`, `bg-error-subtle`, and so on.

## Usage Rules

- **Navigation/header:** navy background, white text, 4 px yellow underline as the only large use of yellow.
- **Buttons:** primary = brand blue with white text; secondary/outline on white; destructive is not used (the assistant never rejects).
- **Status:** always icon + text + colour (shield icon with "Needs review" / "No issues found";
  octagon / triangle / info icon with "High / Medium / Low severity"). Colour is never the only signal.
- **Evidence:** cited document rows get a subtle-yellow background **and** a highlighter icon with an accessible label.
- **Forms:** the Live/Mock control is a labelled radio group; the cache switch has a visible `<label>`.
- **Density:** restrained shadows (`shadow-sm` on cards only), 1 px subtle borders, generous padding, 12 px radius.

## Contrast Notes (WCAG 2.2 AA)

| Pair | Ratio | Verdict |
|---|---:|---|
| White on brand blue `#1456A0` | 7.32 | Pass (normal text) |
| White on blue hover `#10457F` | 9.63 | Pass |
| Primary text `#1D2939` on white | 14.70 | Pass |
| Secondary text `#667085` on white / page | 4.97 / 4.72 | Pass (normal text) |
| Navy on subtle blue / subtle yellow / yellow | 11.68 / 12.18 / 8.08 | Pass |
| White on navy header | 13.10 | Pass |
| Success on success-subtle | 5.13 | Pass |
| Warning on warning-subtle | 4.97 | Pass |
| Error on error-subtle | 6.05 | Pass |
| Info on info-subtle | 5.57 | Pass |
| **Yellow `#F5C542` on white** | **1.62** | **Fail.** Never use yellow for text or as the only boundary of a control. |
| **Teal `#168C8C` on white** | **4.07** | **Fails for normal text**, passes for large text (≥ 3:1). Use only for large text, icons, or charts. |
| Input boundary `#8A94A6` on white | 3.06 | Pass (non-text UI component, 3:1) |
| Decorative border `#E4E7EC` on white | 1.24 | Decorative only (not a component boundary) |

Focus states use a 3 px brand-blue ring at 50% opacity on top of the element border. Keyboard
focus is visible on case-list items, the mode toggle, tabs and buttons.
