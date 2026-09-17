# Hyperframes Composition Brief: ClaimLens

## Objective
Create a short, cinematic launch video for **ClaimLens** resolving the dual pain points of claims delay: consumer roadside anxiety and insurer manual inspection backlogs.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: landscape — 1920x1080 (16:9)
- Duration: 20.0 seconds (60 FPS)

## Source Material
- Project root: `/Users/tacticalcamel/ClaimLens`
- Primary files read:
  - `claimlens/static/index.html` (Cockpit layout, HUD, SVG annotations, badges)
  - `claimlens/static/css/styles.css` (Palette, typography, glass styling)
  - `README.md` (Blueprint evaluation metrics, architecture, CBUAE compliance)
  - `site/fixtures/case_b.json`, `site/fixtures/case_c.json` (Real AED pricing and triage outputs)
- Product name: `ClaimLens`
- Tagline / strongest claim: *"From 14 days of manual waiting to 3 seconds of verifiable certainty."*
- Key UI or visual moments to recreate:
  - Inspection reticle sweep across collision damage photo (`case_b.jpg`).
  - Two-stage segmentation masks (21 part classes in teal, 6 damage classes in ruby).
  - Real-time telemetry HUD counting up repair cost (AED 12,070) and loss ratio (80.5%).
  - CBUAE Article 7(2) Total Loss statutory seal.
  - Safe Abstention shield for structural unibody hit (`case_c.jpg`).

## Copy that must appear verbatim
- "An accident takes 2 seconds. The claim takes 14 days. Until now."
- "Stage 1: 21 Vehicle Parts • Stage 2: 6 Damage Classes"
- "3,174 Live Scraped UAE OEM Parts (AED)"
- "CBUAE Article 7(2) Statutory Total Loss: 80.5% > 50%"
- "Safe Abstention: Structural Integrity Mandatory Inspection"
- "0.0% False High-Confidence Decisions"

## Creative Direction
- Tone preset: `polished`
- Creative direction: `high-tech insurtech cockpit & cinematic product film`
- Interpretation: Precise, sharp, high density, dark cockpit styling (`#080C14`, `#0E1524`, `#10B981`, `#F43F5E`, `#F59E0B`). Every number and legal citation is authentic.
- Angle: Resolves the pain point of collision claims delays for both drivers and insurers.

## Visual Identity
- Background: `#080C14`
- Surface / Glass: `#0E1524` with `rgba(255, 255, 255, 0.1)` borders
- Text Primary: `#F8FAFC`
- Text Secondary: `#94A3B8`
- Accent Emerald: `#10B981`
- Alert Ruby: `#F43F5E`
- Warning Amber: `#F59E0B`
- Display font: `Syne`
- Body font: `Space Grotesk`
- Telemetry font: `JetBrains Mono`

## Storyboard
1. **Scene 1 (0.0s – 3.2s)**: The Dual Pain Point (Driver waiting vs Insurer backlog)
2. **Scene 2 (3.2s – 8.0s)**: Two-Stage Computer Vision & Spatial Overlap
3. **Scene 3 (8.0s – 13.5s)**: Deterministic AED Pricing & CBUAE Total Loss
4. **Scene 4 (13.5s – 17.0s)**: The Insurer Safety Invariant (Safe Abstention on Structural Hit)
5. **Scene 5 (17.0s – 20.0s)**: Cockpit Brand Lockup & Call To Action

## Audio
- Audio role: High-tech steady electronic rhythm with institutional confidence.
- Music: `happy-beats-business-moves-vol-12-by-ende-dot-app.mp3`
- Music treatment: Starts at 0.35, gentle swell into vision reveal, fades under outro logo.
- Beat sync locks:
  - 3.27s: Scene 2 vision reveal lands on beat (`bong_001.ogg`).
  - 8.74s: Scene 3 costing HUD countdown & statutory seal (`impactBell_heavy_000.ogg`).
  - 13.64s: Scene 4 amber safe abstention shield locks.
  - 17.47s: Scene 5 brand lockup settles.
- SFX files:
  - `assets/sfx/impact/impactSoft_medium_001.ogg`
  - `assets/sfx/impact/impactBell_heavy_000.ogg`
  - `assets/sfx/interface/bong_001.ogg`
  - `assets/sfx/interface/drop_001.ogg`
  - `assets/sfx/interface/switch_001.ogg`
