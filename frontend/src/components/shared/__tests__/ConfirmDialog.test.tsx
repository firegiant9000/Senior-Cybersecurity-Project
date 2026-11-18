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

  describe('returnFocus', () => {
    // A list that reloads through a loading placeholder, like the settings tables.
    function ListHarness({
      remove,
      disableWhileBusy = false,
      asyncTarget = false,
    }: {
      remove: (id: number) => Promise<void>;
      disableWhileBusy?: boolean;
      asyncTarget?: boolean;
    }) {
      const { confirm, confirmDialog } = useConfirm();
      const [items, setItems] = useState([1, 2, 3]);
      const [loading, setLoading] = useState(false);
      const [busy, setBusy] = useState(false);
      const run = async (id: number) => {
        setBusy(true);
        try {
          await remove(id);
          setLoading(true);
          await Promise.resolve();
          setItems((xs) => xs.filter((x) => x !== id));
          setLoading(false);
        } catch {
          // caller-owned error state
        } finally {
          setBusy(false);
        }
      };
      return (
        <div>
          <h2 tabIndex={-1}>Items</h2>
          <button>Elsewhere</button>
          {loading ? (
            <p>Loading…</p>
          ) : (
            <ul>
              {items.map((id) => (
                <li key={id} data-row-id={id}>
                  <button
                    data-action="remove"
                    disabled={disableWhileBusy && busy}
                    onClick={() =>
                      confirm({
                        title: `Remove ${id}?`,
                        body: 'Body',
                        confirmLabel: 'Remove',
                        onConfirm: () => run(id),
                        returnFocus: () => {
                          const el = document.querySelector<HTMLElement>(
                            `[data-row-id="${id === 3 ? 2 : id + 1}"] button`,
                          );
                          return asyncTarget ? Promise.resolve(el) : el;
                        },
                      })
                    }
                  >
                    Remove {id}
                  </button>
                </li>
              ))}
            </ul>
          )}
          {confirmDialog}
        </div>
      );
    }

    async function removeVia(name: string) {
      const btn = screen.getByRole('button', { name });
      btn.focus();
      fireEvent.click(btn);
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: 'Remove' }));
      });
    }

    it('focuses the returnFocus target once the reloaded list has rendered', async () => {
      render(<ListHarness remove={vi.fn().mockResolvedValue(undefined)} />);
      await removeVia('Remove 1');
      expect(screen.queryByRole('button', { name: 'Remove 1' })).toBeNull();
      expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Remove 2' }));
    });

    it('awaits an async returnFocus', async () => {
      render(<ListHarness remove={vi.fn().mockResolvedValue(undefined)} asyncTarget />);
      await removeVia('Remove 3');
      expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Remove 2' }));
    });

    it('returns to the re-enabled trigger when the action fails', async () => {
      render(<ListHarness remove={vi.fn().mockRejectedValue(new Error('nope'))} disableWhileBusy />);
      await removeVia('Remove 2');
      expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Remove 2' }));
    });

    it('uses returnFocus when the trigger is still there but disabled', async () => {
      const target = vi.fn(() => screen.getByRole('heading', { name: 'Items' }));
      function DisabledHarness() {
        const { confirm, confirmDialog } = useConfirm();
        const [done, setDone] = useState(false);
        return (
          <div>
            <h2 tabIndex={-1}>Items</h2>
            <button
              disabled={done}
              onClick={() =>
                confirm({
                  title: 'T',
                  body: 'B',
                  confirmLabel: 'Go',
                  onConfirm: async () => setDone(true),
                  returnFocus: target,
                })
              }
            >
              Trigger
            </button>
            {confirmDialog}
          </div>
        );
      }
      render(<DisabledHarness />);
      const trigger = screen.getByRole('button', { name: 'Trigger' });
      trigger.focus();
      fireEvent.click(trigger);
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: 'Go' }));
      });
      expect(target).toHaveBeenCalledTimes(1);
      expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Items' }));
    });

    it('does not call returnFocus on Cancel', () => {
      const target = vi.fn(() => null);
      render(<Harness opts={{ onConfirm: vi.fn().mockResolvedValue(undefined), returnFocus: target }} />);
      open();
      fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
      expect(target).not.toHaveBeenCalled();
    });

    it('leaves focus alone if the user moved it while the action was pending', async () => {
      const d = deferred();
      render(<ListHarness remove={() => d.promise} />);
      const btn = screen.getByRole('button', { name: 'Remove 1' });
      btn.focus();
      fireEvent.click(btn);
      fireEvent.click(screen.getByRole('button', { name: 'Remove' }));
      const elsewhere = screen.getByRole('button', { name: 'Elsewhere' });
      elsewhere.focus();
      await act(async () => {
        d.resolve();
      });
      expect(document.activeElement).toBe(elsewhere);
    });

    it('does nothing if the host unmounts while the action is pending', async () => {
      const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const d = deferred();
      const target = vi.fn(() => null);
      const { unmount } = render(<Harness opts={{ onConfirm: () => d.promise, returnFocus: target }} />);
      open();
      fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
      unmount();
      await act(async () => {
        d.resolve();
      });
      expect(target).not.toHaveBeenCalled();
      expect(spy).not.toHaveBeenCalled();
    });
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
