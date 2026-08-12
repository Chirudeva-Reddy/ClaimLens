# Spec: ClaimLens

Source: [PROJECT_BLUEPRINT.md](PROJECT_BLUEPRINT.md) — this spec operationalizes it into buildable, testable requirements. Where this spec is silent, the blueprint governs; where they conflict, this spec (as the more recent, human-approved document) wins and the blueprint should be updated to match.

## Assumptions

Proceeding on these unless corrected — none are blocking, all are cheap to revisit at the relevant milestone:

1. **Python/tooling:** Python 3.13 (already on this machine), `venv` + `pip` with a `pyproject.toml` (no poetry/uv) — will fall back to a pinned Python version at the model-training milestone only if `ultralytics`/`torch` lack 3.13 wheels yet.
2. **Image capture — deviates from blueprint §5.** The blueprint's "guided image capture (7 fixed views)" is not feasible to require of a user; ClaimLens instead accepts a variable number of user-submitted photos focused on the damaged area(s), with no mandatory full-vehicle coverage. This changes how the §9 `structural_or_hidden_damage_suspected` flag can detect "missing required views" — since there's no fixed checklist to check against, that rule needs a different basis (e.g. damage-zone proximity to structural areas, low photo count, poor coverage of the damaged region, or model confidence floor) rather than "did the user submit all 7 shots." Exact rule design deferred to the quality-gate/triage milestone.
3. **Curated price table:** a hand-built static JSON/CSV of illustrative per-component repair-or-replace price ranges + labor/paint rates, checked into the repo, clearly labeled illustrative (not a live pricing feed). Built at the cost-estimator milestone.
4. **Threshold presets** (blueprint §9): UAE 50% (cited to CBUAE motor-insurance rulebook) as one preset, plus 2-3 other illustrative percentage-of-value presets representing other common regulatory patterns — all explicitly labeled illustrative, not legal advice.
5. **Code style:** PEP 8 + type hints, formatted with `ruff format`, linted with `ruff check`. Docstrings only on public functions/classes where the "why" isn't obvious from the signature — no module essays.
6. **Testing split:** pure-Python logic (quality gate rules, cost estimator, triage engine, policy retrieval) gets `pytest` unit tests with real pass/fail assertions. ML model quality (mAP, IoU, etc.) is reported per blueprint §11 as metrics in the README/model card, not as a pass/fail test gate — a model that trains and produces *some* predictions is what CI can assert; whether the numbers are *good enough* is a human judgment call at that checkpoint.

## Objective

Build and deploy ClaimLens: a photo-based vehicle damage triage tool that (1) detects visible damage via a fine-tuned CV model, (2) estimates a visible-repair-cost range from curated, non-hallucinated pricing data, (3) applies a transparent, configurable economic rule to produce one of three outcomes — *probably repairable*, *probable total loss*, or *insufficient evidence, inspection recommended* — and (4) explains every output with the detections, cost assumptions, rule applied, and what remains unknown.

**User:** someone evaluating this as a portfolio/interview artifact (via the live demo + GitHub README) — the primary "user" of the running app is a stand-in for a claimant checking their own accident photos.

**Success looks like:** a working Gradio demo, live on Hugging Face Spaces, that correctly produces each of the three outcomes on the blueprint §13 demo cases (A/B/C), backed by a real trained model (not a stub) and a fully rule-based, source-cited decision engine — plus a GitHub repo whose README a technical reviewer can read in under 5 minutes and understand exactly what the system does and doesn't know.

## Tech Stack

- **Language:** Python 3.13
- **CV model:** YOLOv8n-seg (Ultralytics/PyTorch), fine-tuned with MPS acceleration on this machine (Apple M4 Pro) — target ~30-60 min wall-clock for the in-session run, more epochs/images than a CPU-only budget would allow (blueprint §8 tier 1, adapted for available hardware); ONNX export for portable inference.
- **Cost + decision logic:** plain Python, fully rule-based, no ML/LLM in this path.
- **Policy retrieval:** lightweight TF-IDF or embedding similarity search (scope decided at that milestone) over a small illustrative clause set.
- **Demo UI:** Gradio Blocks + custom CSS.
- **Package management:** `venv` + `pip`, `pyproject.toml`.
- **Testing:** `pytest`.
- **Formatting/linting:** `ruff`.
- **Hosting:** Hugging Face Spaces (Gradio SDK) for the live demo; GitHub for source of record. Both accounts are already available — exact repo/Space names confirmed at the deployment milestone.
- **Optional stronger training:** Colab notebook (documented, not executed in this session) — blueprint §8 tier 2.

## Commands

Finalized at the repo-scaffold milestone (first build step); expected shape:

```
Setup:  python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
Test:   pytest
Lint:   ruff check .
Format: ruff format .
Dev:    python -m claimlens.app        # launches Gradio demo locally
Train:  python -m claimlens.train      # bounded YOLOv8n-seg fine-tune (MPS)
```

## Project Structure

```
claimlens/
  quality_gate/       → image-quality gate (usable/reject logic)
  detection/           → damage detection & segmentation (model wrapper, inference)
  costing/              → repair-cost estimator + curated price table
  triage/                → total-loss decision engine (§9 logic)
  policy/                 → policy clause retrieval
  app.py                  → Gradio Blocks UI, wires the pipeline together
  train.py                → YOLOv8n-seg fine-tuning entrypoint
data/
  raw/                     → downloaded dataset (gitignored); Roboflow's export already provides
                              disjoint train/valid/test folders with no augmentation, so this is
                              used directly — no separate processed/ split step is needed
  price_table.json         → curated illustrative pricing data
  policy_clauses/          → sample/illustrative policy text
models/                     → trained weights + exported ONNX (gitignored, or Git LFS if small enough)
tests/                       → pytest unit tests, mirrors claimlens/ package layout
notebooks/
  colab_train.ipynb          → optional stronger-training notebook (blueprint §8 tier 2)
README.md
SPEC.md
PROJECT_BLUEPRINT.md
```

## Code Style

```python
def compute_economic_ratio(estimated_repair_cost: float, pre_accident_value: float) -> float:
    """Repair cost as a fraction of pre-accident value; the core §9 input."""
    if pre_accident_value <= 0:
        raise ValueError("pre_accident_value must be positive")
    return estimated_repair_cost / pre_accident_value
```

- Type hints on all function signatures.
- Docstring only where the *why* isn't obvious from the name/signature (as above — not "adds two numbers").
- Raise on invalid input at boundaries (e.g. non-positive vehicle value); trust internal callers otherwise.
- No premature abstraction — one triage rule function, not a `TriageStrategy` interface, unless/until a second strategy is actually needed.

## Testing Strategy

- **Framework:** `pytest`, tests under `tests/`, mirroring `claimlens/` package structure (`tests/triage/test_decision.py` etc.).
- **Pure-logic modules** (quality gate rules, cost estimator, triage engine, policy retrieval): unit tests with concrete pass/fail assertions, run in CI/pre-commit. Every branch in the §9 decision table gets at least one test case.
- **Model/ML code:** a smoke test that the training pipeline runs end-to-end on a tiny fixture subset and inference produces well-formed output (not a quality gate on mAP). Real quality metrics (mAP@50, IoU, macro-F1, calibration, etc. — full list in blueprint §11) are reported in the model card/README, reviewed by the human at that milestone's checkpoint rather than asserted in a test.
- **No data leakage:** enforced at the split-generation step (source-image-level train/val/test split), verified by a test that checks no image ID appears in more than one split.
- **End-to-end acceptance:** blueprint §13's three demo cases (A/B/C) run manually against the deployed Gradio app as the final acceptance check before considering the build done.

## Boundaries

- **Always:** run `pytest` and `ruff check` before considering a milestone complete; keep the total-loss threshold and all prices/rates in config/data files, never hardcoded inline; label all pricing and policy content as illustrative; state assumptions/uncertainty in every triage output.
- **Ask first:** adding any new dependency beyond what's already scoped here; changing the resolved decisions (title, per-milestone checkpoint cadence, training budget); any change to the §9 decision logic's structure (not its threshold values, which are meant to be configurable); committing trained model weights if they're large enough to need Git LFS; anything touching the GitHub/HF account or repo/Space naming.
- **Never:** call an LLM for a price or a policy fact (blueprint's core anti-pattern, §2); use Reddit-sourced data or labels; commit API keys/tokens (Roboflow, HF) — use environment variables / a gitignored `.env`; claim "production-ready" or report a single headline accuracy number in place of the §11 metrics table; skip the "insufficient evidence" path to force a confident answer.

## Success Criteria

- All three blueprint §13 demo cases (A/B/C) produce the correct triage outcome when run against the live deployed demo.
- A real fine-tuned YOLOv8n-seg model (not a stub/pretrained-only model) backs the detection stage, trained via the in-session MPS run, with honest metrics reported per §11 (whatever they are — no minimum mAP bar required to ship, per blueprint §8's "report calibrated, honest numbers, not a perfection claim").
- Every triage output includes: detected components + confidence, cost range + assumptions, the exact rule/threshold applied, and an explicit statement of what isn't known from the submitted evidence.
- `pytest` passes, covering every branch of the §9 decision table and the no-leakage split check.
- Demo is live on Hugging Face Spaces; source (code, training notebook, README with metrics, model card) is on GitHub.
- README includes: personal problem statement, live demo link, architecture diagram, metrics table, "why not just ask an LLM" section, local run instructions, roadmap, and an illustrative-project/non-legal-advice disclaimer (blueprint §14).

## Open Questions

- Exact Roboflow API key/account — deferred to the data-acquisition milestone (user will obtain then).
- Exact GitHub repo name and Hugging Face Space name/visibility — deferred to the deployment milestone (accounts already exist).
- Whether policy retrieval uses TF-IDF or a lightweight embedding model — deferred to that milestone; either satisfies blueprint §6's "no paid LLM API required for the public demo" constraint.
- Final `total_loss_threshold` preset list and exact percentages beyond UAE's 50% — deferred to the triage-engine milestone.
