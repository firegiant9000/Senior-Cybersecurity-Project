import React, { useState } from "react";
import { sendPasswordResetEmail, sendEmailVerification } from "firebase/auth";
import { auth } from "../firebase";
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";
import "./LoginPage.css";

export default function LoginPage({ defaultSignUp = false }: { defaultSignUp?: boolean }) {
  const { login, signup } = useAuth();
  const navigate = useNavigate();

  const [isSignUp, setIsSignUp] = useState(defaultSignUp);
  const [isForgotPassword, setIsForgotPassword] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (isSignUp && password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    if (isSignUp && password.length < 6) {
      setError("Password must be at least 6 characters");
      return;
    }

    setLoading(true);
    try {
      if (isSignUp) {
        await signup(email, password);
        // Send verification email after signup
        if (auth.currentUser) {
          await sendEmailVerification(auth.currentUser);
        }
      } else {
        await login(email, password);
      }
      navigate("/dashboard");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Authentication failed";
      if (message.includes("user-not-found") || message.includes("wrong-password") || message.includes("invalid-credential")) {
        setError("Invalid email or password");
      } else if (message.includes("email-already-in-use")) {
        setError("An account with this email already exists");
      } else if (message.includes("invalid-email")) {
        setError("Invalid email address");
      } else if (message.includes("weak-password")) {
        setError("Password is too weak — use at least 6 characters");
      } else {
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (!email) {
      setError("Please enter your email address");
      return;
    }

    setLoading(true);
    try {
      await sendPasswordResetEmail(auth, email);
      setSuccess("Password reset email sent! Check your inbox.");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to send reset email";
      if (message.includes("user-not-found")) {
        setError("No account found with this email");
      } else if (message.includes("invalid-email")) {
        setError("Invalid email address");
      } else if (message.includes("too-many-requests")) {
        setError("Too many requests. Please try again later.");
      } else {
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  };

  // Forgot password view
  if (isForgotPassword) {
    return (
      <div className="login-page">
        <div className="login-card">
          <div className="login-header">
            <img src="/logo.png" alt="Hacker Tracker" className="login-logo" />
            <h1>Cyber Threat Intelligence</h1>
            <p>Reset your password</p>
          </div>

          <form onSubmit={handleForgotPassword} className="login-form">
            {error && <div className="login-error">{error}</div>}
            {success && <div className="login-success">{success}</div>}

            <div className="form-group">
              <label htmlFor="reset-email">Email</label>
              <input
                id="reset-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                autoComplete="email"
              />
            </div>

            <button type="submit" className="login-btn" disabled={loading}>
              {loading ? "Sending..." : "Send Reset Email"}
            </button>
          </form>

          <div className="login-footer">
            <button
              type="button"
              className="toggle-btn"
              onClick={() => {
                setIsForgotPassword(false);
                setError("");
                setSuccess("");
              }}
            >
              Back to sign in
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Login / Signup view
  return (
    <div className={`login-page${isSignUp ? " login-page--signup" : ""}`}>
      <div className="login-card">
        <div className="login-header">
          <img src="/logo.png" alt="Hacker Tracker" className="login-logo" />
          <h1>Cyber Threat Intelligence</h1>
          <p>{isSignUp ? "Create your account" : "Sign in to your account"}</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          {error && <div className="login-error">{error}</div>}
          {success && <div className="login-success">{success}</div>}

          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              autoComplete="email"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 6 characters"
              required
              autoComplete={isSignUp ? "new-password" : "current-password"}
            />
          </div>

          {isSignUp && (
            <div className="form-group">
              <label htmlFor="confirmPassword">Confirm Password</label>
              <input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter your password"
                required
                autoComplete="new-password"
              />
            </div>
          )}

          <button type="submit" className="login-btn" disabled={loading}>
            {loading ? "Please wait..." : isSignUp ? "Create Account" : "Sign In"}
          </button>
        </form>

        <div className="login-footer">
          {!isSignUp && (
            <button
              type="button"
              className="toggle-btn forgot-btn"
              onClick={() => {
                setIsForgotPassword(true);
                setError("");
                setSuccess("");
              }}
            >
              Forgot your password?
            </button>
          )}
          <button
            type="button"
            className="toggle-btn"
            onClick={() => {
              setIsSignUp(!isSignUp);
              setError("");
              setSuccess("");
            }}
          >
            {isSignUp
              ? "Already have an account? Sign in"
              : "Don't have an account? Sign up"}
          </button>
        </div>
      </div>
    </div>
  );
}
