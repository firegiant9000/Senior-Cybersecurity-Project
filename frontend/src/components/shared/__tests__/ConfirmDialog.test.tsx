import { useState } from 'react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import ConfirmDialog, { useConfirm, type ConfirmOptions } from '../ConfirmDialog';

function Harness({ opts }: { opts: Partial<ConfirmOptions> & Pick<ConfirmOptions, 'onConfirm'> }) {
  const { confirm, confirmDialog } = useConfirm();
  return (
    <div>
      <button
        onClick={() =>
          confirm({ title: 'Delete it?', body: 'This cannot be undone.', confirmLabel: 'Delete', ...opts })
        }
      >
        Open
      </button>
      <button
        onClick={() =>
          confirm({ title: 'Second dialog', body: 'Other', confirmLabel: 'Go', onConfirm: opts.onConfirm })
        }
      >
        Open2
      </button>
      {confirmDialog}
    </div>
  );
}

function deferred() {
  let resolve!: () => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<void>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function open() {
  fireEvent.click(screen.getByRole('button', { name: 'Open' }));
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('ConfirmDialog / useConfirm', () => {
  it('opens with focus on Cancel', () => {
    render(<Harness opts={{ onConfirm: vi.fn().mockResolvedValue(undefined) }} />);
    screen.getByRole('button', { name: 'Open' }).focus();
    open();
    expect(screen.getByRole('alertdialog')).toBeInTheDocument();
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Cancel' }));
  });

  it('Cancel closes without calling onConfirm', () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    render(<Harness opts={{ onConfirm }} />);
    const openBtn = screen.getByRole('button', { name: 'Open' });
    openBtn.focus();
    open();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onConfirm).not.toHaveBeenCalled();
    expect(screen.queryByRole('alertdialog')).toBeNull();
    expect(document.activeElement).toBe(openBtn);
  });

  it('Escape closes without calling onConfirm', () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    render(<Harness opts={{ onConfirm }} />);
    const openBtn = screen.getByRole('button', { name: 'Open' });
    openBtn.focus();
    open();
    fireEvent.keyDown(document.activeElement as Element, { key: 'Escape' });
    expect(onConfirm).not.toHaveBeenCalled();
    expect(screen.queryByRole('alertdialog')).toBeNull();
    expect(document.activeElement).toBe(openBtn);
  });

  it('Tab from outside the dialog focuses Cancel', () => {
    render(<Harness opts={{ onConfirm: vi.fn().mockResolvedValue(undefined) }} />);
    open();
    (document.activeElement as HTMLElement).blur();
    expect(document.activeElement).toBe(document.body);
    fireEvent.keyDown(document.body, { key: 'Tab' });
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Cancel' }));
    (document.activeElement as HTMLElement).blur();
    fireEvent.keyDown(document.body, { key: 'Tab', shiftKey: true });
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Cancel' }));
  });

  it('confirm() while open is a no-op and keeps the focus-return target', () => {
    render(<Harness opts={{ onConfirm: vi.fn().mockResolvedValue(undefined) }} />);
    const openBtn = screen.getByRole('button', { name: 'Open' });
    openBtn.focus();
    open();
    fireEvent.click(screen.getByRole('button', { name: 'Open2' }));
    expect(screen.getByText('Delete it?')).toBeInTheDocument();
    expect(screen.queryByText('Second dialog')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(document.activeElement).toBe(openBtn);
  });

  it('Tab cycles inside the dialog', () => {
    render(<Harness opts={{ onConfirm: vi.fn().mockResolvedValue(undefined) }} />);
    open();
    const cancel = screen.getByRole('button', { name: 'Cancel' });
    const confirmBtn = screen.getByRole('button', { name: 'Delete' });
    confirmBtn.focus();
    fireEvent.keyDown(confirmBtn, { key: 'Tab' });
    expect(document.activeElement).toBe(cancel);
    fireEvent.keyDown(cancel, { key: 'Tab', shiftKey: true });
    expect(document.activeElement).toBe(confirmBtn);
  });

  it('Confirm awaits onConfirm then closes', async () => {
    const d = deferred();
    const onConfirm = vi.fn(() => d.promise);
    render(<Harness opts={{ onConfirm }} />);
    const openBtn = screen.getByRole('button', { name: 'Open' });
    openBtn.focus();
    open();
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    const working = screen.getByRole('button', { name: 'Working…' });
    expect(working).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled();
    expect(screen.getByRole('alertdialog')).toHaveAttribute('aria-busy', 'true');
    await act(async () => {
      d.resolve();
    });
    expect(screen.queryByRole('alertdialog')).toBeNull();
    expect(document.activeElement).toBe(openBtn);
  });

  it('double click calls onConfirm once', async () => {
    const d = deferred();
    const onConfirm = vi.fn(() => d.promise);
    render(<Harness opts={{ onConfirm }} />);
    open();
    const btn = screen.getByRole('button', { name: 'Delete' });
    fireEvent.click(btn);
    fireEvent.click(btn);
    expect(onConfirm).toHaveBeenCalledTimes(1);
    await act(async () => {
      d.resolve();
    });
  });

  it('Escape while busy does nothing', async () => {
    const d = deferred();
    render(<Harness opts={{ onConfirm: () => d.promise }} />);
    open();
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    fireEvent.keyDown(document.body, { key: 'Escape' });
    expect(screen.getByRole('alertdialog')).toBeInTheDocument();
    await act(async () => {
      d.resolve();
    });
  });

  it('rejection closes the dialog and does not throw', async () => {
    const d = deferred();
    render(<Harness opts={{ onConfirm: () => d.promise }} />);
    open();
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    await act(async () => {
      d.reject(new Error('boom'));
    });
    expect(screen.queryByRole('alertdialog')).toBeNull();
  });

  it('closes even if the host hides the dialog while the action is pending', async () => {
    const d = deferred();
    function HidingHarness() {
      const { confirm, confirmDialog } = useConfirm();
      const [hidden, setHidden] = useState(false);
      return (
        <div>
          <button
            onClick={() =>
              confirm({
                title: 'Delete it?',
                body: 'Body',
                confirmLabel: 'Delete',
                onConfirm: () => d.promise,
              })
            }
          >
            Open
          </button>
          <button onClick={() => setHidden((h) => !h)}>Toggle</button>
          {!hidden && confirmDialog}
        </div>
      );
    }
    render(<HidingHarness />);
    open();
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    fireEvent.click(screen.getByRole('button', { name: 'Toggle' }));
    expect(screen.queryByRole('alertdialog')).toBeNull();
    await act(async () => {
      d.resolve();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Toggle' }));
    expect(screen.queryByRole('alertdialog')).toBeNull();
    open();
    expect(screen.getByRole('alertdialog')).toBeInTheDocument();
  });

  it('ConfirmDialog does not call onClose after unmount while pending', async () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const onClose = vi.fn();
    const d = deferred();
    const { unmount } = render(
      <ConfirmDialog open onClose={onClose} title="T" body="B" confirmLabel="Go" onConfirm={() => d.promise} />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Go' }));
    unmount();
    await act(async () => {
      d.resolve();
    });
    expect(onClose).not.toHaveBeenCalled();
    expect(spy).not.toHaveBeenCalled();
  });

  it('cancelLabel replaces the dismiss text', () => {
    render(
      <Harness opts={{ cancelLabel: 'Keep running', onConfirm: vi.fn().mockResolvedValue(undefined) }} />,
    );
    open();
    expect(screen.getByRole('button', { name: 'Keep running' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Cancel' })).toBeNull();
  });
});
