import { describe, it, expect, beforeEach } from 'vitest';
import { findRowAction, focusOrder } from '../focusAfterRemoval';

describe('focusOrder', () => {
  it('lists the row itself, later ids in order, then earlier ids nearest first', () => {
    expect(focusOrder([1, 2, 3, 4, 5], 3)).toEqual([3, 4, 5, 2, 1]);
  });

  it('handles the first and last positions', () => {
    expect(focusOrder(['a', 'b', 'c'], 'a')).toEqual(['a', 'b', 'c']);
    expect(focusOrder(['a', 'b', 'c'], 'c')).toEqual(['c', 'b', 'a']);
  });

  it('returns just the id when it is not in the list', () => {
    expect(focusOrder([1, 2], 9)).toEqual([9]);
  });
});

describe('findRowAction', () => {
  let root: HTMLElement;

  beforeEach(() => {
    document.body.innerHTML = `
      <table id="t"><tbody>
        <tr data-row-id="1"><td><button data-action="remove">r1</button></td></tr>
        <tr data-row-id="2"><td>owner, no button</td></tr>
        <tr data-row-id="3"><td><button data-action="remove" disabled>r3</button></td></tr>
        <tr data-row-id="4"><td><button data-action="rotate">x4</button><button data-action="remove">r4</button></td></tr>
      </tbody></table>
      <div data-row-id="9"><button data-action="remove">outside</button></div>`;
    root = document.getElementById('t')!;
  });

  it('returns the first row in id order that has an enabled matching action', () => {
    expect(findRowAction(root, [2, 3, 4, 1], 'remove')?.textContent).toBe('r4');
  });

  it('matches ids given as numbers or strings', () => {
    expect(findRowAction(root, ['1'], 'remove')?.textContent).toBe('r1');
  });

  it('only searches inside root', () => {
    expect(findRowAction(root, [1], 'remove')?.textContent).toBe('r1');
    expect(findRowAction(root, [9], 'remove')).toBeNull();
  });

  it('returns null for a missing root, no ids, or no matching action', () => {
    expect(findRowAction(null, [1], 'remove')).toBeNull();
    expect(findRowAction(root, [], 'remove')).toBeNull();
    expect(findRowAction(root, [1, 4], 'revoke')).toBeNull();
  });
});
