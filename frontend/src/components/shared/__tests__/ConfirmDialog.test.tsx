import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { useConfirm, type ConfirmOptions } from '../ConfirmDialog';

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
    open();
    fireEvent.keyDown(document.activeElement as Element, { key: 'Escape' });
    expect(onConfirm).not.toHaveBeenCalled();
    expect(screen.queryByRole('alertdialog')).toBeNull();
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

  it('unmount while pending does not warn', async () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const d = deferred();
    const { unmount } = render(<Harness opts={{ onConfirm: () => d.promise }} />);
    open();
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    unmount();
    await act(async () => {
      d.resolve();
    });
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
