import { useState, useEffect, useCallback } from 'react';

interface Prefs {
    hidden: string[];
    gridOrder: string[];
}

// Curated demo default: Overview shows only the narrative-critical widgets out of the box.
// executiveSummary + vendorAlerts are non-moveable but still toggleable via the Customize
// panel; alongside the four moveable defaults (cyberMap, projectedLoss, avgRiskScore,
// criticalRiskCves) they form the six widgets visible on a fresh login. Users can toggle
// other widgets back on from the Customize panel; existing localStorage prefs are preserved.
const DEFAULT_HIDDEN = [
    'malwareChart', 'totalAttempts', 'totalLosses', 'progression',
    'avgLoss', 'cvesExploited', 'attackTypeCount', 'stateCount',
    'totalCves', 'ic3Anomalies', 'escalatingSectors',
    'incidentMgmt', 'cyberRisks', 'heatmap',
    'lossAttack', 'avgLossSector', 'complaintsSector', 'sectorTable',
];

function defaultPrefs(allIds: string[], moveableIds: string[]): Prefs {
    return {
        hidden: DEFAULT_HIDDEN.filter((id) => allIds.includes(id)),
        gridOrder: [...moveableIds],
    };
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
    return defaultPrefs(allIds, moveableIds);
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
        setPrefs(defaultPrefs(allIds, moveableIds));
    }, [allIds, moveableIds]);

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
