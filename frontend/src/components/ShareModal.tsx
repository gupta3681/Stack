import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useInvalidateStacks } from "../hooks/useInvalidateStacks";
import type { Stack } from "../types";

interface Props {
  stack: Stack;
  open: boolean;
  onClose: () => void;
}

/**
 * Public-link modal for a topic stack. Three states:
 *   1. private + no slug ever generated → "Make public" CTA
 *   2. private + slug exists (un-shared)  → "Re-share to get the same link"
 *   3. public                              → URL + copy + "Make private"
 */
export function ShareModal({ stack, open, onClose }: Props) {
  const qc = useQueryClient();
  const invalidate = useInvalidateStacks();
  const dialogRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!open) return;
    setCopied(false);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const onSuccess = (updated: Stack) => {
    // Update the cached stack so the parent view sees is_public flip immediately.
    qc.setQueryData(["topic-stack", stack.id], updated);
    invalidate();
  };

  const share = useMutation({
    mutationFn: () =>
      stack.id !== null
        ? api.shareTopicStack(stack.id)
        : Promise.reject(new Error("Unsaved stack")),
    onSuccess,
  });

  const unshare = useMutation({
    mutationFn: () =>
      stack.id !== null
        ? api.unshareTopicStack(stack.id)
        : Promise.reject(new Error("Unsaved stack")),
    onSuccess,
  });

  const toggleContext = useMutation({
    mutationFn: (include: boolean) =>
      stack.id !== null
        ? api.updateTopicStack(stack.id, { share_context_in_public: include })
        : Promise.reject(new Error("Unsaved stack")),
    onSuccess,
  });

  if (!open) return null;

  const publicUrl =
    stack.share_slug !== null
      ? `${window.location.origin}/s/${stack.share_slug}`
      : null;

  const handleCopy = async () => {
    if (!publicUrl) return;
    try {
      await navigator.clipboard.writeText(publicUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API blocked (insecure context, etc.) — fall through silently.
    }
  };

  return (
    <div
      className="modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label="Share stack"
      >
        <div className="modal__head">
          <span className="modal__eyebrow">
            Share · {stack.name ?? "Stack"}
          </span>
          <button
            type="button"
            className="modal__close"
            aria-label="Close"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <div className="modal__form">
          {stack.is_public ? (
            <>
              <p className="share__status share__status--public">
                Public — anyone with the link can see this stack.
              </p>
              <div className="share__url-row">
                <input
                  className="share__url"
                  value={publicUrl ?? ""}
                  readOnly
                  onFocus={(e) => e.currentTarget.select()}
                />
                <button type="button" onClick={handleCopy}>
                  {copied ? "Copied" : "Copy"}
                </button>
              </div>
              <label className="share__toggle">
                <input
                  type="checkbox"
                  checked={stack.share_context_in_public}
                  disabled={toggleContext.isPending}
                  onChange={(e) => toggleContext.mutate(e.target.checked)}
                />
                <span>
                  Include rich context (markdown notes) for visitors
                </span>
              </label>
              <p className="share__hint">
                Hidden from visitors: tasks marked done, your in-progress
                timer, completion timestamps. Only the queued items show.
                {!stack.share_context_in_public
                  ? " Long-form notes stay private until you flip the switch above."
                  : ""}
              </p>
              <div className="modal__actions">
                <button
                  type="button"
                  className="modal__danger"
                  onClick={() => unshare.mutate()}
                  disabled={unshare.isPending}
                >
                  {unshare.isPending ? "…" : "Make private"}
                </button>
                <div className="modal__actions-right">
                  <button type="button" onClick={onClose}>
                    Done
                  </button>
                </div>
              </div>
            </>
          ) : (
            <>
              <p className="share__status">
                Private. Make this stack public to get a shareable link.
              </p>
              {stack.share_slug !== null && (
                <p className="share__hint">
                  This stack was shared before. Re-sharing will return the
                  same link as last time —{" "}
                  <code>{`${window.location.origin}/s/${stack.share_slug}`}</code>
                  .
                </p>
              )}
              <div className="modal__actions">
                <div />
                <div className="modal__actions-right">
                  <button type="button" onClick={onClose}>
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={() => share.mutate()}
                    disabled={share.isPending}
                  >
                    {share.isPending
                      ? "…"
                      : stack.share_slug !== null
                        ? "Re-share"
                        : "Make public"}
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
