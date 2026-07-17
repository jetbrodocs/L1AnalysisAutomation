# Jetbro Brand Guidelines

Apply these guidelines when generating any visual output, document, or styled content for Jetbro.

## Colors

| Name | Hex | Usage |
|------|-----|-------|
| Accent | `#c45a32` | Links, highlights, accent line, call-to-action elements |
| Accent Light | `#d97b4a` | Gradient endpoint only — never used standalone |
| Text | `#1a1a1a` | Primary text, headings, logo fill |
| Secondary | `#4a4a4a` | Subtitles, labels, secondary text |
| Muted | `#7a7a7a` | Metadata, captions, fine print |
| Background | `#ffffff` | Page background |

## Typography

**Bricolage Grotesque** — display/headings. Weights: 400, 600, 700. Fallback: `'Helvetica Neue', 'Arial', sans-serif`

**Outfit** — body text. Weights: 300, 400, 500, 600. Fallback: `'Helvetica Neue', 'Arial', sans-serif`

**Space Mono** — monospace/code. Weights: 400, 700. Fallback: `'Courier New', monospace`

Google Fonts link (copy into `<head>`):

```html
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@400;600;700&family=Outfit:wght@300;400;500;600&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
```

## Logo

Reference: `logo.svg` in the same folder (`jetbro-brand/logo.svg`).

- Uses `fill="currentColor"` — inherits text color, no need to set fill explicitly
- Minimum display height: 14px (small contexts like cards), 28px (standard/letterhead)
- No background container or border needed — display directly on white or light backgrounds
- For dark backgrounds, set parent text color to white

## Accent Line

Signature separator pattern — use after headers and between major sections. Always full-width within content area.

If you import `tokens.css`, use the ready-made class:

```html
<hr class="jetbro-accent-line">
```

Otherwise, copy this pattern. The `@media print` fallback is **required** — without it the gradient renders as a solid black bar in PDF/print export, because print engines strip gradient backgrounds by default. In print, fall back to solid accent orange.

```css
.jetbro-accent-line {
  height: 2px;
  border: 0;
  background: linear-gradient(90deg, #c45a32, #d97b4a, transparent);
}
@media print {
  .jetbro-accent-line {
    background: #c45a32 !important;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
}
```

## Spacing & Layout (Print)

For A4 documents:

- Page margins: 20mm sides, 15–20mm top
- Content font size: 9.5–11pt
- Line height: 1.5–1.7
- Company name in headers: 10px, uppercase, letter-spacing 3px, color `#4a4a4a`

## Design Principles

- Minimal and clean — use generous whitespace, no heavy borders
- Use `#c45a32` sparingly — links, accent line, occasional highlights only; never large filled areas
- Tables use thin borders (`#ddd` or `#eee`), not bold rules
- Use Space Mono for data and numbers (amounts, codes, IDs)
- Left-align most content; right-align addresses and amounts

## CSS Tokens

`tokens.css` in the same folder provides CSS custom properties. For web projects, import it:

```css
@import url('./tokens.css');
```

Then use variables like `var(--jetbro-accent)`, `var(--jetbro-font-body)`, etc.
