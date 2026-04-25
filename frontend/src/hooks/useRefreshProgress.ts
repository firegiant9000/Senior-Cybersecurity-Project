import { useState, useCallback, useEffect } from 'react'

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

  const reset = useCallback(() => {
    setItems([])
    setIsActive(false)
  }, [])

  const start = useCallback((itemNames: string[]) => {
    setItems(itemNames.map(name => ({ name, completed: false })))
    setIsActive(true)
  }, [])

  const markItemComplete = useCallback((itemName: string) => {
    setItems(prev => {
      const updated = prev.map(item =>
        item.name === itemName ? { ...item, completed: true } : item
      )
      
      // Auto-reset when all items are complete
      const allComplete = updated.every(item => item.completed)
      if (allComplete) {
        // Small delay to show 100% before resetting
        setTimeout(() => reset(), 300)
      }
      
      return updated
    })
  }, [reset])

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
