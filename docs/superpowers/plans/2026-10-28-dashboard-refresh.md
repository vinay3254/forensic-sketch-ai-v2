# SketchLab dashboard refresh

Use the Seto reference's light three-column workspace, rounded surfaces, centered welcome, quick actions, composer and history rail. Adapt to existing forensic case APIs. Keep current routes and access rules.

1. Refresh application shell with light navigation, responsive mobile drawer, user menu and consistent icons.
2. Replace case landing table with welcome dashboard, three workflow shortcuts, description composer and recent case previews. Provide searchable grid/list directory through URL parameters. Native accessible new-case dialog supports sketch and interview entry.
3. Carry dashboard descriptions to the existing workspace form. Keep generation explicitly user-triggered.
4. Add restrained transform/opacity entrance and hover motion, keyboard focus and reduced-motion support. Keep existing case workspace functional.
5. Verify production build and desktop/mobile browser flows, including search, dialog keyboard behavior, description handoff and navigation. Update handoff.

Assumptions: existing React/Vite authenticated desktop app, responsive mobile support, current branding and APIs. No added runtime dependencies. Target WCAG AA, LCP <2500ms, INP <200ms, CLS <0.1; performance targets require field measurement.
