import { useEffect, useRef, useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { ApiError, api } from "../api/client";
import { useAuth } from "./AuthContext";

interface Props {
  open: boolean;
  onClose: () => void;
}

export function ProfileModal({ open, onClose }: Props) {
  const { user, refresh } = useAuth();
  const dialogRef = useRef<HTMLDivElement>(null);

  const [displayName, setDisplayName] = useState(user?.display_name ?? "");
  const [profileNote, setProfileNote] = useState<string | null>(null);

  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordNote, setPasswordNote] = useState<string | null>(null);

  // Reset form state every time the modal opens so we don't show leftover
  // success messages from a previous edit.
  useEffect(() => {
    if (!open) return;
    setDisplayName(user?.display_name ?? "");
    setProfileNote(null);
    setCurrentPw("");
    setNewPw("");
    setConfirmPw("");
    setPasswordError(null);
    setPasswordNote(null);
    const t = setTimeout(() => {
      dialogRef.current
        ?.querySelector<HTMLInputElement>(".profile__display-name-input")
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
  }, [open, user, onClose]);

  const saveProfile = useMutation({
    mutationFn: () =>
      api.updateProfile({ display_name: displayName.trim() || null }),
    onSuccess: async () => {
      setProfileNote("Saved.");
      await refresh();
    },
    onError: (err) => {
      setProfileNote(
        err instanceof ApiError ? err.message : "Couldn't save."
      );
    },
  });

  const changePassword = useMutation({
    mutationFn: () =>
      api.changePassword({
        current_password: currentPw,
        new_password: newPw,
      }),
    onSuccess: () => {
      setPasswordNote("Password changed.");
      setCurrentPw("");
      setNewPw("");
      setConfirmPw("");
    },
    onError: (err) => {
      setPasswordError(
        err instanceof ApiError ? err.message : "Couldn't change password."
      );
    },
  });

  const submitProfile = (e: FormEvent) => {
    e.preventDefault();
    setProfileNote(null);
    saveProfile.mutate();
  };

  const submitPassword = (e: FormEvent) => {
    e.preventDefault();
    setPasswordError(null);
    setPasswordNote(null);
    if (newPw !== confirmPw) {
      setPasswordError("New passwords don't match.");
      return;
    }
    changePassword.mutate();
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
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label="Profile"
      >
        <div className="modal__head">
          <span className="modal__eyebrow">Profile</span>
          <button
            type="button"
            className="modal__close"
            aria-label="Close"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <form className="modal__form" onSubmit={submitProfile}>
          <div className="modal__field">
            <span className="modal__label">Email</span>
            <div className="profile__readonly">{user?.email}</div>
          </div>

          <label className="modal__field">
            <span className="modal__label">Display name</span>
            <input
              className="modal__title-input profile__display-name-input"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="(none)"
              maxLength={100}
            />
          </label>

          {profileNote && <div className="profile__note">{profileNote}</div>}

          <div className="modal__actions">
            <div />
            <div className="modal__actions-right">
              <button type="button" onClick={onClose}>
                Close
              </button>
              <button type="submit" disabled={saveProfile.isPending}>
                {saveProfile.isPending ? "Saving…" : "Save"}
              </button>
            </div>
          </div>
        </form>

        <div className="profile__divider" aria-hidden />

        <form className="modal__form" onSubmit={submitPassword}>
          <div className="profile__section-title">Change password</div>

          <label className="modal__field">
            <span className="modal__label">Current password</span>
            <input
              type="password"
              autoComplete="current-password"
              value={currentPw}
              onChange={(e) => setCurrentPw(e.target.value)}
              required
            />
          </label>

          <label className="modal__field">
            <span className="modal__label">New password</span>
            <input
              type="password"
              autoComplete="new-password"
              minLength={8}
              value={newPw}
              onChange={(e) => setNewPw(e.target.value)}
              required
            />
          </label>

          <label className="modal__field">
            <span className="modal__label">Confirm new password</span>
            <input
              type="password"
              autoComplete="new-password"
              minLength={8}
              value={confirmPw}
              onChange={(e) => setConfirmPw(e.target.value)}
              required
            />
          </label>

          {passwordError && <div className="auth-error">{passwordError}</div>}
          {passwordNote && <div className="profile__note">{passwordNote}</div>}

          <div className="modal__actions">
            <div />
            <div className="modal__actions-right">
              <button
                type="submit"
                disabled={
                  changePassword.isPending ||
                  !currentPw ||
                  !newPw ||
                  !confirmPw
                }
              >
                {changePassword.isPending ? "Changing…" : "Change password"}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
