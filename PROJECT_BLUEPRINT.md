# ClaimLens — Project Blueprint
### Explainable Vehicle Damage & Total-Loss Triage (portfolio edition)

*Working title — see §10 for alternatives. Adapted from a ChatGPT expert review of an original UAE-specific hackathon proposal, then re-scoped into a buildable, deployable, resume-ready solo project.*

---

## 0. TL;DR

The original idea — "AI looks at photos and decides if your car is a total loss" — got a 51/100 from ChatGPT's review because it collapses four different questions (can it be repaired? is repair economically justified? does insurance cover it? how much do they pay?) into one unverifiable prediction, trains on Reddit opinions, and lets an LLM invent repair prices.

The fix isn't more AI — it's *less arrogant* AI: detect what's visible, price what's visible, apply a transparent economic rule, and explicitly say "I can't see the chassis, get this inspected" when that's true. That reframe is what turns this into a real, gradeable computer-vision project instead of a plausible-sounding demo.

This document adapts that reviewed plan into something one person can actually build and deploy: a photo-based damage detector (real trained CV model) feeding a transparent, explainable total-loss triage engine, shipped as a live demo plus a GitHub repo.

---

## 1. Where this came from

You went through a car accident, and then a month of silence before your insurer finally called the vehicle a total loss. That wait — not knowing, no visibility into how the decision would be made or when — is the actual product insight here, more than the UAE regulatory detail in the original proposal. The project's honest pitch is: *"I can't fix insurance company response times, but I can show what a fast, transparent, first-pass read on 'is this likely a total loss' could look like — and, just as importantly, when it should honestly say it doesn't know."*

That "doesn't know" case is not a weakness to hide. It's the most technically credible part of the whole system, and the reviewer said as much: a model that abstains when the evidence is insufficient is more trustworthy than one that guesses confidently every time.

---

## 2. The ChatGPT review, polished

The original proposal was reviewed as a hackathon/grant pitch and scored across six dimensions. Kept here because the scorecard is a genuinely useful map of what to fix:

| Area | Score | Why |
|---|---|---|
| Problem statement | 8/10 | Real, relatable problem — but the pain (wait time, opacity) was never quantified |
| Novelty | 3/10 | Photo-based damage assessment + repairable-vs-total-loss prediction already exists commercially (Tractable, CCC) |
| Methodology | 4/10 | Over-relies on images alone, Reddit-derived labels, and LLM-generated price estimates |
| Execution feasibility | 5/10 | A narrow triage MVP is very feasible; the original "production-ready, comprehensive" scope was not |
| Impact & evaluation | 3/10 | No ground-truth strategy, metrics, baselines, or error analysis defined |
| UAE/regulatory fit | 5/10 | Best potential differentiator, but the proposal misunderstood how repairability, coverage, and total-loss actually interact |
| **Overall** | **~51/100** | Reject as a production/grant proposal; conditional advance as a hackathon project *after* a substantial pivot |

**The core conceptual bug.** The proposal's implicit model was:

```
Total loss = f(photograph)
```

That's wrong. Total loss is a function of several independent inputs — visible damage, estimated repair cost, pre-accident vehicle value, structural condition, and the applicable coverage/regulatory rule:

```
Total-loss assessment = f(damage, repair cost, pre-accident value, structural condition, policy rule)
```

A photo classifier can feed *one* of those inputs. It cannot be the decision by itself — and several proposed shortcuts compounded that mistake:

- **Reddit as ground truth.** What a stranger on Reddit *believes* counts as a total loss isn't a valid label for an insurance outcome — wrong jurisdiction, wrong incentives, and (separately) against Reddit's current API terms for training ML models without rightsholder permission.
- **LLM as a price database.** Asking a language model to "look up" repair prices invites hallucinated numbers presented as facts. An LLM is a good *reasoning and interface* layer (mapping "front left wing" → "left front fender," parsing policy wording, writing the explanation) and a bad *source of truth* for money.
- **"Repairable → covered by comprehensive insurance."** These are different questions. Whether a car *can* be fixed, whether fixing it is *economically justified*, whether the *policy covers this event*, and *how much* is payable are four separate determinations, and collapsing them produces a confidently wrong answer.
- **"Production-ready with perfect accuracy."** This is a credibility red flag to any technical reviewer. Even commercial vendors with huge proprietary datasets report confidence scores and abstention thresholds, not perfection. The right engineering target is *measured performance + calibrated uncertainty + safe abstention* — a system that says "insufficient evidence, inspection recommended" is behaving correctly, not failing.
- **Scope.** The original ask — CV, valuation, parts pricing, labor estimation, policy interpretation, payout calculation, a Reddit data pipeline, a marketing site, multi-insurer support, and a mobile app — is a funded startup's roadmap, not one project. It had to be cut down to something a single dashboard could demonstrate end to end.

The review's own reframing of the pitch is the right one, and it's the spine of everything below: *stop trying to predict the final claims decision, and instead build an evidence-backed pre-assessment and triage layer that knows the edge of its own competence.*

---

## 3. Scope decision: generalized, not UAE-locked

You flagged that the UAE-specific regulatory detail might be more than this needs — agreed, for two reasons: it gates the project behind legal research you'd have to redo for a portfolio piece, and it narrows the audience (most people reviewing your GitHub or resume won't be evaluating UAE insurance-law accuracy, they'll be evaluating your CV/ML engineering).

So the total-loss rule becomes a **configurable economic threshold** — "flag for total-loss review once estimated repair cost exceeds *X%* of pre-accident value" — instead of a hardcoded jurisdiction-specific figure. This is not a simplification that sacrifices credibility: it's actually how the concept generalizes in the real world. Jurisdictions differ mainly in *what X is and how it's computed* (UAE's motor-insurance framework uses a 50% economic test plus a structural-damage criterion; many others use a percentage-of-value threshold or a "repair cost + salvage value vs. actual cash value" formula). Making the threshold a parameter — with UAE's 50% as one selectable preset among a few illustrative ones — keeps the regulatory-reasoning *idea* (which the reviewer called the strongest possible differentiator) without requiring you to be a licensed authority on any one country's insurance code.

Same logic applies to the policy-clause retrieval layer (§9): it runs over a small set of clearly-labeled **sample/illustrative policy text**, not a real insurer's legal document, and every output says so.

---

## 4. What the product actually does

Not a binary classifier. A three-outcome triage, because a binary "total loss / not total loss" output is exactly the overconfident behavior the review flagged:

| Outcome | Meaning |
|---|---|
| **Probably repairable** | Estimated visible-damage cost is comfortably under the threshold, no structural red flags |
| **Probable total loss — recommend review** | Estimated cost crosses the configured threshold against vehicle value |
| **Insufficient evidence — physical inspection recommended** | Damage location/type suggests possible structural, mechanical, or hidden damage the photos can't resolve, or image quality/coverage is inadequate |

Every output ships with: which components were detected and how confidently, the cost range and what it assumes, the exact rule that produced the triage decision, and — critically — what *isn't* known from the submitted evidence.

---

## 5. System architecture

Each stage is independently built and independently evaluable — this was the review's central engineering fix, replacing one opaque end-to-end prediction with a pipeline of small, checkable steps:

```
Guided image capture (7 fixed views)
        │
        ▼
Image-quality gate  (reject blurry/unusable frames)
        │
        ▼
Damage detection & segmentation  (fine-tuned CV model)
   → damaged components, damage type, severity, per-detection confidence
        │
        ▼
Visible repair-cost estimator
   → component → repair-or-replace → curated part-price range + labor/paint range
   → preliminary cost range with assumptions listed
        │
        ▼
Total-loss triage engine
   → cost ÷ vehicle value vs. configurable threshold
   → structural/hidden-damage uncertainty flags
   → confidence calibration
        │
        ▼
Policy assistant (retrieval, not classification)
   → cites the specific clause it used; states "not established" rather than guessing
        │
        ▼
Explainable result: triage decision + uncertainty + escalation + full reasoning trail
```

---

## 6. Tech stack (and why)

Chosen against the actual constraints of building this solo and hosting it for free, not just in the abstract:

| Layer | Choice | Why |
|---|---|---|
| CV model | YOLOv8-seg (nano/small), PyTorch/Ultralytics | Small enough to fine-tune on CPU in a bounded time, small enough to run inference on free hosting, well-documented, exports cleanly to ONNX |
| Cost + decision logic | Plain Python, fully rule-based | No hallucination risk, every number traceable to a source — exactly what the review demanded |
| Policy retrieval | Lightweight embedding or TF-IDF similarity search over a small clause set | Real retrieval without needing a paid LLM API to function for every visitor |
| Demo / app UI | Gradio Blocks, custom CSS | Ships as an actual dashboard (the review's advice: *the dashboard is the impressive part, not a marketing hero section*), and is the standard, instantly-recognizable format for ML portfolio work |
| Hosting (live demo) | Hugging Face Spaces | Free, purpose-built for exactly this kind of ML/CV demo, no backend server to babysit |
| Source of record | GitHub | Where the resume link points; full code, training notebook, README with metrics |
| Optional stronger training | Google Colab (free GPU) notebook, included in repo | Lets you (or an interviewer) re-run training with more compute than this sandbox has, and swap in improved weights |

**Why not a custom Vercel-frontend + Render-backend split:** I checked current free tiers before recommending this. Render's free web-service tier is real but tight (512 MB RAM / 0.1 vCPU, sleeps after 15 minutes idle) — workable but constraining for a CV model. Vercel/Netlify free tiers don't run backend containers at all. Hugging Face Spaces is the one place built specifically for "upload an image, run a model, show the result" and is what ML hiring managers expect to see a CV portfolio project living on. A polished custom frontend is still achievable *inside* Gradio Blocks with custom CSS/HTML — you get the good dashboard without a second hosting bill or a second thing that can go down.

**A deliberate reliability choice:** the public, live demo does **not** require your own paid LLM API key to function. The policy-explanation layer defaults to template + retrieved-clause text; a real LLM call is documented as an optional local-run enhancement. This avoids a demo that quietly breaks (or racks up a bill) the day someone's resume gets a spike of clicks.

---

## 7. Data strategy

The original proposal's CarDD reference is a real, well-cited academic dataset (CarDD, arXiv 2211.00945) — but I checked, and getting it today means filling in a licensing form and waiting for the authors to email a download link, which isn't compatible with building this in one sitting. Two better-fitting alternatives, both checked for direct availability:

- **Primary: "CarDD" mirror on Roboflow Universe** — 2,500 images, 19 fine-grained damage classes (crack, scratch, dent, detachment, glass shatter, lamp broken/cracked, deformation by severity, tire flat, etc.), **licensed CC BY 4.0** (free use with attribution), directly exportable in YOLO/COCO format via Roboflow's API. This is the one to build against — permissively licensed, no waiting, and the fine-grained classes make for a better demo and a better resume line than a handful of broad categories.
- **Backup / supplement: Kaggle car-damage datasets** (e.g., `lplenka/coco-car-damage-detection-dataset`, `hendrichscullen/vehide-dataset-automatic-vehicle-damage-detection`) — smaller, useful for topping up specific damage classes or for a secondary held-out test set drawn from a different source than training (important for honest evaluation — see §11).

The README will state exactly which dataset and license the deployed model was trained on, with attribution. No Reddit-sourced images or labels anywhere in this project.

---

## 8. Model & training plan (kept honest, on purpose)

This sandbox has no GPU, so the plan is two-tier rather than one long shot in the dark:

1. **Now, in-session:** fine-tune YOLOv8n-seg (nano — smallest variant) on a bounded subset of the Roboflow data, few epochs, reduced image size, sized to finish in a bounded wall-clock window on CPU. Whatever mAP/IoU that run produces gets reported *as-is* in the README, with the constraint stated plainly ("CPU-only, N epochs, M images — see notebook for a stronger run").
2. **Optional, for you to run later:** a ready-to-run Colab notebook (free T4 GPU) that trains the same pipeline longer/larger, so you can drop in materially better weights before an interview cycle without re-architecting anything.

This mirrors exactly the standard the review set: *report calibrated, honest numbers, not a perfection claim.* A modest, clearly-explained mAP is a far better interview story than an unverifiable claim — you can walk through what the confusion matrix looks like, what class confuses the model, and what more data/epochs would fix.

---

## 9. Decision engine logic (generic version)

```python
economic_ratio = estimated_repair_cost / pre_accident_value

if structural_or_hidden_damage_suspected or image_evidence_insufficient:
    triage = "INSUFFICIENT_EVIDENCE_INSPECTION_REQUIRED"
elif economic_ratio >= total_loss_threshold:  # threshold is a config value, e.g. 0.50 / 0.70 / 0.75
    triage = "PROBABLE_TOTAL_LOSS_REVIEW"
else:
    triage = "PROBABLY_REPAIRABLE"
```

`total_loss_threshold` ships with a few illustrative regional presets (UAE's 50% economic test being one, cited to the CBUAE motor-insurance rulebook) that a user can pick from a dropdown — this keeps the "turn regulation into the innovation" idea from the review alive without hardwiring the whole system to one jurisdiction.

`structural_or_hidden_damage_suspected` is a rule, not a guess: it trips when detected damage is adjacent to structurally-relevant zones (e.g., pillar/frame-adjacent regions), when required views are missing/low-quality, or when model confidence on a load-bearing component falls below a set floor. This is what produces the "physical inspection recommended" case — the single most technically impressive output to show a reviewer, per the original assessment, because it demonstrates the system knows what it can't see.

---

## 10. Title options

| Name | Read |
|---|---|
| **ClaimLens** *(recommended)* | Clean, brandable; "lens" signals the CV angle, "claim" the insurance domain |
| **ClearClaim** | Leans into the personal motivation — transparency where you got none |
| **WriteOff AI** | "Written off" is the common UK/UAE/India term for a total loss; memorable, a little playful |
| **WreckWise** | Friendly, approachable, alliterative |

---

## 11. Evaluation plan

No single "accuracy" number — the review's sharpest critique was that a headline accuracy figure hides exactly the expensive edge cases that matter. Each stage gets its own metric:

| Component | Primary metric |
|---|---|
| Image quality gate | Usable-image precision/recall |
| Damaged-part identification | macro-F1, per-class precision/recall |
| Damage localization | mAP@50, mAP@50-95, IoU |
| Repair-cost estimate | MAE, median absolute % error vs. a small hand-built reference set |
| Total-loss triage | Sensitivity, specificity, confusion matrix |
| Confidence calibration | Brier score / calibration curve |
| Policy retrieval | Correct-clause retrieval rate |
| Safety (the one that matters most) | **False high-confidence auto-triage rate** — wrong *and* confident, the dangerous failure mode |

**Ground-truth hierarchy** (generic version of the review's ranking): real adjuster/inspection outcome > certified repair-shop estimate > expert-verified annotation > public dataset label. Nothing sourced from informal social-media opinion.

**No data leakage:** train/val/test splits enforced at the source-image level so the same photo (or near-duplicate crop) never appears in more than one split — otherwise reported metrics look artificially strong.

---

## 12. Deployment plan

1. **GitHub** — full source, training notebook, model card, README with metrics, architecture diagram, and this blueprint. You'll own the repo under your own account; I'll hand you a ready-to-push local repo plus the exact commands.
2. **Hugging Face Spaces (Gradio SDK)** — the live, linkable demo. Spaces are themselves git repos, so pushing here is the same `git push` motion as GitHub, just a second remote.
3. **No server to maintain** — both are static-push deployments; nothing to keep alive on your end.

---

## 13. Demo script (what a reviewer sees in 60 seconds)

| Case | Input | Output |
|---|---|---|
| A — obvious minor damage | Scuffed bumper/fender | *Probably repairable*, low cost ratio, high confidence |
| B — economically severe damage | Multi-panel front-end damage | *Probable total loss — recommend review*, cost ratio shown crossing the threshold, reasoning displayed |
| C — ambiguous/structural-adjacent damage | Damage near a structural zone | *Insufficient evidence — physical inspection recommended*, with an explicit statement of what can't be confirmed from the photos |

Case C is the one to lead with in an interview. It's the proof the system understands its own limits rather than guessing — which is the single point the original review kept returning to.

---

## 14. How this shows up on your resume / GitHub

**Suggested resume line (will tighten once the real metrics exist):**
> *ClaimLens — Explainable vehicle-damage & total-loss triage system. Fine-tuned a YOLOv8 segmentation model for damage detection, built a transparent (non-LLM) cost and decision-rule engine, and deployed a live demo; designed the system to abstain and escalate to human review when photo evidence is insufficient rather than force a low-confidence prediction.*

**README structure:** personal problem statement → live demo link + screenshot/GIF → architecture diagram → model metrics table → "why not just ask an LLM" section (this is a great, interview-bait section given the review's critique of LLM-as-price-oracle) → how to run locally → roadmap → license/disclaimer (illustrative project, not a licensed insurance or legal tool).

---

## 15. Roadmap

- **Now (this build):** the pipeline above, one clean demo, honest metrics.
- **Later, optional:** partner with a garage/assessor for real labeled outcomes; add a secondary weak signal (e.g., dashboard warning-light photo) for hidden-damage suspicion; multi-region threshold presets; better LLM-backed policy reasoning with citations, gated behind a user-supplied API key so the public demo stays free to run.

---

## 16. Open decisions

Captured as questions in the accompanying message — title pick, how autonomously to build, and how much time to invest in model training — since those materially change what happens next and are genuinely yours to call.
