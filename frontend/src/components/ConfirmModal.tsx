import { useEffect, useRef } from "react";

interface Props {
  open: boolean;
  title: string;
  /** Plain-text body. Renders as a single paragraph; pass `<>...</>` if you
   * need richer markup. */
  message: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Marks the confirm button as the destructive action — it gets the
   * `modal__danger` outline so the user reads it as a heavy click. */
  destructive?: boolean;
  pending?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Generic in-app confirm dialog. Replaces window.confirm so destructive
 * actions land in a Mono-styled modal instead of a browser-native popup
 * that escapes the focus scope.
 *
 * Self-contained: closes on Escape, backdrop click, or either button.
 * The CANCEL button is focused on open so a stray Enter doesn't fire the
 * destructive path.
 */
export function ConfirmModal({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  destructive = false,
  pending = false,
  onConfirm,
  onCancel,
}: Props) {
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const t = setTimeout(() => cancelRef.current?.focus(), 30);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      clearTimeout(t);
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      className="modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
    >
      <div
        className="modal modal--confirm"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
      >
        <div className="modal__head">
          <span className="modal__eyebrow" id="confirm-title">
            {title}
          </span>
          <button
            type="button"
            className="modal__close"
            aria-label="Close"
            onClick={onCancel}
          >
            ×
          </button>
        </div>
        <div className="modal__form">
          <p className="confirm__message">{message}</p>
          <div className="modal__actions">
            <div />
            <div className="modal__actions-right">
              <button
                ref={cancelRef}
                type="button"
                onClick={onCancel}
                disabled={pending}
              >
                {cancelLabel}
              </button>
              <button
                type="button"
                className={destructive ? "modal__danger" : ""}
                onClick={onConfirm}
                disabled={pending}
              >
                {pending ? "…" : confirmLabel}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
