# ClaimLens — Task Checklist

Full detail (acceptance criteria, verification, files) in [plan.md](plan.md). Work top to bottom; stop at each checkpoint for review before continuing (checkpoint-per-milestone autonomy, confirmed).

## Phase 0: Repo Scaffold
- [x] Task 1: Initialize project structure and tooling
- [ ] **Checkpoint: Repo Scaffold** — review with user

## Phase 1: Data Acquisition & Prep
- [x] Task 2: Dataset download script
- [x] Task 3: Verify no source-image leakage across splits
- [x] **Checkpoint: Data Acquisition & Prep** — review with user

## Phase 2: Image-Quality Gate
- [x] Task 4: Quality gate logic
- [x] **Checkpoint: Image-Quality Gate** — review with user

## Phase 3: Damage Detection & Segmentation
- [x] Task 5: Bounded YOLOv8n-seg fine-tune (MPS)
- [x] Task 6: Inference wrapper
- [x] **Checkpoint: Damage Detection & Segmentation** — review with user

## Phase 4: Visible Repair-Cost Estimator
- [x] Task 7: Curated price table
- [x] Task 8: Cost estimator module
- [x] **Checkpoint: Cost Estimator** — review with user

## Phase 5: Total-Loss Triage Engine
- [x] Task 9: Triage decision engine (blueprint §9)
- [x] **Checkpoint: Total-Loss Triage Engine** — review with user

## Phase 6: Policy Retrieval
- [ ] Task 10: Illustrative policy clause retrieval
- [ ] **Checkpoint: Policy Retrieval** — review with user

## Phase 7: Gradio Demo UI
- [ ] Task 11: Wire the pipeline into a Gradio Blocks app
- [ ] **Checkpoint: Gradio Demo UI** — review with user

## Phase 8: Eval / Metrics Writeup
- [ ] Task 12: Model card and metrics table
- [ ] **Checkpoint: Eval / Metrics Writeup** — review with user

## Phase 9: README + Deployment
- [ ] Task 13: README
- [ ] Task 14: Deploy to GitHub + Hugging Face Spaces
- [ ] **Checkpoint: Complete** — final acceptance against live demo
