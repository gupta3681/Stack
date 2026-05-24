/**
 * Tiny tolerant YAML-frontmatter parser/serializer.
 *
 * Used by the task edit modal (to keep input fields synced with the
 * markdown) and the public viewer (to strip frontmatter before rendering
 * the body). Not real YAML — single-line `key: value` only, no quoting,
 * no multi-line scalars. Anything richer should go in the body.
 *
 * Whitespace contract:
 *   - Serialize emits `key: value` (one space after the colon as separator).
 *   - Parse strips exactly ONE leading whitespace char after the colon
 *     (the separator), preserving any further leading and all trailing
 *     space inside the value. This is what lets the user type spaces
 *     mid-word in input fields without round-tripping eating them.
 */

export const KNOWN_FRONTMATTER_KEYS = [
  "name",
  "description",
  "direct_link",
] as const;
export type KnownFrontmatterKey = (typeof KNOWN_FRONTMATTER_KEYS)[number];

export interface ParsedFrontmatter {
  fields: Record<string, string>;
  body: string;
}

export function parseMd(md: string): ParsedFrontmatter {
  if (!md.startsWith("---")) return { fields: {}, body: md };
  const lines = md.split(/\r?\n/);
  if (lines[0].trim() !== "---") return { fields: {}, body: md };

  let endIdx = -1;
  for (let i = 1; i < lines.length; i++) {
    if (lines[i].trim() === "---") {
      endIdx = i;
      break;
    }
  }
  if (endIdx === -1) return { fields: {}, body: md };

  const fields: Record<string, string> = {};
  for (let i = 1; i < endIdx; i++) {
    const line = lines[i];
    const colonIdx = line.indexOf(":");
    if (colonIdx === -1) continue;
    const key = line.slice(0, colonIdx).trim();
    // Strip ONE leading separator char only — preserve any further spaces
    // the user typed (matters for editable input fields).
    const value = line.slice(colonIdx + 1).replace(/^[ \t]/, "");
    if (key) fields[key] = value;
  }
  const body = lines
    .slice(endIdx + 1)
    .join("\n")
    .replace(/^\n+/, "");
  return { fields, body };
}

export function serializeMd(p: ParsedFrontmatter): string {
  const knownLines = KNOWN_FRONTMATTER_KEYS.filter((k) => p.fields[k]).map(
    (k) => `${k}: ${p.fields[k]}`
  );
  const unknownLines = Object.entries(p.fields)
    .filter(([k]) => !KNOWN_FRONTMATTER_KEYS.includes(k as KnownFrontmatterKey))
    .map(([k, v]) => `${k}: ${v}`);
  const fmLines = [...knownLines, ...unknownLines];
  if (fmLines.length === 0) return p.body;
  return p.body
    ? `---\n${fmLines.join("\n")}\n---\n\n${p.body}`
    : `---\n${fmLines.join("\n")}\n---\n`;
}
