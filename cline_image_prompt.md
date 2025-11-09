# Build pixel-faithful HTML/CSS from this wireframe

![Wireframe](design/wireframe-home.png)

**Goal:** Produce clean, accessible, responsive HTML/CSS that matches the wireframe exactly—no creativity.

**Requirements**
- Files:
  - `public/index.html`
  - `public/styles.css`
- HTML: semantic structure (header, nav, aside, main, section, footer), meaningful aria-labels.
- CSS: BEM naming, CSS variables for colors/spacing/typography; no frameworks; no inline styles; no JS.
- Font: Inter (fallback to system-ui).
- Layout rules:
  - Container max-width: 1200px; centered; 24px page padding.
  - Header: 72px sticky; left logo; right actions.
  - Sidebar: 260px fixed; full height; collapsible on <1024px.
  - Cards: 16px radius; 24px padding; shadow subtle.
  - Table: sticky header; zebra striping; row height 44px; ellipsis on long cells.
- Colors & type (use as CSS variables):
--bg:#0F172A; --surface:#111827; --card:#1F2937;
--text:#E5E7EB; --muted:#9CA3AF; --border:#334155;
--primary:#3B82F6; --success:#10B981; --danger:#EF4444;
--radius:16px; --pad:24px; --gap:24px;
--h1:28px; --h2:20px; --body:14px;

- Accessibility: color contrast ≥ 4.5:1 for text; focus outlines visible.
- Responsiveness: collapse sidebar <1024px; stack panels <768px.
- Content: **Use labels/text exactly as in the image**; where unreadable, use a short placeholder but TODO comment it.

**Deliverables**
1. Create `public/index.html` and `public/styles.css`.
2. Ensure the output, when opened in a browser, visually matches the wireframe.
3. Add a short README section at top of `index.html` as an HTML comment explaining structure.

**Do not** add JS or external fonts/CSS libs.

