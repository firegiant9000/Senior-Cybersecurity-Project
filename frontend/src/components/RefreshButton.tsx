import React, { useEffect, useRef, useState } from 'react'
import type { ProgressItem } from '../hooks/useRefreshProgress'
import './RefreshButton.css'

interface RefreshButtonProps {
  onClick: () => void
  loading?: boolean
  disabled?: boolean
  items?: ProgressItem[]
  progress?: number
  label?: string
  title?: string
}

/**
 * Refresh button with hover progress indicator.
 * Shows individual item progress when hovered during a refresh operation.
 *
 * Usage:
 *   <RefreshButton
 *     onClick={refresh}
 *     loading={loading}
 *     items={progressItems}
 *     progress={progressPercent}
 *     label="Refresh"
 *   />
 */
export const RefreshButton: React.FC<RefreshButtonProps> = ({
  onClick,
  loading = false,
  disabled = false,
  items = [],
  progress = 0,
  label = 'Refresh',
  title,
}) => {
  const [isHovering, setIsHovering] = useState(false)
  const [isLingering, setIsLingering] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const lingerTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (items.length === 0) {
      setIsLingering(false)
      if (lingerTimeoutRef.current) {
        clearTimeout(lingerTimeoutRef.current)
        lingerTimeoutRef.current = null
      }
    }
  }, [items.length])

  useEffect(() => {
    return () => {
      if (lingerTimeoutRef.current) {
        clearTimeout(lingerTimeoutRef.current)
      }
    }
  }, [])

  const handleMouseEnter = () => {
    if (lingerTimeoutRef.current) {
      clearTimeout(lingerTimeoutRef.current)
      lingerTimeoutRef.current = null
    }
    setIsLingering(false)
    setIsHovering(true)
  }

  const handleMouseLeave = () => {
    setIsHovering(false)
    if (items.length === 0) return

    setIsLingering(true)
    if (lingerTimeoutRef.current) {
      clearTimeout(lingerTimeoutRef.current)
    }
    lingerTimeoutRef.current = setTimeout(() => {
      setIsLingering(false)
      lingerTimeoutRef.current = null
    }, 3000)
  }

  const showProgress = items.length > 0 && (isHovering || isLingering)

  return (
    <div
      ref={containerRef}
      className="refresh-button-container"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <button
        className="overview-refresh-btn"
        onClick={onClick}
        disabled={disabled || loading}
        title={title || `${label} dashboard data`}
        aria-label={`${label} dashboard data`}
      >
        ↻ <span className="refresh-btn-label">{label}</span>
      </button>

      {showProgress && (
        <div
          ref={tooltipRef}
          className="refresh-progress-tooltip"
          role="status"
          aria-live="polite"
          aria-label={`Refresh progress: ${progress}%`}
        >
          {/* Progress bar */}
          <div className="progress-bar-container">
            <div className="progress-bar-background">
              <div
                className="progress-bar-fill"
                style={{ width: `${progress}%` }}
                aria-valuenow={progress}
                aria-valuemin={0}
                aria-valuemax={100}
              />
            </div>
            <span className="progress-percentage">{progress}%</span>
          </div>

          {/* Items list */}
          <div className="progress-items-list">
            {items.map((item, idx) => (
              <div
                key={`${item.name}-${idx}`}
                className={`progress-item ${item.completed ? 'completed' : 'pending'}`}
              >
                <span className="progress-item-icon">
                  {item.completed ? '✓' : '⏳'}
                </span>
                <span className="progress-item-name">{item.name}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default RefreshButton
