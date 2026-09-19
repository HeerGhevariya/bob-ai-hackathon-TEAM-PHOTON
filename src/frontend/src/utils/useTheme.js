import { useState, useEffect } from 'react'

/**
 * Returns the current theme ('light' or 'dark') and re-renders on changes.
 * Used by chart components to adapt colors dynamically.
 */
export function useTheme() {
  const [theme, setTheme] = useState(() => {
    return document.documentElement.getAttribute('data-theme') || 'light'
  })

  useEffect(() => {
    const observer = new MutationObserver(() => {
      const t = document.documentElement.getAttribute('data-theme') || 'light'
      setTheme(t)
    })
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => observer.disconnect()
  }, [])

  return theme
}

/**
 * Returns chart-friendly styling object for the current theme.
 */
export function useChartTheme() {
  const theme = useTheme()
  const isDark = theme === 'dark'

  return {
    tooltip: {
      background: isDark ? '#131e30' : '#ffffff',
      border: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.07)'}`,
      borderRadius: 8,
      color: isDark ? '#e8ecf4' : '#111827',
      fontSize: 12.5,
      boxShadow: isDark
        ? '0 8px 32px rgba(0,0,0,0.45)'
        : '0 8px 24px rgba(0,0,0,0.08)',
      padding: '8px 12px',
    },
    tick: isDark ? '#4e5a6e' : '#9ca3af',
    grid: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)',
    accent: isDark ? '#00d4aa' : '#00b894',
    isDark,
  }
}
