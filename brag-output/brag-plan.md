# Brag Plan: ClaimLens

## What is this app?
ClaimLens is an explainable, two-stage vehicle damage segmentation and statutory total-loss triage system powered by fine-tuned YOLOv8-seg, deterministic UAE OEM parts pricing in AED, and CBUAE regulatory decision logic.

## The angle
An automotive accident takes 2 seconds—yet traditional insurance claim triage takes 10 to 14 days of painful roadside uncertainty for the driver, and creates massive manual inspection backlogs for insurance companies. ClaimLens eliminates both delays with instant, explainable computer vision that prices repairs in AED and applies statutory total loss rules, while safely abstaining when unibody structural integrity is compromised.

## Hook (first 2-3 seconds)
A stark, high-contrast hook confronting both sides of the crisis:
- **Left (Consumer)**: "Day 11 waiting roadside..." with an anxious driver icon.
- **Right (Insurer)**: "4,200 backlogged manual claims..." with overwhelmed adjusters.
- **Punchy Title**: *"An accident takes 2 seconds. The claim takes 14 days. Until now."*

## Key moments (the middle)
1. **The Instant Two-Stage CV Scan (3.2s – 8.0s)**:
   - Collision photograph enters under a glowing inspection reticle.
   - Stage 1 segments 21 automotive body panels (`yolov8n-seg`, 80.8% Mask mAP) in crisp emerald/teal.
   - Stage 2 pinpoints collision damage categories (`dent`, `scratch`, `tear`) in calibrated ruby polygons.
   - Shapely spatial overlap links damage to underlying panels.
2. **Deterministic UAE OEM Pricing & CBUAE Total-Loss Triage (8.0s – 13.5s)**:
   - Live telemetry HUD counts up repair cost to **AED 12,070** against a pre-accident value of AED 15,000.
   - Economic Loss Ratio hits **80.5%**, immediately triggering Central Bank of the UAE (CBUAE) Article 7(2) statutory constructive total-loss rule (> 50%).
   - Zero pricing hallucinations: grounded in 3,174 scraped UAE OEM parts across Toyota, Nissan, Hyundai, and Mercedes.
3. **The Insurer Safety Invariant: Safe Abstention (13.5s – 17.0s)**:
   - Load-bearing structural zones (quarter-panel hit in Case C) trigger mandatory safe abstention (`INSUFFICIENT_EVIDENCE_INSPECTION_REQUIRED`).
   - Displays clear "What Isn't Known" checklist (laser-bench alignment, unibody geometry, SRS sensors).
   - Solves the insurer's greatest fear: no black-box guesses when vehicle roadworthiness is on the line.

## Outro / punchline (17.0s – 20.0s)
The cockpit brand lockup settles with live demo badge:
- *"From 14 days of manual waiting to 3 seconds of verifiable certainty."*
- Badge: `chirudeva-reddy.github.io/ClaimLens`

## User flow worth showing
1. **Entry**: Accident photo loaded into the inspection cockpit.
2. **Key Action**: Two-stage segmentation scans panels and damages; spatial intersection flags zones.
3. **Result**: Deterministic AED quote generated; CBUAE statutory decision rendered; instant PDF/JSON triage report export.

## Tone
- Preset: `polished`
- Creative direction: `high-tech insurtech cockpit & dramatic product film`
- Interpretation: Serious, authoritative, crisp typography, clean transitions, zero generic SaaS fluff, highlighting real legal and financial precision.

## Format: landscape — 1920x1080
## Duration: 20.0 seconds

## Visual identity (from the project)
- Background: `#080C14` (Neutral charcoal/slate cockpit foundation)
- Surface: `#0E1524` (Elevated cockpit glass)
- Accent: `#10B981` (Calibrated emerald)
- Damage / Alert: `#F43F5E` (Ruby red for damage masks & total loss)
- Warning: `#F59E0B` (Amber for structural abstention)
- Display font: `Syne`
- Body font: `Space Grotesk`
- Telemetry font: `JetBrains Mono`
- Strongest visual element: The magnifying inspection lens with polygon damage mesh and real-time loss ratio HUD.

## Share copy (draft)
An accident takes 2 seconds—the insurance claim shouldn't take 14 days. ClaimLens combines two-stage computer vision, live UAE OEM parts pricing (AED), and CBUAE statutory rules for instant, explainable total-loss triage.

## Audio direction
- Role: Steady, high-tech electronic groove with clean corporate authority.
- Music: `happy-beats-business-moves-vol-12-by-ende-dot-app.mp3`
- Music treatment: Volume at 0.35, gentle fade under opening text, swelling into the vision reveal, and fading cleanly under the final logo.
- Music cue guidance:
  - Strong cues: 3.27s (beat lock: vision reveal), 8.74s (beat lock: costing & total loss trigger), 13.64s (beat lock: structural abstention), 17.47s (beat lock: logo & resolution).
- Audio-reactive treatment: Subtle neon glow and reticle pulses that breathe with the music.
- SFX posture: Restrained, high-fidelity UI clicks, soft impact swells, and confirmation dings.
- Restraint rule: No loud screeching crash sounds or cartoon effects. Sound must reflect high-reliability institutional fintech/insurtech.

## Storyboard

### Scene 1 — The Dual Pain Point — 3.2s
- **Visual**: Split canvas in `#080C14`. Left side features the driver stranded roadside ("Day 11 waiting for an adjuster"). Right side features the insurer backlog ("4,200 manual claims waiting in queue"). Center headline slides in: *"An accident takes 2 seconds. The claim takes 14 days."*
- **Sequential**: Left card slides in at 0.4s, right card at 0.8s, center hook locks at 1.4s.
- **Audio intent**: Mood of friction and delay.
- **Audio-coupled idea**: Soft impact at 0.4s (`impactSoft_medium_001.ogg`), subtle switch at 0.8s (`switch_001.ogg`).
- **Music**: Vol 12 starts softly.
- **Transition**: Fast optical sweep (`drop_001.ogg`) into Scene 2 at 3.2s.

### Scene 2 — Two-Stage Vision & Spatial Overlap — 4.8s (3.2s – 8.0s)
- **Visual**: Real collision photo enters (`case_b.jpg`). Inspection reticle calibrates. Stage 1 highlights 21 vehicle panels (bumper, hood, fender) in teal outline. Stage 2 segments collision damages (dent D01, scratch D02) in ruby polygons. Spatial polygon intersection binds damages to panels.
- **Sequential**: Reticle sweeps at 3.4s, panel masks pop at 4.2s, damage polygons lock with labels at 5.5s.
- **Audio intent**: High-precision engineering scan.
- **Audio-coupled idea**: Beat-locked at 3.27s with entry pop (`bong_001.ogg`).
- **Transition**: Smooth slide into telemetry cockpit at 8.0s.

### Scene 3 — Deterministic AED Costing & CBUAE Total Loss — 5.5s (8.0s – 13.5s)
- **Visual**: Cockpit telemetry HUD expands. Real scraped UAE OEM catalog prices (AED) calculate live line items (Front Bumper: AED 3,250, Hood Assembly: AED 4,120, Labor: AED 4,700). Total counter ticks rapidly from AED 0 to AED 12,070. Pre-accident cash value: AED 15,000. Loss ratio bar fills to 80.5%. CBUAE Article 7(2) statutory badge flashes: **TOTAL LOSS VERDICT (> 50% Threshold Exceeded)**.
- **Sequential**: Counter spins up from 8.2s to 10.0s; loss ratio bar animates; total loss seal slams in at 10.8s.
- **Audio-coupled idea**: Beat-locked at 8.74s; confirmation chime (`impactBell_heavy_000.ogg`) at 10.8s.
- **Transition**: Switch to safety invariant at 13.5s.

### Scene 4 — The Insurer Safety Invariant (Safe Abstention) — 3.5s (13.5s – 17.0s)
- **Visual**: Case C loads showing structural quarter-panel collision. System detects damage intersecting load-bearing unibody zone. Instead of guessing, ClaimLens displays amber warning: `INSUFFICIENT_EVIDENCE_INSPECTION_REQUIRED` with mandatory bench inspection checklist. Zero LLM hallucinations.
- **Sequential**: Zone detection at 13.8s, amber shield stamp at 14.5s, checklist items check off sequentially.
- **Audio-coupled idea**: Beat-locked at 13.64s; warning switch click (`switch_001.ogg`).
- **Transition**: Zoom into final brand card at 17.0s.

### Scene 5 — Outro & Resolution — 3.0s (17.0s – 20.0s)
- **Visual**: ClaimLens Cockpit brand mark, version badge, and tagline: *"From 14 days of delays to 3 seconds of verifiable certainty."* Link: `chirudeva-reddy.github.io/ClaimLens`.
- **Sequential**: Logo scales in with emerald glow at 17.2s; URL badge settles at 17.8s; gentle hold until 20.0s.
- **Audio-coupled idea**: Beat-locked at 17.47s; music bed fades smoothly.
