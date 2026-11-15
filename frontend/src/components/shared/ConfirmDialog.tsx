import { useCallback, useEffect, useId, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import './ConfirmDialog.css';

export interface ConfirmOptions {
  title: string;
  body: ReactNode;
  confirmLabel: string;
  tone?: 'danger' | 'default';
  cancelLabel?: string;
  onConfirm: () => Promise<void>;
}

interface ConfirmDialogProps extends ConfirmOptions {
  open: boolean;
  onClose: () => void;
}

export default function ConfirmDialog({
  open,
  onClose,
  title,
  body,
  confirmLabel,
  tone = 'danger',
  cancelLabel = 'Cancel',
  onConfirm,
}: ConfirmDialogProps) {
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const mountedRef = useRef(true);
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const onCloseRef = useRef(onClose);
  const titleId = useId();
  const bodyId = useId();

  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (open) cancelRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (!busyRef.current) {
          e.preventDefault();
          onCloseRef.current();
        }
        return;
      }
      if (e.key !== 'Tab') return;
      const first = cancelRef.current;
      const last = confirmRef.current;
      if (!first || !last) return;
      e.preventDefault();
      if (busyRef.current) return;
      const active = document.activeElement;
      if (!dialogRef.current?.contains(active)) {
        first.focus();
        return;
      }
      if (e.shiftKey) {
        (active === first ? last : first).focus();
      } else {
        (active === last ? first : last).focus();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [open]);

  const handleConfirm = async () => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    try {
      await onConfirm();
    } catch {
      // The caller's onConfirm owns its error state; the dialog just closes.
    } finally {
      busyRef.current = false;
      if (mountedRef.current) {
        setBusy(false);
        onCloseRef.current();
      }
    }
  };

  if (!open) return null;

  return (
    <div className="confirm-backdrop">
      <div
        ref={dialogRef}
        className="confirm-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={bodyId}
        aria-busy={busy}
      >
        <h2 id={titleId} className="confirm-title">
          {title}
        </h2>
        <div id={bodyId} className="confirm-body">
          {body}
        </div>
        <div className="confirm-actions">
          <button
            ref={cancelRef}
            type="button"
            className="confirm-btn confirm-btn-cancel"
            disabled={busy}
            onClick={() => onClose()}
          >
            {cancelLabel}
          </button>
          <button
            ref={confirmRef}
            type="button"
            className={`confirm-btn confirm-btn-confirm confirm-btn-${tone}`}
            disabled={busy}
            onClick={handleConfirm}
          >
            {busy ? 'Working…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export function useConfirm(): {
  confirm: (opts: ConfirmOptions) => void;
  confirmDialog: ReactNode;
} {
  const [opts, setOpts] = useState<ConfirmOptions | null>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);

  const openRef = useRef(false);
  const genRef = useRef(0);
  const hostMountedRef = useRef(true);

  useEffect(() => {
    hostMountedRef.current = true;
    return () => {
      hostMountedRef.current = false;
    };
  }, []);

  const closeGen = useCallback((gen: number) => {
    if (gen !== genRef.current || !openRef.current) return;
    openRef.current = false;
    if (hostMountedRef.current) setOpts(null);
    const el = returnFocusRef.current;
    returnFocusRef.current = null;
    if (el && el.isConnected) el.focus();
  }, []);

  const confirm = useCallback(
    (o: ConfirmOptions) => {
      if (openRef.current) return;
      openRef.current = true;
      genRef.current += 1;
      const gen = genRef.current;
      returnFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      // Close in the hook's own finally so it happens even if the dialog
      // component is unmounted while the action is pending.
      const wrapped = async () => {
        try {
          await o.onConfirm();
        } finally {
          closeGen(gen);
        }
      };
      setOpts({ ...o, onConfirm: wrapped });
    },
    [closeGen],
  );

  const confirmDialog = opts ? (
    <ConfirmDialog {...opts} open onClose={() => closeGen(genRef.current)} />
  ) : null;
  return { confirm, confirmDialog };
}
