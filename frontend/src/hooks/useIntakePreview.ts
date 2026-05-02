import { useEffect, useRef, useState } from "react";
import {
  previewAssessmentIntake,
  type AssessmentIntakePreviewRequest,
  type AssessmentIntakeResponse,
} from "../api/assessmentIntake";

const DEBOUNCE_MS = 350;

/**
 * Debounced live tier-preview hook.
 *
 * Re-fires `POST /intake-preview` whenever the payload changes (debounced),
 * abort-cancelling the prior request so out-of-order responses can't clobber
 * fresher state.
 */
export function useIntakePreview(
  payload: AssessmentIntakePreviewRequest,
  enabled: boolean,
): { preview: AssessmentIntakeResponse | null; loading: boolean } {
  const [preview, setPreview] = useState<AssessmentIntakeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const payloadKey = JSON.stringify(payload);
  const inflightRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!enabled) return;

    const t = setTimeout(() => {
      inflightRef.current?.abort();
      const ctrl = new AbortController();
      inflightRef.current = ctrl;
      setLoading(true);

      previewAssessmentIntake(payload, ctrl.signal)
        .then((resp) => {
          if (!ctrl.signal.aborted) setPreview(resp);
        })
        .catch((err: unknown) => {
          // Ignore aborts; surface real failures only in console.
          if (ctrl.signal.aborted) return;
          if (err instanceof DOMException && err.name === "AbortError") return;
          console.warn("Intake preview failed:", err);
        })
        .finally(() => {
          if (!ctrl.signal.aborted) setLoading(false);
        });
    }, DEBOUNCE_MS);

    return () => {
      clearTimeout(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [payloadKey, enabled]);

  useEffect(() => {
    return () => {
      inflightRef.current?.abort();
    };
  }, []);

  return { preview, loading };
}
