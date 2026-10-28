// a four-point star drawn like a pencil study: graphite outline, hatched shading, red-pencil centre
export default function Sparkle({ size = 120 }: { size?: number }) {
  const hatch = Array.from({ length: 14 }, (_, i) => 20 + i * 6)
  return (
    <svg width={size} height={size} viewBox="0 0 120 120" aria-hidden>
      <defs>
        <clipPath id="sk-star">
          <path d="M60 6 C63 45 75 57 114 60 C75 63 63 75 60 114 C57 75 45 63 6 60 C45 57 57 45 60 6 Z" />
        </clipPath>
        <radialGradient id="sk-shade" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#26241f" stopOpacity="0.05" />
          <stop offset="100%" stopColor="#26241f" stopOpacity="0.28" />
        </radialGradient>
      </defs>
      <path d="M60 6 C63 45 75 57 114 60 C75 63 63 75 60 114 C57 75 45 63 6 60 C45 57 57 45 60 6 Z" fill="url(#sk-shade)" />
      <g clipPath="url(#sk-star)" stroke="#3d3a34" strokeWidth="0.7" opacity="0.55">
        {hatch.map((x) => (
          <line key={x} x1={x - 30} y1="120" x2={x + 30} y2="0" />
        ))}
      </g>
      <path
        d="M60 6 C63 45 75 57 114 60 C75 63 63 75 60 114 C57 75 45 63 6 60 C45 57 57 45 60 6 Z"
        fill="none"
        stroke="#26241f"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M60 10 C62.5 46 74 58 110 60.5" fill="none" stroke="#26241f" strokeWidth="0.8" opacity="0.5" />
      <circle cx="60" cy="60" r="6" fill="#b0442c" />
      <circle cx="60" cy="60" r="6" fill="none" stroke="#26241f" strokeWidth="1" opacity="0.6" />
    </svg>
  )
}
