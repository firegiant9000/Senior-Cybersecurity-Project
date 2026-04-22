import { useState, useEffect, useCallback } from 'react';

interface Prefs {
    hidden: string[];
    gridOrder: string[];
}

function loadPrefs(allIds: string[], moveableIds: string[], storageKey: string): Prefs {
    try {
        const raw = localStorage.getItem(storageKey);
        if (raw) {
            const parsed = JSON.parse(raw) as Partial<Prefs>;
            const hidden = Array.isArray(parsed.hidden)
                ? parsed.hidden.filter((id) => allIds.includes(id))
                : [];
            const storedOrder = Array.isArray(parsed.gridOrder) ? parsed.gridOrder : [];
            const moveableSet = new Set(moveableIds);
            const orderedKnown = storedOrder.filter((id) => moveableSet.has(id));
            const orderedSet = new Set(orderedKnown);
            const newIds = moveableIds.filter((id) => !orderedSet.has(id));
            return { hidden, gridOrder: [...orderedKnown, ...newIds] };
        }
    } catch {
        // corrupted — fall through
    }
    return {
        hidden: [
            'ic3Anomalies', 'incidentMgmt', 'heatmap',
            'lossAttack', 'avgLossSector', 'complaintsSector', 'sectorTable',
            'attackTypeCount', 'stateCount',
        ].filter((id) => allIds.includes(id)),
        gridOrder: [...moveableIds],
    };
}

export function useWidgetPrefs(allIds: string[], moveableIds: string[], storageKey: string) {
    const [prefs, setPrefs] = useState<Prefs>(() => loadPrefs(allIds, moveableIds, storageKey));

    useEffect(() => {
        localStorage.setItem(storageKey, JSON.stringify(prefs));
    }, [prefs, storageKey]);

    const toggle = useCallback((id: string) => {
        setPrefs((prev) => ({
            ...prev,
            hidden: prev.hidden.includes(id)
                ? prev.hidden.filter((h) => h !== id)
                : [...prev.hidden, id],
        }));
    }, []);

    const move = useCallback((id: string, direction: 'up' | 'down') => {
        setPrefs((prev) => {
            const order = [...prev.gridOrder];
            const idx = order.indexOf(id);
            if (idx < 0) return prev;
            if (direction === 'up' && idx === 0) return prev;
            if (direction === 'down' && idx === order.length - 1) return prev;
            const swapIdx = direction === 'up' ? idx - 1 : idx + 1;
            [order[idx], order[swapIdx]] = [order[swapIdx], order[idx]];
            return { ...prev, gridOrder: order };
        });
    }, []);

    const reorder = useCallback((fromId: string, toId: string) => {
        setPrefs((prev) => {
            const order = [...prev.gridOrder];
            const fromIdx = order.indexOf(fromId);
            let toIdx = order.indexOf(toId);
            if (fromIdx < 0 || toIdx < 0 || fromIdx === toIdx) return prev;
            order.splice(fromIdx, 1);
            // Removing fromId shifts every element after it left by 1;
            // adjust toIdx so the insert still lands before toId.
            if (fromIdx < toIdx) toIdx--;
            order.splice(toIdx, 0, fromId);
            return { ...prev, gridOrder: order };
        });
    }, []);

    const insertAtEnd = useCallback((fromId: string) => {
        setPrefs((prev) => {
            const order = [...prev.gridOrder];
            const fromIdx = order.indexOf(fromId);
            if (fromIdx < 0) return prev;
            order.splice(fromIdx, 1);
            order.push(fromId);
            return { ...prev, gridOrder: order };
        });
    }, []);

    const reset = useCallback(() => {
        setPrefs({ hidden: [], gridOrder: [...moveableIds] });
    }, [moveableIds]);

    return {
        hiddenSet: new Set(prefs.hidden),
        gridOrder: prefs.gridOrder,
        toggle,
        move,
        reorder,
        insertAtEnd,
        reset,
    };
}
