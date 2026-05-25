import { useEffect, useRef, useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { ApiError, api } from "../api/client";

interface Props {
  open: boolean;
  onClose: () => void;
}

const RATING_VALUES = [1, 2, 3, 4, 5] as const;

/**
 * In-app feedback capture. Rating 1-5 (required) + free-text comments +
 * free-text bug notes (both optional). On success shows "Thanks!" inline
 * for a beat, then closes.
 *
 * Tied to the logged-in user server-side (admin can see who said what) —
 * we don't pretend it's anonymous in the UI. If we ever want anonymous
 * feedback that'd be a separate flow.
 */
export function FeedbackModal({ open, onClose }: Props) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const [rating, setRating] = useState<number | null>(null);
  const [comments, setComments] = useState("");
  const [bugs, setBugs] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  // Reset on every open. Always start from a blank slate — leftover state
  // from a previous submission would be confusing.
  useEffect(() => {
    if (!open) return;
    setRating(null);
    setComments("");
    setBugs("");
    setError(null);
    setSubmitted(false);
    const t = setTimeout(() => {
      // Focus the first rating button so keyboard users land somewhere
      // meaningful.
      dialogRef.current
        ?.querySelector<HTMLButtonElement>(".feedback__rating-btn")
        ?.focus();
    }, 30);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      clearTimeout(t);
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  const submit = useMutation({
    mutationFn: () => {
      if (rating === null) throw new Error("Pick a rating first.");
      return api.submitFeedback({
        rating,
        comments: comments.trim() || null,
        bugs: bugs.trim() || null,
      });
    },
    onSuccess: () => {
      setSubmitted(true);
      // Auto-close after a beat so the user gets confirmation but doesn't
      // have to click again.
      setTimeout(() => onClose(), 1200);
    },
    onError: (err) => {
      setError(
        err instanceof ApiError ? err.message : "Couldn't send — try again."
      );
    },
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (rating === null) {
      setError("Pick a rating first.");
      return;
    }
    submit.mutate();
  };

  if (!open) return null;

  return (
    <div
      className="modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        className="modal modal--feedback"
        role="dialog"
        aria-modal="true"
        aria-label="Send feedback"
      >
        <div className="modal__head">
          <span className="modal__eyebrow">Send feedback</span>
          <button
            type="button"
            className="modal__close"
            aria-label="Close"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        {submitted ? (
          <div className="modal__form">
            <p className="confirm__message">
              <strong>Thanks.</strong> Sent.
            </p>
          </div>
        ) : (
          <form className="modal__form" onSubmit={onSubmit}>
            <fieldset className="modal__field">
              <legend className="modal__label">
                Rating <span className="feedback__req" aria-hidden>·</span>
              </legend>
              <div
                className="feedback__rating"
                role="radiogroup"
                aria-label="Rate 1 to 5"
              >
                {RATING_VALUES.map((n) => (
                  <button
                    key={n}
                    type="button"
                    role="radio"
                    aria-checked={rating === n}
                    className={`feedback__rating-btn${
                      rating === n ? " feedback__rating-btn--active" : ""
                    }`}
                    onClick={() => setRating(n)}
                  >
                    {n}
                  </button>
                ))}
              </div>
              <div className="feedback__rating-legend" aria-hidden>
                <span>← rough</span>
                <span>great →</span>
              </div>
            </fieldset>

            <label className="modal__field">
              <span className="modal__label">Comments</span>
              <textarea
                value={comments}
                onChange={(e) => setComments(e.target.value)}
                placeholder="what's working, what's not, what would help…"
                rows={3}
                maxLength={5000}
              />
            </label>

            <label className="modal__field">
              <span className="modal__label">Bugs to highlight</span>
              <textarea
                value={bugs}
                onChange={(e) => setBugs(e.target.value)}
                placeholder="something broken? steps to reproduce help."
                rows={3}
                maxLength={5000}
              />
            </label>

            {error && <div className="auth-error">{error}</div>}

            <div className="modal__actions">
              <div />
              <div className="modal__actions-right">
                <button type="button" onClick={onClose}>
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submit.isPending || rating === null}
                >
                  {submit.isPending ? "Sending…" : "Send"}
                </button>
              </div>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
