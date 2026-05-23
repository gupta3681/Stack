# mono — Style Reference
> Architectural grid on white

**Theme:** light

MONO X7 employs a stark, almost architectural aesthetic, reminiscent of an artist's canvas or technical drawing. The visual system is dominated by high contrast black text and lines on a pristine white background, often utilizing a grid-like structure. Typography is precise and highly customized, with distinct weight and letter-spacing variations that dictate hierarchy through subtle means. Interactions are signaled not with color, but by the presence or absence of thin, sharp borders, giving components a planar rather than volumetric feel.

## Colors

| Name | Value | Role |
|------|-------|------|
| Canvas White | `#ffffff` | Page backgrounds, card surfaces, form input fields — a stark, pure white for a clean, expansive feel |
| Ink Black | `#292929` | Primary text, headings, button borders, icons, dividing lines — provides sharp definition against Canvas White. Acts as the primary border and text color for interactive elements |
| Deep Black | `#000000` | Decorative fills (SVGs), input text, and borders — used sparingly for maximum contrast in specific UI elements |

## Typography

### NH — Primary headings and body text. Its subtle negative letter-spacing contributes to the precise, condensed feel.
- **Substitute:** Helvetica Neue
- **Weights:** 100, 300, 400
- **Sizes:** 16px, 18px, 25px, 32px, 40px, 43px
- **Line height:** 1.20, 1.25, 1.27, 1.34, 1.50
- **Letter spacing:** -0.0200em

### S-Condensed — Navigation links, metadata, and labels. The pronounced positive letter-spacing creates a distinctive, airy appearance for functional text.
- **Substitute:** Impact
- **Weights:** 300, 400, 500
- **Sizes:** 12px, 14px, 40px
- **Line height:** 0.90, 1.18, 1.20, 1.34
- **Letter spacing:** 0.1000em, 0.2000em

### EV — Specialized, extremely light headlines. Its very tight tracking and light weight make it feel almost etched.
- **Substitute:** Roboto Thin
- **Weights:** 100
- **Sizes:** 28px
- **Line height:** 0.90
- **Letter spacing:** -0.0500em

### S-Works — Unique, expressive headlines. The moderate weight and normal letter-spacing allow it to stand out against more tracked and condensed fonts.
- **Substitute:** Bebas Neue Pro
- **Weights:** 350
- **Sizes:** 40px
- **Line height:** 1.34
- **Letter spacing:** normal

### Type Scale

| Role | Size | Line Height | Letter Spacing |
|------|------|-------------|----------------|
| caption | 12px | 1.18 | 1.2px |
| body | 16px | 1.5 | -0.32px |
| subheading | 18px | 1.25 | -0.36px |
| heading | 25px | 1.27 | -0.5px |
| heading-lg | 32px | 1.2 | -0.64px |
| display-sm | 40px | 1.34 | -0.8px |
| display | 43px | 1.34 | -0.86px |

## Spacing & Layout

**Base unit:** 4px

**Density:** comfortable

- **Section gap:** 40px
- **Card padding:** 20px
- **Element gap:** 8px

### Border Radius

- **none:** 0px

## Components

### Outline Button
**Role:** Primary and secondary actions with minimal visual weight.

Text in Ink Black (#292929) on a transparent background, with a 1px solid Ink Black border and 0px radius. Padding is 0px top/bottom, 20px left/right, giving a wide, flat appearance.

### Minimal Input Field
**Role:** Standard text input fields.

Background is Canvas White (#ffffff), text is Deep Black (#000000), with a 1px solid Deep Black border. No border-radius. Padding is 8px top/bottom, 0px left/right, emphasizing vertical alignment.

### Navigation Link
**Role:** Top-level navigation items and language selectors.

Utilizes S-Condensed, with specific letter-spacing. Colors are Ink Black (#292929) for text. Often appears with a thin Ink Black border on hover or active state to denote selection.

### Section Heading
**Role:** Major content section titles.

Typography from NH family, often at 43px or 40px, with specific letter-spacing -0.0200em. Uses Ink Black (#292929) color. Frequently bordered by Ink Black lines to separate content areas.

## Do's and Don'ts

### Do
- Maintain a clear, high-contrast between Ink Black (#292929) text/lines and Canvas White (#ffffff) backgrounds.
- Utilize 0px border-radius for all interactive elements and containers to maintain the precise, angular aesthetic.
- Apply positive letter-spacing (0.1em or 0.2em) from S-Condensed for navigation, tags, and small labels to distinguish them from body text.
- Use thin (1px) Ink Black (#292929) borders as the primary visual cue for interactive elements and content divisions.
- Structure layouts using visible grid lines or strong horizontal/vertical divisions rather than relying on card elevation or soft shadows.
- Emphasize content hierarchy through variations in font-family, weight, and letter-spacing rather than relying on color or large size differences.
- For buttons, use transparent backgrounds with Ink Black (#292929) text and borders, with 0px vertical padding and 20px horizontal padding.

### Don't
- Avoid using any color other than Ink Black (#292929), Deep Black (#000000), or Canvas White (#ffffff) for primary UI elements.
- Do not introduce rounded corners or soft shadows; all elements should adhere to a sharp, planar aesthetic.
- Do not use generic system fonts for headings or key interface elements; always select from the specified custom typography.
- Avoid large and complex hero components; opt for minimal, high-contrast textual statements or product visuals on a Canvas White (#ffffff) background.
- Do not use subtle gray text for functional elements; all text, save for contextual accents, should be Ink Black for maximum impact.
- Do not use excessive padding or element gaps; maintain an efficient information density with 8px as a common element gap and 20px for card padding.
- Do not design buttons with solid background fills; all buttons should be ghosted or outlined.

## Imagery

Imagery primarily consists of product photography, abstract graphics, and occasional textual illustrations. Product photos are tight crops, often showcasing the hardware in an abstract or deconstructed manner, with a heavy emphasis on geometric patterns and technical diagrams. Illustrations are abstract, using a monochromatic palette to match the UI, with strong geometric shapes, dots, and lines (e.g., printed circuit board patterns). Icons are minimalist, outlined, and monochromatic, with a fine stroke weight. The role of imagery is primarily decorative atmosphere and product showcase, with a relatively low density compared to text-heavy sections. Images are typically contained within defined areas, often bordered by the same thin black lines as other UI elements.

## Layout

The page uses a full-bleed layout, particularly for the main canvas, but frequently employs strong vertical and horizontal dividers to create distinct, modular content blocks. The hero section often features a large, singular product image or graphic, sometimes with overlay text, defining a clear focal point. Content progresses with a mix of stacked, centered headlines and text blocks, alongside two-column layouts where text and visuals alternate. A strong underlying grid is evident, with elements often snapping to these implicit lines. Vertical rhythm is established through consistent spacing, and sections can alternate between pure white and light gray backgrounds for differentiation. Navigation is minimalist, adhering to a fixed top bar on larger screens with simple text links.

## Similar Brands

- **Teenage Engineering** — Shares a precise, almost brutalist, high-contrast monochrome aesthetic with custom, technical typography.
- **Braun (Dieter Rams era)** — Emphasizes clear functional hierarchy, minimalist forms, and a strict adherence to grid systems, leveraging whitespace dramatically.
- **Ars Technica** — Uses a similarly crisp, high-contrast black-on-white layout with distinct typography for a dense, information-rich presentation.
- **OP-1** — Strong product focus on geometric design, often showcased with technical diagrams and a minimalist approach to branding and UI.
