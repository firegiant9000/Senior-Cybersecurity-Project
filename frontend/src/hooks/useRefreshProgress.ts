import { useState, useCallback, useEffect, useRef } from 'react'

export interface ProgressItem {
  name: string
  completed: boolean
}

export interface UseRefreshProgressResult {
  items: ProgressItem[]
  progress: number // 0-100
  isActive: boolean // true if refresh is in progress
  markItemComplete: (itemName: string) => void
  reset: () => void
  start: (itemNames: string[]) => void
}

/**
 * Hook to track progress of multiple async items completing.
 * Useful for showing progress on refresh buttons.
 *
 * Usage:
 *   const progress = useRefreshProgress();
 *   // Start tracking
 *   progress.start(['Item 1', 'Item 2', 'Item 3']);
 *   // Mark items complete as they resolve
 *   fetchData().then(() => progress.markItemComplete('Item 1'));
 *   // Progress is automatically calculated
 */
export function useRefreshProgress(): UseRefreshProgressResult {
  const [items, setItems] = useState<ProgressItem[]>([])
  const [isActive, setIsActive] = useState(false)
  const resetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearResetTimer = useCallback(() => {
    if (resetTimerRef.current !== null) {
      clearTimeout(resetTimerRef.current)
      resetTimerRef.current = null
    }
  }, [])

  const reset = useCallback(() => {
    clearResetTimer()
    setItems([])
    setIsActive(false)
  }, [clearResetTimer])

  const start = useCallback((itemNames: string[]) => {
    clearResetTimer()
    setItems(itemNames.map(name => ({ name, completed: false })))
    setIsActive(true)
  }, [clearResetTimer])

  const markItemComplete = useCallback((itemName: string) => {
    setItems(prev => {
      const updated = prev.map(item =>
        item.name === itemName ? { ...item, completed: true } : item
      )

      const allComplete = updated.every(item => item.completed)
      if (allComplete) {
        // Brief delay so users see 100% before the bar disappears.
        clearResetTimer()
        resetTimerRef.current = setTimeout(() => {
          resetTimerRef.current = null
          reset()
        }, 300)
      }

      return updated
    })
  }, [reset, clearResetTimer])

  useEffect(() => clearResetTimer, [clearResetTimer])

  const progress = items.length === 0 
    ? 0 
    : Math.round((items.filter(item => item.completed).length / items.length) * 100)

  return {
    items,
    progress,
    isActive,
    markItemComplete,
    reset,
    start,
  }
}
