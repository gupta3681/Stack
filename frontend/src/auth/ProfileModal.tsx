import { useEffect, useRef, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "../api/client";
import { ConfirmModal } from "../components/ConfirmModal";
import type { ApiToken, ApiTokenCreated } from "../types";
import { useAuth } from "./AuthContext";

interface Props {
  open: boolean;
  onClose: () => void;
}

type Tab = "general" | "password" | "tokens";

const TABS: { value: Tab; label: string }[] = [
  { value: "general", label: "General" },
  { value: "password", label: "Password" },
  { value: "tokens", label: "API Tokens" },
];

function formatTokenDate(iso: string | null): string {
  if (!iso) return "Never used";
  // Postgres/SQLite naive datetimes arrive as "2026-05-25T12:00:00" — no Z,
  // no offset. Tz-aware ones look like "...+00:00" or "...Z". Append Z only
  // when neither suffix is already there; otherwise we produce "...+00:00Z"
  // and `new Date()` returns Invalid Date.
  const hasTzSuffix = /(Z|[+-]\d{2}:?\d{2})$/.test(iso);
  const d = new Date(hasTzSuffix ? iso : iso + "Z");
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function ProfileModal({ open, onClose }: Props) {
  const { user, refresh, logout } = useAuth();
  const qc = useQueryClient();
  const dialogRef = useRef<HTMLDivElement>(null);

  const [tab, setTab] = useState<Tab>("general");

  const [displayName, setDisplayName] = useState(user?.display_name ?? "");
  const [profileNote, setProfileNote] = useState<string | null>(null);

  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordNote, setPasswordNote] = useState<string | null>(null);

  // Token creation state. `justCreated` holds the raw token immediately after
  // it's minted — surfaced ONCE for copy. Cleared on modal close, tab leave,
  // and explicit Dismiss.
  const [tokenName, setTokenName] = useState("");
  const [tokenError, setTokenError] = useState<string | null>(null);
  const [revokeError, setRevokeError] = useState<string | null>(null);
  const [justCreated, setJustCreated] = useState<ApiTokenCreated | null>(null);
  const [copyNote, setCopyNote] = useState<string | null>(null);
  // Holds the token row pending revoke confirmation. Null = no dialog open.
  const [pendingRevoke, setPendingRevoke] = useState<ApiToken | null>(null);

  // Modal-open reset: ONLY depend on `open`. If we also depended on `user` or
  // `onClose`, a parent re-render (counts refetch, sibling state change)
  // would re-fire the reset and wipe in-progress typing or the freshly-
  // revealed token. The latest values for `user` etc. are captured at the
  // moment open flips true, which is when we actually want to use them.
  useEffect(() => {
    if (!open) return;
    setTab("general");
    setDisplayName(user?.display_name ?? "");
    setProfileNote(null);
    setCurrentPw("");
    setNewPw("");
    setConfirmPw("");
    setPasswordError(null);
    setPasswordNote(null);
    setTokenName("");
    setTokenError(null);
    setRevokeError(null);
    setJustCreated(null);
    setCopyNote(null);
    setPendingRevoke(null);
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
    // Intentional: only re-run on open transitions.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Clear the once-shown raw token + copy hint whenever the user leaves the
  // Tokens tab. Without this, switching to Password and back re-renders the
  // reveal box verbatim, breaking the "shown once" promise.
  useEffect(() => {
    if (tab !== "tokens") {
      setJustCreated(null);
      setCopyNote(null);
      setRevokeError(null);
    }
  }, [tab]);

  // Helper: if a mutation/query 401s, the session is dead — log out so the
  // user lands on the login page instead of a silently-broken modal.
  const handle401 = (err: unknown): boolean => {
    if (err instanceof ApiError && err.status === 401) {
      logout();
      return true;
    }
    return false;
  };

  const saveProfile = useMutation({
    mutationFn: () =>
      api.updateProfile({ display_name: displayName.trim() || null }),
    onSuccess: async () => {
      setProfileNote("Saved.");
      await refresh();
    },
    onError: (err) => {
      if (handle401(err)) return;
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
      // Don't auto-logout on 401 from /change-password — that just means the
      // current password was wrong. Show the message instead.
      setPasswordError(
        err instanceof ApiError ? err.message : "Couldn't change password."
      );
    },
  });

  // Tokens tab: fetch only while visible AND force a fresh load each visit
  // (staleTime: 0) so a token created/revoked in another browser tab is
  // reflected immediately.
  const tokensQuery = useQuery({
    queryKey: ["api-tokens"],
    queryFn: () => api.listApiTokens(),
    enabled: open && tab === "tokens",
    staleTime: 0,
  });

  // 401 from the tokens list = session expired. Log out so the user isn't
  // staring at a silently-broken empty list.
  useEffect(() => {
    handle401(tokensQuery.error);
    // handle401 is referentially stable enough for this; logout is from
    // context and the auth provider memoizes it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tokensQuery.error]);

  const createToken = useMutation({
    mutationFn: () => api.createApiToken(tokenName.trim()),
    onSuccess: (token) => {
      setJustCreated(token);
      setTokenName("");
      setTokenError(null);
      setCopyNote(null);
      qc.invalidateQueries({ queryKey: ["api-tokens"] });
    },
    onError: (err) => {
      if (handle401(err)) return;
      setTokenError(err instanceof ApiError ? err.message : "Couldn't create token.");
    },
  });

  const revokeToken = useMutation({
    mutationFn: (id: number) => api.revokeApiToken(id),
    onSuccess: () => {
      setRevokeError(null);
      qc.invalidateQueries({ queryKey: ["api-tokens"] });
    },
    onError: (err) => {
      if (handle401(err)) return;
      setRevokeError(
        err instanceof ApiError ? err.message : "Couldn't revoke token."
      );
      // Refetch in case the row was already gone server-side (404 race) —
      // the list should converge with reality even on failure.
      qc.invalidateQueries({ queryKey: ["api-tokens"] });
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

  const submitToken = (e: FormEvent) => {
    e.preventDefault();
    setTokenError(null);
    if (!tokenName.trim() || createToken.isPending) return;
    createToken.mutate();
  };

  const copyToken = async () => {
    if (!justCreated) return;
    try {
      await navigator.clipboard.writeText(justCreated.token);
      setCopyNote("Copied to clipboard.");
    } catch {
      setCopyNote("Couldn't copy — tap the field, then ⌘C / Ctrl+C.");
    }
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

        <div className="profile__tabs" role="tablist" aria-label="Profile sections">
          {TABS.map((t) => (
            <button
              key={t.value}
              type="button"
              role="tab"
              aria-selected={tab === t.value}
              className={`profile__tab${tab === t.value ? " profile__tab--active" : ""}`}
              onClick={() => setTab(t.value)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === "general" && (
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
                <button type="submit" disabled={saveProfile.isPending}>
                  {saveProfile.isPending ? "Saving…" : "Save"}
                </button>
              </div>
            </div>
          </form>
        )}

        {tab === "password" && (
          <form className="modal__form" onSubmit={submitPassword}>
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
        )}

        {tab === "tokens" && (
          <div className="modal__form">
            <p className="profile__hint">
              Long-lived bearer tokens for CLIs, agents, and the Claude Code
              skill file. Use in <code>Authorization: Bearer …</code>.
            </p>

            {justCreated && (
              <div className="token__reveal">
                <div className="token__reveal-label">
                  Save this token now — it won't be shown again.
                </div>
                {/* Textarea (not div) so manual select-all works reliably on
                 * mobile WebKit where `user-select: all` is unreliable, and
                 * for HTTP origins where navigator.clipboard is undefined. */}
                <textarea
                  className="token__reveal-value"
                  value={justCreated.token}
                  readOnly
                  rows={2}
                  aria-label="New API token"
                  onFocus={(e) => e.currentTarget.select()}
                />
                <div className="token__reveal-actions">
                  <button type="button" onClick={copyToken}>
                    Copy
                  </button>
                  <button type="button" onClick={() => setJustCreated(null)}>
                    Dismiss
                  </button>
                </div>
                {copyNote && <div className="profile__note">{copyNote}</div>}
              </div>
            )}

            <form className="token__create" onSubmit={submitToken}>
              <input
                className="modal__title-input"
                value={tokenName}
                onChange={(e) => setTokenName(e.target.value)}
                placeholder="Token name (e.g. laptop, claude-code)"
                aria-label="New token name"
                maxLength={100}
              />
              <button
                type="submit"
                disabled={createToken.isPending || !tokenName.trim()}
              >
                {createToken.isPending ? "Generating…" : "Generate"}
              </button>
            </form>
            {tokenError && <div className="auth-error">{tokenError}</div>}
            {revokeError && <div className="auth-error">{revokeError}</div>}

            <ul className="token__list">
              {tokensQuery.isLoading && (
                <li className="token__empty">Loading…</li>
              )}
              {tokensQuery.data && tokensQuery.data.length === 0 && (
                <li className="token__empty">No tokens yet.</li>
              )}
              {tokensQuery.data?.map((t) => {
                // Per-row disabled: only THIS row's button shows pending,
                // not every Revoke in the list. revokeToken.variables holds
                // the most-recent mutate() argument.
                const rowRevoking =
                  revokeToken.isPending && revokeToken.variables === t.id;
                return (
                  <li key={t.id} className="token__row">
                    <div className="token__row-main">
                      <span className="token__row-name">{t.name}</span>
                      <span className="token__row-prefix">
                        {t.prefix}
                        {"…"}
                      </span>
                    </div>
                    <div className="token__row-meta">
                      Created {formatTokenDate(t.created_at)} ·{" "}
                      {t.last_used_at
                        ? `last used ${formatTokenDate(t.last_used_at)}`
                        : "never used"}
                    </div>
                    <button
                      type="button"
                      className="token__revoke"
                      onClick={() => {
                        setRevokeError(null);
                        setPendingRevoke(t);
                      }}
                      disabled={rowRevoking}
                    >
                      {rowRevoking ? "Revoking…" : "Revoke"}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        <ConfirmModal
          open={pendingRevoke !== null}
          title="Revoke token"
          message={
            pendingRevoke ? (
              <>
                Revoke <strong>"{pendingRevoke.name}"</strong>? Any client
                using this token will stop working immediately.
              </>
            ) : null
          }
          confirmLabel="Revoke"
          destructive
          pending={
            revokeToken.isPending &&
            revokeToken.variables === pendingRevoke?.id
          }
          onCancel={() => setPendingRevoke(null)}
          onConfirm={() => {
            if (!pendingRevoke) return;
            revokeToken.mutate(pendingRevoke.id, {
              onSettled: () => setPendingRevoke(null),
            });
          }}
        />
      </div>
    </div>
  );
}
