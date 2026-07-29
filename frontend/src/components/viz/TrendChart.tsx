import Chart from 'react-apexcharts'
import type { ApexOptions } from 'apexcharts'

// Cockpit "Findings Trend" as an ApexCharts area spark. Themed from the CSS tokens so it tracks
// light/dark. Lazy loaded (apexcharts is heavy) so it stays off the initial bundle.
export default function TrendChart({ data }: { data: { month: string; open: number }[] }) {
  const css = getComputedStyle(document.documentElement)
  const accent = css.getPropertyValue('--color-accent').trim() || '#F26A43'
  const ink = css.getPropertyValue('--color-ink-muted').trim() || '#959E8C'

  const options: ApexOptions = {
    chart: { type: 'area', sparkline: { enabled: true }, parentHeightOffset: 0, animations: { enabled: true, speed: 700, easing: 'easeout' } },
    colors: [accent],
    stroke: { curve: 'smooth', width: 2.5 },
    fill: { type: 'gradient', gradient: { shadeIntensity: 0.4, opacityFrom: 0.32, opacityTo: 0, stops: [0, 100] } },
    dataLabels: { enabled: false },
    grid: { padding: { top: 6, bottom: 0, left: 4, right: 4 } },
    xaxis: { categories: data.map((d) => d.month), crosshairs: { show: true, stroke: { color: ink, width: 1, dashArray: 3 } } },
    tooltip: {
      theme: 'dark',
      x: { show: true },
      y: { formatter: (v) => `${v} open`, title: { formatter: () => '' } },
      marker: { show: false },
    },
    markers: { hover: { size: 5 } },
  }
  const series = [{ name: 'Open findings', data: data.map((d) => d.open) }]

  return <Chart type="area" height={168} options={options} series={series} />
}
