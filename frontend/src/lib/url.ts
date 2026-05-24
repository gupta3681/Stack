/**
 * Defense-in-depth URL guard for click targets.
 *
 * The backend rejects non-http(s) direct_link values at the Pydantic
 * layer, but rendering paths should never trust storage blindly — old
 * data predating the validator, a bypass via a future bulk import, or
 * any other source of a `javascript:` / `data:` / `file:` URL must NOT
 * become an executable link.
 *
 * Returns the trimmed URL if it's a safe http(s) link, otherwise null.
 * Callers should treat null as "no link" and not render a clickable
 * element at all (no href, no window.open).
 */
export function safeHref(url: string | null | undefined): string | null {
  if (!url) return null;
  const trimmed = url.trim();
  if (!trimmed) return null;
  // ^https?:\/\/ — case-insensitive, scheme only. Rejects javascript:,
  // data:, vbscript:, file:, about:, chrome:, and protocol-relative //.
  if (!/^https?:\/\//i.test(trimmed)) return null;
  return trimmed;
}
