import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const NOT_CONFIRMED =
  "We couldn't confirm your address yet. Open the link in the email, then try again.";
const buttonStyle = { padding: "0.5rem 1rem", cursor: "pointer" } as const;

/**
 * Shown when the API refuses an account because its email is not verified.
 * `onVerified` runs after the address is confirmed (for example to retry an
 * invite acceptance that was refused).
 */
export default function VerifyEmailPanel({ onVerified }: { onVerified?: () => Promise<void> }) {
  const { user, resendVerification, confirmVerification, logout } = useAuth();
  const navigate = useNavigate();
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const handleResend = async () => {
    setBusy(true);
    try {
      setMessage(await resendVerification());
    } finally {
      setBusy(false);
    }
  };

  const handleConfirm = async () => {
    setBusy(true);
    setMessage("");
    try {
      // Still unverified if Firebase says so, or if the server refused/failed the profile load.
      const profileLoaded = await confirmVerification();
      if (!profileLoaded || (user && !user.emailVerified)) {
        setMessage(NOT_CONFIRMED);
        return;
      }
      await onVerified?.();
    } catch {
      setMessage(NOT_CONFIRMED);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", flexDirection: "column", gap: "1rem" }}>
      <p>Verify your email address to continue. We sent a link to {user?.email}.</p>
      {message && <p role="status">{message}</p>}
      <button onClick={handleResend} disabled={busy} style={buttonStyle}>
        Resend verification email
      </button>
      <button onClick={handleConfirm} disabled={busy} style={buttonStyle}>
        I&apos;ve verified my email
      </button>
      <button onClick={async () => { await logout(); navigate("/"); }} style={{ ...buttonStyle, opacity: 0.7 }}>
        Log Out
      </button>
    </div>
  );
}
