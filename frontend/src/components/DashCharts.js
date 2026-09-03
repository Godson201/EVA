import React from 'react';

export function BarChart({ data, color = 'var(--d-primary)', height = 140 }) {
  const max = Math.max(...data, 1);
  const barW = 10;
  const gap = 8;
  const width = Math.max(data.length * (barW + gap), barW);

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="dash-bar-chart" preserveAspectRatio="none">
      {data.map((v, i) => {
        const h = v > 0 ? Math.max((v / max) * (height - 6), 3) : 0;
        const x = i * (barW + gap);
        const y = height - h;
        return <rect key={i} x={x} y={y} width={barW} height={h} rx={3} fill={color} />;
      })}
    </svg>
  );
}

export function DonutChart({ segments, size = 130, thickness = 16, centerLabel, centerSub }) {
  const total = segments.reduce((sum, seg) => sum + seg.value, 0) || 1;
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;
  let acc = 0;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="dash-donut-svg">
      <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--d-border)" strokeWidth={thickness} />
        {segments.filter(seg => seg.value > 0).map((seg, i) => {
          const frac = seg.value / total;
          const dash = frac * c;
          const dashOffset = -acc * c;
          acc += frac;
          return (
            <circle
              key={i}
              cx={size / 2}
              cy={size / 2}
              r={r}
              fill="none"
              stroke={seg.color}
              strokeWidth={thickness}
              strokeDasharray={`${dash} ${c - dash}`}
              strokeDashoffset={dashOffset}
            />
          );
        })}
      </g>
      {centerLabel && (
        <text x="50%" y="47%" textAnchor="middle" className="dash-donut-total">{centerLabel}</text>
      )}
      {centerSub && (
        <text x="50%" y="62%" textAnchor="middle" className="dash-donut-total-label">{centerSub}</text>
      )}
    </svg>
  );
}
