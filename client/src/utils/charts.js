import {
  ArcElement, BarElement, CategoryScale, Chart as ChartJS, Filler, Legend, LinearScale, LineElement,
  PointElement, Tooltip,
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, BarElement, PointElement, LineElement, ArcElement, Filler, Tooltip, Legend)

const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim()

// Apply the design-system font and theme colours to every chart. Called on
// load and whenever the light/dark theme changes.
export function applyChartTheme() {
  ChartJS.defaults.font.family = "'Inter Variable', 'Inter', system-ui, sans-serif"
  ChartJS.defaults.font.size = 12
  ChartJS.defaults.color = css('--muted') || '#64748b'
  ChartJS.defaults.borderColor = css('--chart-grid') || 'rgba(100,116,139,.14)'
  ChartJS.defaults.maintainAspectRatio = false
  ChartJS.defaults.plugins.tooltip.backgroundColor = '#0f172a'
  ChartJS.defaults.plugins.tooltip.padding = 10
  ChartJS.defaults.plugins.tooltip.cornerRadius = 10
  ChartJS.defaults.plugins.tooltip.titleFont = { weight: '600' }
  ChartJS.defaults.plugins.legend.labels.usePointStyle = true
  ChartJS.defaults.plugins.legend.labels.boxWidth = 8
}
applyChartTheme()
if (typeof window !== 'undefined') window.addEventListener('themechange', applyChartTheme)

export const PALETTE = {
  indigo: '#6366f1', violet: '#8b5cf6', green: '#10b981', amber: '#f59e0b', red: '#ef4444', sky: '#0ea5e9',
  slate: '#94a3b8', pink: '#ec4899',
}

// Vertical gradient fill for line/area charts.
export function areaGradient(color) {
  return (ctx) => {
    const { chart } = ctx
    const { ctx: c, chartArea } = chart
    if (!chartArea) return `${color}33`
    const g = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom)
    g.addColorStop(0, `${color}55`)
    g.addColorStop(1, `${color}00`)
    return g
  }
}

export const bandColor = (pct) => (pct >= 70 ? PALETTE.green : pct >= 40 ? PALETTE.amber : PALETTE.red)
