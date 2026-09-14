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
      background: isDark ? '#111b2e' : '#ffffff',
      border: isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.08)',
      borderRadius: 10,
      color: isDark ? '#e8ecf4' : '#1a1d26',
      fontSize: 13,
      boxShadow: isDark ? '0 8px 32px rgba(0,0,0,0.4)' : '0 8px 32px rgba(0,0,0,0.08)',
    },
    tick: isDark ? '#5a6478' : '#8b95a8',
    grid: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.05)',
    accent: isDark ? '#00d4aa' : '#00b894',
    isDark,
  }
}
