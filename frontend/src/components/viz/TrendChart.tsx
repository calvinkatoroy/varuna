import Chart from 'react-apexcharts'
import type { ApexOptions } from 'apexcharts'

type Row = { month: string; critical: number; high: number; medium: number; low: number }

// Cockpit "Findings Trend" as a stacked-by-severity area (open findings over time). Themed from
// the CSS tokens so it tracks light/dark. Lazy loaded (apexcharts is heavy).
export default function TrendChart({ data }: { data: Row[] }) {
  const css = getComputedStyle(document.documentElement)
  const col = (v: string) => css.getPropertyValue(v).trim()
  const light = document.documentElement.getAttribute('data-theme') === 'light'

  const options: ApexOptions = {
    chart: { type: 'area', stacked: true, toolbar: { show: false }, parentHeightOffset: 0, animations: { enabled: true, speed: 700, easing: 'easeout' } },
    colors: [col('--color-crit'), col('--color-high'), col('--color-med'), col('--color-low')],
    stroke: { curve: 'smooth', width: 1.5 },
    fill: { type: 'gradient', gradient: { opacityFrom: 0.55, opacityTo: 0.12 } },
    dataLabels: { enabled: false },
    legend: { show: false },
    grid: { show: false, padding: { top: 0, bottom: 0, left: 2, right: 2 } },
    xaxis: {
      categories: data.map((d) => d.month),
      axisBorder: { show: false }, axisTicks: { show: false },
      labels: { style: { colors: col('--color-ink-faint'), fontFamily: 'inherit', fontSize: '12px' } },
    },
    yaxis: { show: false },
    tooltip: { theme: light ? 'light' : 'dark', y: { formatter: (v) => `${v} open` } },
  }
  const series = [
    { name: 'Critical', data: data.map((d) => d.critical) },
    { name: 'High', data: data.map((d) => d.high) },
    { name: 'Medium', data: data.map((d) => d.medium) },
    { name: 'Low', data: data.map((d) => d.low) },
  ]
  return <Chart type="area" height={214} options={options} series={series} />
}
