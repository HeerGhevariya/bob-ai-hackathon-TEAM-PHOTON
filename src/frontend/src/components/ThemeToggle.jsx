import { useState, useEffect } from 'react'
import { Moon, Sun } from 'lucide-react'

export default function ThemeToggle() {
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('tg-theme') || 'light'
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('tg-theme', theme)
  }, [theme])

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light')
  }

  return (
    <button
      className="theme-toggle"
      onClick={toggleTheme}
      title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
      aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
    >
      <span className="theme-toggle-icon">
        {theme === 'light' ? <Moon size={15} /> : <Sun size={15} />}
      </span>
      {theme === 'light' ? 'Dark Mode' : 'Light Mode'}
    </button>
  )
}
