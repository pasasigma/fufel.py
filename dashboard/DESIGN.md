---
name: "База Миро"
description: "Black and green operational dashboard for the server team."
colors:
  primary: "#80e6aa"
  primary-hover: "#a1f4c1"
  primary-ink: "#10271a"
  background: "#080e0b"
  panel: "#122019"
  line: "#2c4035"
  text: "#eff7f2"
  muted: "#adbdb3"
  button: "#1b2b22"
  input: "#0b1610"
  input-line: "#3b5043"
  selected: "#d5f2df"
  selected-ink: "#173725"
  hero-light: "#9ae7b2"
  hero-deep: "#5dbc88"
  hero-ink: "#103322"
  stat: "#18271e"
  stat-emphasis: "#254f36"
  tag: "#213d2d"
  tag-text: "#c2e8cf"
  error: "#472a29"
  error-text: "#ffc4ad"
  pending: "#3c3824"
  pending-text: "#e9db92"
typography:
  display:
    fontFamily: "Manrope, sans-serif"
    fontSize: "clamp(29px, 3.2vw, 44px)"
    fontWeight: 800
    lineHeight: 1.18
    letterSpacing: "-.04em"
  headline:
    fontFamily: "Manrope, sans-serif"
    fontSize: "clamp(25px, 2.5vw, 36px)"
    fontWeight: 800
    lineHeight: 1.25
    letterSpacing: "-.035em"
  title:
    fontFamily: "Manrope, sans-serif"
    fontSize: "21px"
    fontWeight: 700
    lineHeight: 1.35
    letterSpacing: "-.02em"
  body:
    fontFamily: "Manrope, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.65
  label:
    fontFamily: "Manrope, sans-serif"
    fontSize: "12px"
    fontWeight: 700
  metric:
    fontFamily: "Manrope, sans-serif"
    fontSize: "31px"
    fontWeight: 800
    lineHeight: 1.15
    letterSpacing: "-.035em"
rounded:
  tag: "7px"
  field: "10px"
  button: "12px"
  nav: "16px"
  panel: "20px"
  dialog: "22px"
  hero: "23px"
  rail: "24px"
spacing:
  compact: "8px"
  control-gap: "9px"
  small: "12px"
  control-inline: "16px"
  grid-small: "18px"
  grid: "20px"
  panel: "26px"
  hero-block: "28px"
  hero-inline: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-ink}"
    rounded: "{rounded.button}"
    padding: "10px 16px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-secondary:
    backgroundColor: "{colors.button}"
    textColor: "{colors.text}"
    rounded: "{rounded.button}"
    padding: "10px 16px"
  button-subtle:
    backgroundColor: "transparent"
    textColor: "{colors.text}"
    rounded: "{rounded.button}"
    padding: "10px 16px"
  field:
    backgroundColor: "{colors.input}"
    textColor: "{colors.text}"
    rounded: "{rounded.field}"
    padding: "11px 13px"
  navigation-selected:
    backgroundColor: "{colors.selected}"
    textColor: "{colors.selected-ink}"
    rounded: "{rounded.nav}"
    width: "48px"
    height: "48px"
  tag:
    backgroundColor: "{colors.tag}"
    textColor: "{colors.tag-text}"
    rounded: "{rounded.tag}"
    padding: "3px 7px"
  stat-card:
    backgroundColor: "{colors.stat}"
    textColor: "{colors.text}"
    rounded: "{rounded.panel}"
    padding: "23px"
---

# Design System: База Миро

## Overview

**Creative North Star: "Спокойный центр управления"**

The implemented black and green world adapts the user-pinned Glassy Dashboard reference into a Russian-language operating space. Mint highlights and dark forest surfaces make the current workspace and primary action easy to distinguish; rounded containers keep dense controls approachable. This is a code-led record of the built interface, not an approved visual comp.

Depth comes from tonal layering, translucent fills, fine borders and one broad green gradient. Manrope and Lucide line icons provide a consistent visual voice across member management, messages, audit and access settings. The review captures are demonstration data and do not establish production metrics.

**Key Characteristics:**
- Near-black canvas with green surfaces and mint actions.
- Locally bundled Manrope with compact supporting labels.
- Rounded panels, fine borders and restrained depth.
- Russian copy, tabular metrics and explicit status text.

## Colors

Forest neutrals carry most surfaces; mint supplies the action color. The normative values above are extracted from `src/style.css`, including its actual CSS custom properties. The `panel` primitive is declared in the source, while visible generic panels use the gradient documented below.

### Primary
- **Fresh Mint** (`primary`, `primary-hover`): primary controls, focus outlines, icons and positive ledger changes; paired with dark `primary-ink`.
- **Meadow Light / Meadow Green** (`hero-light`, `hero-deep`): the overview's broad gradient with `hero-ink` text.

### Neutral
- **Night Forest** (`background`): page canvas.
- **Forest Surface** (`panel`, `stat`, `stat-emphasis`): declared panel base and the two implemented statistic surfaces.
- **Soft Chalk** (`text`): main copy; **Sage Grey** (`muted`): supporting copy.
- **Forest Edge** (`line`, `input-line`): dividers and field strokes.
- **Pale Mint** (`selected`) and **Deep Leaf** (`selected-ink`): selected navigation.
- **Dark Leaf** (`button`, `input`): control surfaces.

Error and pending colors are semantic audit treatments, not extra brand accents. Tags have their own green fill and pale-green text. Error rows pair warm text with an alert icon and a written result.

**The Status Has Words Rule.** Color reinforces an explicit status label; it never replaces one.

## Typography

**Display Font:** Manrope, sans-serif.
**Body Font:** Manrope, sans-serif.
**Label/Mono Font:** Manrope for labels; native browser monospace for command examples and identifiers.

Manrope is bundled locally in weights 400, 500, 600, 700 and 800. Broad, heavy headlines establish hierarchy above compact operational content. The frontmatter records repeated roles rather than asserting one body size for every element.

### Hierarchy
- **Display:** overview hero; the final phrase uses weight 500 and normal style. The heading is constrained to 75% width on large screens, 92% at the intermediate breakpoint.
- **Headline:** page greeting and page titles.
- **Title:** section headings. Smaller action-form headings use 16px.
- **Body:** operational prose is commonly 13px; general paragraphs use line-height 1.65. Message previews use 14px, while login prose uses 16px.
- **Label:** controls and compact action text; supporting labels range from 10px to 12px.
- **Metric:** tabular numerals in statistic cards and ledger amounts. The date is 29px; the login display separately scales from 40px to 66px.

## Layout

The desktop shell is centered with a maximum width of 1600px, 20px outer padding and a 26px gap. Its 76px icon rail is sticky at 20px, with viewport-relative height. The remaining workspace flexes and can shrink without forcing horizontal page overflow.

The overview is the reference-specific composition: greeting, broad hero beside quick links, four statistics, then recent audit events. Its first grid uses `minmax(0,1.8fr) minmax(300px,1fr)` with a 20px gap. Statistics use four equal columns and an 18px gap. Generic panels have 26px padding. Member management uses a separate list/detail split; message and access views use two equal columns.

At 1100px and below, shell padding becomes 14px, the rail 66px, the overview ratio 1.5:1, and paired form fields and the general two-column layout stack. At 800px and below, shell padding becomes 12px, the rail becomes a horizontally scrollable top bar, overview and member panels stack, and statistics use two columns. Panels use 20px padding. Audit filters retain two columns. The mobile review confirms this arrangement, including horizontal navigation scrolling.

Spacing is practical rather than a strict mathematical scale. Use the recorded recurring values for shared controls and grids; preserve local spacing where it encodes hierarchy.

## Elevation & Depth

Resting panels have no shadow. Their background is `linear-gradient(135deg,#1b2b21c9,#101c16e8)` over a canvas with a faint radial green wash. The rail also uses a translucent fill. There is no `backdrop-filter`. Shadows belong to transient feedback and confirmation surfaces.

### Shadow Vocabulary
- **Toast:** `0 12px 32px #0008` separates fixed feedback from page content.
- **Confirmation:** `0 0 0 100vmax #000b,0 20px 50px #0008` dims the surroundings and raises the modal.

**The Quiet Surface Rule.** Use tonal fills and borders for resting containers; reserve shadows for transient layers.

Statistic cards lift by 4px on hover through Framer Motion; the source specifies no custom duration or easing. `useReducedMotion` removes this lift. The reduced-motion media query also disables CSS animation, transition and smooth scrolling.

## Shapes

The frontmatter records the implemented radius vocabulary: small tags, softly rounded fields and buttons, larger panels and rail. Borders are generally 1px. The hero clips its oversized shield illustration; profile avatars are circular. Do not flatten all components to one radius: container corners are intentionally softer than control corners.

## Components

### Buttons
Confident filled actions, quieter secondary controls. The primary button uses mint with dark text, 10px by 16px padding, weight 700 and a minimum height of 44px. Hover uses the lighter mint token. Secondary controls use the dark button surface; hover becomes `#294333` with border `#648570`. Subtle buttons have transparent fill and 12px text. Text buttons have no border and mint text. Disabled buttons use opacity .48 and the not-allowed cursor. Keyboard focus is a 3px accent outline offset by 3px. There is no custom pressed-state style. Icon-only controls use accessible labels; some are 40px, and hero buttons are 42px, so 44px is not a universal implemented minimum.

### Chips
Role and status tags use compact green fill, a 1px `#4a6a55` border, 10px text and the tag radius. Danger tags use warm colors. The hero connection pill has a translucent fill, small dot and written status. These labels are not interactive filters.

### Cards / Containers
Generic panels use the forest gradient, line border and panel radius. Statistic cards use a flat forest surface; the second card receives the deeper green emphasis. Values use tabular numerals and can wrap. Panels are shadowless at rest; transient layers follow the elevation vocabulary.

### Inputs / Fields
Fields use the input surface, input-line stroke, field radius, 11px by 13px padding and minimum height 46px. Placeholder text is `#94a69b`; the caret is mint. Labels sit above fields, and textareas resize vertically. Focus uses the shared outline. No dedicated invalid-field visual style is implemented; request errors appear in an alert toast or retry panel.

### Navigation
A narrow rounded rail uses Lucide icons with hidden visible labels, accessible names and browser titles. The active section is a pale-mint rounded square with dark icon. The desktop target is 48px; mobile targets are 42px. On mobile, the rail flows horizontally and scrolls as needed. Selection is a visual class; no additional active-state semantics are claimed here.

### Hero and quick links
The hero uses a 115-degree meadow gradient, dark copy, generous padding and a low-opacity outlined shield. Its pale action button and transparent secondary action remain subordinate to the headline. The adjacent quick-links panel pairs icons with a short title, supporting line and outward arrow. These are overview patterns rather than a template for all forms.

### Audit, feedback and confirmation
Audit rows pair an icon block, action and actor information with right-aligned time and written status. Full audit rows expose detail disclosure. Empty and loading states use centered muted copy; failures provide a retry control. Toasts use status/alert roles. The native confirmation dialog keeps the requested operation, reason and optional message preview together above cancel and confirm buttons.

## Do's and Don'ts

### Do:
- Do preserve the black and green identity and use dark text on mint actions.
- Do use the existing Manrope weights and Lucide line icons.
- Do retain visible keyboard focus and reduced-motion behavior.
- Do label demonstration content and represent missing metrics with an em dash.
- Do keep member identity and the reason visible before confirming an operation.

### Don't:
- Don't turn the overview composition into a required layout for every screen.
- Don't add decorative charts or fabricate operational metrics.
- Don't describe the translucent fills as backdrop blur; none is implemented.
- Don't rely on color alone for audit status; retain icon and text.

### Переходы разделов
Основные панели и карточки вкладки появляются по очереди за 360 мс с cubic-bezier(.16,1,.3,1): translate от 16px до 0, opacity от .35 до 1. Задержка ограничена 190 мс. Контейнер получает ключ текущей вкладки, поэтому переход повторяется при навигации и не повторяется при вводе в форму. Reduced motion: только opacity .8→1 за 100 мс, без задержки и перемещения.
