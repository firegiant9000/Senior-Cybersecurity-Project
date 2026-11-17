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
  /**
   * Where focus goes after a confirmed action when the trigger is gone or
   * disabled (the row was removed, the list reloaded). Called once, after
   * the render that follows onConfirm settling, so await any reload inside
   * onConfirm. Not called on Cancel/Escape.
   */
  returnFocus?: () => HTMLElement | null | Promise<HTMLElement | null>;
}

interface ConfirmDialogProps extends Omit<ConfirmOptions, 'returnFocus'> {
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

interface PendingFocus {
  trigger: HTMLElement | null;
  returnFocus: ConfirmOptions['returnFocus'];
}

// Focus left the closed dialog for <body>; anything else means the user (or
// the caller) already put it somewhere on purpose.
function focusIsFree(): boolean {
  const active = document.activeElement;
  return !active || active === document.body || !active.isConnected;
}

function usable(el: HTMLElement | null | undefined): el is HTMLElement {
  return !!el && el.isConnected && !el.matches(':disabled');
}

async function restoreFocus(req: PendingFocus, hostMounted: () => boolean): Promise<void> {
  if (!hostMounted() || !focusIsFree()) return;
  if (usable(req.trigger)) {
    req.trigger.focus();
    return;
  }
  if (!req.returnFocus) return;
  let target: HTMLElement | null;
  try {
    target = await req.returnFocus();
  } catch {
    return;
  }
  if (!hostMounted() || !focusIsFree()) return;
  if (usable(target)) target.focus();
}

export function useConfirm(): {
  confirm: (opts: ConfirmOptions) => void;
  confirmDialog: ReactNode;
} {
  const [opts, setOpts] = useState<Omit<ConfirmOptions, 'returnFocus'> | null>(null);
  const triggerRef = useRef<HTMLElement | null>(null);
  const returnFocusOptRef = useRef<ConfirmOptions['returnFocus']>(undefined);

  const openRef = useRef(false);
  const genRef = useRef(0);
  const hostMountedRef = useRef(true);

  // Focus is restored in an effect, after the commit that closes the dialog,
  // so a list the caller reloaded inside onConfirm is already in the DOM.
  const pendingFocusRef = useRef<PendingFocus | null>(null);
  const [focusTick, setFocusTick] = useState(0);

  useEffect(() => {
    hostMountedRef.current = true;
    return () => {
      hostMountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    const req = pendingFocusRef.current;
    pendingFocusRef.current = null;
    if (req) void restoreFocus(req, () => hostMountedRef.current);
  }, [focusTick]);

  const closeGen = useCallback((gen: number, confirmed = false) => {
    if (gen !== genRef.current || !openRef.current) return;
    openRef.current = false;
    const req: PendingFocus = {
      trigger: triggerRef.current,
      returnFocus: confirmed ? returnFocusOptRef.current : undefined,
    };
    triggerRef.current = null;
    returnFocusOptRef.current = undefined;
    if (!hostMountedRef.current) return;
    pendingFocusRef.current = req;
    setOpts(null);
    setFocusTick((t) => t + 1);
  }, []);

  const confirm = useCallback(
    (o: ConfirmOptions) => {
      if (openRef.current) return;
      openRef.current = true;
      genRef.current += 1;
      const gen = genRef.current;
      const active = document.activeElement;
      triggerRef.current = active instanceof HTMLElement && active !== document.body ? active : null;
      const { returnFocus, ...dialogOpts } = o;
      returnFocusOptRef.current = returnFocus;
      // Close in the hook's own finally so it happens even if the dialog
      // component is unmounted while the action is pending.
      const wrapped = async () => {
        try {
          await o.onConfirm();
        } finally {
          closeGen(gen, true);
        }
      };
      setOpts({ ...dialogOpts, onConfirm: wrapped });
    },
    [closeGen],
  );

  const confirmDialog = opts ? (
    <ConfirmDialog {...opts} open onClose={() => closeGen(genRef.current)} />
  ) : null;
  return { confirm, confirmDialog };
}
