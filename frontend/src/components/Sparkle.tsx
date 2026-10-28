// the soft four-point star from the home screen; pure SVG so it scales cleanly
export default function Sparkle({ size = 120 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 120 120" aria-hidden className="drop-shadow-[0_10px_30px_rgba(240,150,110,0.35)]">
      <defs>
        <radialGradient id="sp-core" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#ffd2b8" />
          <stop offset="45%" stopColor="#f2a27c" />
          <stop offset="100%" stopColor="#b9a8e8" stopOpacity="0.35" />
        </radialGradient>
        <linearGradient id="sp-ray" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#c9b8f0" />
          <stop offset="100%" stopColor="#f4b59a" />
        </linearGradient>
      </defs>
      <path d="M60 4 C64 44 76 56 116 60 C76 64 64 76 60 116 C56 76 44 64 4 60 C44 56 56 44 60 4 Z" fill="url(#sp-ray)" opacity="0.55" />
      <path d="M60 24 C62 48 72 58 96 60 C72 62 62 72 60 96 C58 72 48 62 24 60 C48 58 58 48 60 24 Z" fill="url(#sp-core)" transform="rotate(45 60 60)" opacity="0.8" />
      <circle cx="60" cy="60" r="9" fill="#fff" opacity="0.9" />
    </svg>
  )
}
