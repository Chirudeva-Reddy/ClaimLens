/**
 * ClaimLens Insurtech Cockpit Client Engine
 * Anti-Slop V6, Motion 4, Density 8
 * Features:
 * 1. High-precision SVG polygon vector rendering with non-scaling strokes & glow.
 * 2. True bidirectional hover synchronization between polygons & table rows with clamped Tooltip HUD.
 * 3. Micro-motion scenario switcher bar with smooth loading skeleton shimmer.
 * 4. Real-time dual-slider simulation (ACV & Threshold) connected to <5ms /api/recalculate.
 * 5. Executive appraisal survey report export modal & white-paper print handler.
 */

document.addEventListener('DOMContentLoaded', () => {
    'use strict';

    // Application State
    const state = {
        activeScenarioId: null,
        uploadedFile: null,
        lastAnalysisData: null,
        imageDimensions: { width: 1000, height: 1000 },
        activeLayers: { parts: true, damages: true, labels: true },
        claimReferenceId: generateClaimId()
    };

    function generateClaimId() {
        const rand = Math.floor(1000 + Math.random() * 9000);
        return `CLM-2026-DXB-${rand}`;
    }

    // Status Icons (Clean Monochromatic / Semantic SVGs, No Emojis)
    const STATUS_ICONS = {
        waiting: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
        emerald: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
        ruby: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
        amber: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`
    };

    // DOM Elements - Navigation & Evidence Setup
    const dropzone = document.getElementById('upload-dropzone');
    const fileInput = document.getElementById('image-file-input');
    const dropzoneIdle = document.getElementById('dropzone-idle');
    const dropzonePreview = document.getElementById('dropzone-preview');
    const previewImg = document.getElementById('preview-img');
    const btnClearPreview = document.getElementById('btn-clear-preview');
    const qualityGateBanner = document.getElementById('quality-gate-banner');

    const selectBrand = document.getElementById('select-brand');
    const inputAcv = document.getElementById('input-acv');
    const sliderAcv = document.getElementById('slider-acv');
    const acvDisplayTag = document.getElementById('acv-display-tag');
    const selectJurisdiction = document.getElementById('select-jurisdiction');
    const sliderThreshold = document.getElementById('slider-threshold');
    const sliderThresholdVal = document.getElementById('slider-threshold-val');
    const btnRunInspection = document.getElementById('btn-run-inspection');
    const btnSpinner = document.getElementById('btn-spinner');
    const latencyVal = document.getElementById('latency-val');

    // DOM Elements - Executive Telemetry
    const triageBanner = document.getElementById('triage-banner');
    const triageIcon = document.getElementById('triage-icon');
    const triageHeadline = document.getElementById('triage-headline');
    const triageSummary = document.getElementById('triage-summary');
    const triageAction = document.getElementById('triage-action');
    const gaugeBar = document.getElementById('gauge-bar');
    const gaugeLossRatio = document.getElementById('gauge-loss-ratio');

    const kpiRepairCost = document.getElementById('kpi-repair-cost');
    const kpiRepairRange = document.getElementById('kpi-repair-range');
    const kpiAcv = document.getElementById('kpi-acv');
    const kpiThreshold = document.getElementById('kpi-threshold');
    const kpiThresholdRule = document.getElementById('kpi-threshold-rule');

    // DOM Elements - Split Studio & Canvas
    const canvasViewport = document.getElementById('canvas-viewport');
    const canvasPlaceholder = document.getElementById('canvas-placeholder');
    const canvasWrapper = document.getElementById('canvas-wrapper');
    const canvasBaseImg = document.getElementById('canvas-base-img');
    const canvasSvg = document.getElementById('canvas-svg');
    const canvasTooltip = document.getElementById('canvas-tooltip');
    const ttHeader = document.getElementById('tt-header');
    const ttDamage = document.getElementById('tt-damage');
    const ttConf = document.getElementById('tt-conf');
    const ttCost = document.getElementById('tt-cost');

    // DOM Elements - Analytical Console Tabs
    const tableBody = document.getElementById('table-body');
    const assumptionsList = document.getElementById('assumptions-list');
    const policyClausesContainer = document.getElementById('policy-clauses-container');

    // DOM Elements - Appraisal Modal & Export
    const adjusterModalBackdrop = document.getElementById('adjuster-modal-backdrop');
    const btnOpenAppraisal = document.getElementById('btn-open-appraisal');
    const btnCloseModal = document.getElementById('btn-close-modal');
    const btnModalPrint = document.getElementById('btn-modal-print');
    const btnPrintReport = document.getElementById('btn-print-report');
    const btnExportJson = document.getElementById('btn-export-json');

    const rptClaimId = document.getElementById('rpt-claim-id');
    const rptDate = document.getElementById('rpt-date');
    const rptBrand = document.getElementById('rpt-brand');
    const rptVerdictBadge = document.getElementById('rpt-verdict-badge');
    const rptAcv = document.getElementById('rpt-acv');
    const rptRepair = document.getElementById('rpt-repair');
    const rptLossRatio = document.getElementById('rpt-loss-ratio');
    const rptThreshold = document.getElementById('rpt-threshold');
    const rptStatementText = document.getElementById('rpt-statement-text');
    const rptTableBody = document.getElementById('rpt-table-body');
    const rptClauseTitle = document.getElementById('rpt-clause-title');
    const rptClauseText = document.getElementById('rpt-clause-text');

    // =========================================================================
    // 1. Tab Navigation Handlers
    // =========================================================================
    document.querySelectorAll('.tabs-nav .tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tabs-nav .tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            const targetId = btn.getAttribute('data-tab');
            const targetPane = document.getElementById(targetId);
            if (targetPane) targetPane.classList.add('active');
        });
    });

    // =========================================================================
    // 2. Real-Time Dynamic ACV & Threshold Controls
    // =========================================================================
    function syncAcvDisplay(val) {
        const num = parseFloat(val) || 0;
        inputAcv.value = num;
        if (sliderAcv) {
            sliderAcv.value = Math.min(250000, Math.max(5000, num));
        }
        if (acvDisplayTag) {
            acvDisplayTag.textContent = `AED ${num.toLocaleString('en-US')}`;
        }
        document.querySelectorAll('.chip-btn').forEach(c => {
            if (parseFloat(c.getAttribute('data-val')) === num) {
                c.classList.add('active');
            } else {
                c.classList.remove('active');
            }
        });
    }

    if (sliderAcv) {
        sliderAcv.addEventListener('input', (e) => {
            syncAcvDisplay(e.target.value);
            triggerRecalculate();
        });
    }

    inputAcv.addEventListener('input', (e) => {
        syncAcvDisplay(e.target.value);
        triggerRecalculate();
    });

    document.querySelectorAll('.chip-btn').forEach(chip => {
        chip.addEventListener('click', () => {
            const val = parseFloat(chip.getAttribute('data-val'));
            syncAcvDisplay(val);
            triggerRecalculate();
        });
    });

    sliderThreshold.addEventListener('input', (e) => {
        sliderThresholdVal.textContent = `${e.target.value}%`;
        if (selectJurisdiction.value !== 'custom') {
            selectJurisdiction.value = 'custom';
            kpiThresholdRule.textContent = 'Custom Insurer Economic Rule';
        }
        triggerRecalculate();
    });

    selectJurisdiction.addEventListener('change', (e) => {
        const val = e.target.value;
        if (val === 'uae_50') {
            sliderThreshold.value = 50;
            sliderThresholdVal.textContent = '50%';
            kpiThresholdRule.textContent = 'CBUAE Motor Policy Article 7(2)';
        } else if (val === 'us_70') {
            sliderThreshold.value = 70;
            sliderThresholdVal.textContent = '70%';
            kpiThresholdRule.textContent = 'US Total Loss Formula (70%)';
        } else if (val === 'us_75') {
            sliderThreshold.value = 75;
            sliderThresholdVal.textContent = '75%';
            kpiThresholdRule.textContent = 'US Standard Economic Rule (75%)';
        } else if (val === 'uk_60') {
            sliderThreshold.value = 60;
            sliderThresholdVal.textContent = '60%';
            kpiThresholdRule.textContent = 'UK / European Market Standard (60%)';
        } else {
            kpiThresholdRule.textContent = 'Custom Insurer Economic Rule';
        }
        triggerRecalculate();
    });

    // =========================================================================
    // 3. Evidence Dropzone & File Upload Handling
    // =========================================================================
    dropzone.addEventListener('click', (e) => {
        if (!state.uploadedFile && !state.activeScenarioId && e.target !== btnClearPreview) {
            fileInput.click();
        }
    });

    dropzone.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            fileInput.click();
        }
    });

    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) handleSelectedFile(file);
    });

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('drag-over');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('drag-over');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('drag-over');
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            handleSelectedFile(e.dataTransfer.files[0]);
        }
    });

    btnClearPreview.addEventListener('click', (e) => {
        e.stopPropagation();
        clearInputEvidence();
    });

    function handleSelectedFile(file) {
        state.uploadedFile = file;
        state.activeScenarioId = null;
        document.querySelectorAll('.scenario-tab-btn').forEach(c => c.classList.remove('active-scenario'));

        const reader = new FileReader();
        reader.onload = (event) => {
            previewImg.src = event.target.result;
            dropzoneIdle.classList.add('hidden');
            dropzonePreview.classList.remove('hidden');
            qualityGateBanner.classList.add('hidden');
        };
        reader.readAsDataURL(file);
    }

    function clearInputEvidence() {
        state.uploadedFile = null;
        state.activeScenarioId = null;
        fileInput.value = '';
        previewImg.src = '';
        dropzonePreview.classList.add('hidden');
        dropzoneIdle.classList.remove('hidden');
        qualityGateBanner.classList.add('hidden');
        document.querySelectorAll('.scenario-tab-btn').forEach(c => c.classList.remove('active-scenario'));
    }

    // =========================================================================
    // 4. Quick-Launch Scenario Switcher (Segmented Micro-Motion)
    // =========================================================================
    document.querySelectorAll('.scenario-tab-btn').forEach(tab => {
        tab.addEventListener('click', () => {
            const caseId = tab.getAttribute('data-case');
            loadAndRunScenario(caseId);
        });
    });

    async function loadAndRunScenario(caseId) {
        document.querySelectorAll('.scenario-tab-btn').forEach(c => {
            c.classList.remove('active-scenario');
            c.setAttribute('aria-selected', 'false');
        });

        const activeTab = document.querySelector(`[data-case="${caseId}"]`);
        if (activeTab) {
            activeTab.classList.add('active-scenario');
            activeTab.setAttribute('aria-selected', 'true');
        }

        state.activeScenarioId = caseId;
        state.uploadedFile = null;

        // Populate preset parameters
        if (caseId === 'case_a') {
            selectBrand.value = 'Toyota';
            syncAcvDisplay(120000);
            selectJurisdiction.value = 'uae_50';
            sliderThreshold.value = 50;
            sliderThresholdVal.textContent = '50%';
            kpiThresholdRule.textContent = 'CBUAE Motor Policy Article 7(2)';
        } else if (caseId === 'case_b') {
            selectBrand.value = 'General Market Standard';
            syncAcvDisplay(15000);
            selectJurisdiction.value = 'uae_50';
            sliderThreshold.value = 50;
            sliderThresholdVal.textContent = '50%';
            kpiThresholdRule.textContent = 'CBUAE Motor Policy Article 7(2)';
        } else if (caseId === 'case_c') {
            selectBrand.value = 'Toyota';
            syncAcvDisplay(85000);
            selectJurisdiction.value = 'uae_50';
            sliderThreshold.value = 50;
            sliderThresholdVal.textContent = '50%';
            kpiThresholdRule.textContent = 'CBUAE Motor Policy Article 7(2)';
        }

        // Preview image load
        previewImg.src = `/api/scenarios/${caseId}/image`;
        dropzoneIdle.classList.add('hidden');
        dropzonePreview.classList.remove('hidden');
        qualityGateBanner.classList.add('hidden');

        // Automatically trigger AI analysis pipeline
        await executeAnalysis();
    }

    // =========================================================================
    // 5. Loading Skeletons & Analysis Execution
    // =========================================================================
    btnRunInspection.addEventListener('click', async () => {
        await executeAnalysis();
    });

    function setCockpitLoading(isLoading) {
        if (isLoading) {
            btnSpinner.classList.remove('hidden');
            btnRunInspection.disabled = true;

            kpiRepairCost.classList.add('skeleton');
            kpiAcv.classList.add('skeleton');
            kpiThreshold.classList.add('skeleton');
            gaugeLossRatio.classList.add('skeleton');
            triageHeadline.classList.add('skeleton');
            triageSummary.classList.add('skeleton');

            tableBody.innerHTML = `
                <tr><td colspan="6" class="skeleton" style="height: 32px; margin: 4px 0; border: none;"></td></tr>
                <tr><td colspan="6" class="skeleton" style="height: 32px; margin: 4px 0; border: none;"></td></tr>
                <tr><td colspan="6" class="skeleton" style="height: 32px; margin: 4px 0; border: none;"></td></tr>
            `;
        } else {
            btnSpinner.classList.add('hidden');
            btnRunInspection.disabled = false;

            kpiRepairCost.classList.remove('skeleton');
            kpiAcv.classList.remove('skeleton');
            kpiThreshold.classList.remove('skeleton');
            gaugeLossRatio.classList.remove('skeleton');
            triageHeadline.classList.remove('skeleton');
            triageSummary.classList.remove('skeleton');
        }
    }

    async function executeAnalysis() {
        if (!state.uploadedFile && !state.activeScenarioId) {
            alert('Please select a collision photograph or click one of the Quick-Launch validation scenarios above.');
            return;
        }

        setCockpitLoading(true);
        const startTime = performance.now();

        try {
            const formData = new FormData();
            if (state.activeScenarioId) {
                formData.append('scenario_id', state.activeScenarioId);
            } else if (state.uploadedFile) {
                formData.append('image', state.uploadedFile);
            }

            formData.append('brand', selectBrand.value);
            formData.append('acv', inputAcv.value);
            formData.append('jurisdiction', selectJurisdiction.value);
            formData.append('custom_threshold', sliderThreshold.value);

            const response = await fetch('/api/analyze', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`Server returned HTTP ${response.status}`);
            }

            const data = await response.json();
            const elapsed = Math.round(performance.now() - startTime);
            if (latencyVal) {
                latencyVal.textContent = `${elapsed}ms PIPELINE`;
            }

            state.lastAnalysisData = data;
            renderAnalysisResults(data);

        } catch (err) {
            console.error('Inspection failed:', err);
            alert(`Analysis encountered an error: ${err.message}`);
        } finally {
            setCockpitLoading(false);
        }
    }

    // =========================================================================
    // 6. Render Inspection & Telemetry Results
    // =========================================================================
    function renderAnalysisResults(data) {
        // Quality Gate status
        if (!data.quality_gate.accepted) {
            qualityGateBanner.textContent = `Quality Gate Flag: ${data.quality_gate.reason}. ${data.quality_gate.actionable_guidance}`;
            qualityGateBanner.className = 'quality-gate-banner rejected';
            qualityGateBanner.classList.remove('hidden');
        } else {
            qualityGateBanner.classList.add('hidden');
        }

        // Triage Decision Banner
        const color = data.triage.status_color || 'emerald';
        triageBanner.className = `triage-banner status-${color}`;
        triageIcon.innerHTML = STATUS_ICONS[color] || STATUS_ICONS.emerald;
        triageHeadline.textContent = data.triage.headline;
        triageSummary.textContent = data.triage.summary_reason;
        triageAction.textContent = data.triage.recommended_action;

        // Radial Loss Ratio Gauge
        const ratio = Math.min(100.0, Math.max(0.0, data.financials.loss_ratio_pct));
        gaugeLossRatio.textContent = `${ratio.toFixed(1)}%`;
        const circumference = 314.159;
        const offset = circumference - (ratio / 100.0) * circumference;
        gaugeBar.style.strokeDashoffset = offset;
        gaugeBar.style.stroke = color === 'emerald' ? '#10B981' : (color === 'ruby' ? '#F43F5E' : '#F59E0B');

        // KPI Telemetry Cards
        kpiRepairCost.textContent = `AED ${data.financials.repair_cost_median_aed.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        kpiRepairRange.textContent = `Min: AED ${data.financials.repair_cost_min_aed.toLocaleString()} • Max: AED ${data.financials.repair_cost_max_aed.toLocaleString()}`;
        kpiAcv.textContent = `AED ${data.financials.acv_aed.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        kpiThreshold.textContent = `${data.financials.threshold_pct.toFixed(1)}%`;

        // Canvas & High-Precision SVG Rendering
        if (data.image_meta && data.image_meta.raw_base64) {
            canvasPlaceholder.classList.add('hidden');
            canvasBaseImg.src = data.image_meta.raw_base64;
            state.imageDimensions = {
                width: data.image_meta.width,
                height: data.image_meta.height
            };
            canvasSvg.setAttribute('viewBox', `0 0 ${data.image_meta.width} ${data.image_meta.height}`);
            canvasSvg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
            renderSvgPolygons(data.polygons, data.line_items);
        }

        // Analytical Tables & Knowledge Base
        renderCostTable(data.line_items);

        if (data.assumptions && assumptionsList) {
            assumptionsList.innerHTML = data.assumptions.map(a => `<li>${a}</li>`).join('');
        }

        if (data.policy_guidance && policyClausesContainer) {
            renderPolicyClauses(data.policy_guidance);
        }

        // Populate official appraisal report modal
        populateAppraisalReport(data);

        // Smoothly bring results into focus
        document.getElementById('triage-section').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    // =========================================================================
    // 7. High-Precision SVG Polygon Vector Rendering
    // =========================================================================
    function renderSvgPolygons(polygons, lineItems) {
        canvasSvg.innerHTML = '';

        if (!polygons || polygons.length === 0) return;

        polygons.forEach((poly) => {
            if (!poly.polygon || poly.polygon.length < 3) return;

            const pointsStr = poly.polygon.map(p => `${p[0]},${p[1]}`).join(' ');
            const el = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
            el.setAttribute('points', pointsStr);
            el.setAttribute('data-id', poly.id);
            el.setAttribute('data-type', poly.type);
            el.setAttribute('data-label', poly.label);
            el.setAttribute('data-conf', `${(poly.confidence * 100).toFixed(0)}%`);
            el.setAttribute('vector-effect', 'non-scaling-stroke');

            let cssClass = 'svg-polygon ';
            if (poly.type === 'part') {
                cssClass += poly.is_structural ? 'svg-structural' : 'svg-part';
            } else {
                cssClass += poly.is_structural ? 'svg-structural' : 'svg-damage';
            }
            el.setAttribute('class', cssClass);

            if (poly.type === 'damage' && poly.line_item_index !== undefined) {
                el.setAttribute('data-line-item-index', poly.line_item_index);
            }

            // Polygon Hover Events
            el.addEventListener('mouseenter', (e) => {
                highlightPolygonAndRow(poly.id, true);
                showTooltip(e, poly, lineItems);
            });

            el.addEventListener('mousemove', (e) => {
                updateTooltipPos(e);
            });

            el.addEventListener('mouseleave', () => {
                highlightPolygonAndRow(poly.id, false);
                hideTooltip();
            });

            canvasSvg.appendChild(el);
        });

        applyLayerVisibility();
    }

    // =========================================================================
    // 8. Tooltip HUD with Edge Boundary Clamping
    // =========================================================================
    function showTooltip(event, poly, lineItems) {
        ttHeader.textContent = poly.label.toUpperCase().replace('-', ' ');
        ttDamage.textContent = poly.type === 'damage' ? poly.label : 'Body Panel Frame';
        ttConf.textContent = `${(poly.confidence * 100).toFixed(1)}%`;

        let costText = 'Included in panel overhaul';
        if (poly.line_item_index !== undefined && lineItems && lineItems[poly.line_item_index]) {
            const item = lineItems[poly.line_item_index];
            costText = `AED ${item.median_cost_aed.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
        }
        ttCost.textContent = costText;

        canvasTooltip.classList.remove('hidden');
        updateTooltipPos(event);
    }

    function updateTooltipPos(event) {
        if (!canvasTooltip || !canvasViewport) return;
        const vRect = canvasViewport.getBoundingClientRect();
        const ttWidth = canvasTooltip.offsetWidth || 180;
        const ttHeight = canvasTooltip.offsetHeight || 100;

        let x = event.clientX - vRect.left + 14;
        let y = event.clientY - vRect.top - 10;

        // Boundary Clamping: never overflow viewport edges
        if (x + ttWidth > vRect.width - 12) {
            x = event.clientX - vRect.left - ttWidth - 14;
        }
        x = Math.max(10, Math.min(vRect.width - ttWidth - 10, x));

        if (y + ttHeight > vRect.height - 12) {
            y = event.clientY - vRect.top - ttHeight - 10;
        }
        y = Math.max(10, Math.min(vRect.height - ttHeight - 10, y));

        canvasTooltip.style.left = `${x}px`;
        canvasTooltip.style.top = `${y}px`;
    }

    function hideTooltip() {
        if (canvasTooltip) {
            canvasTooltip.classList.add('hidden');
        }
    }

    // =========================================================================
    // 9. True Bidirectional Hover Synchronization
    // =========================================================================
    function highlightPolygonAndRow(polygonId, isHighlighted) {
        if (!polygonId) return;

        // Highlight matching SVG polygon
        const polyEl = canvasSvg.querySelector(`[data-id="${polygonId}"]`);
        if (polyEl) {
            if (isHighlighted) {
                polyEl.classList.add('is-highlighted');
            } else {
                polyEl.classList.remove('is-highlighted');
            }
        }

        // Highlight matching damage table row
        const rowEl = tableBody.querySelector(`[data-poly-id="${polygonId}"]`);
        if (rowEl) {
            if (isHighlighted) {
                rowEl.classList.add('is-highlighted');
                rowEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            } else {
                rowEl.classList.remove('is-highlighted');
            }
        }
    }

    function showTooltipForPolygonId(polygonId) {
        if (!state.lastAnalysisData || !state.lastAnalysisData.polygons) return;
        const poly = state.lastAnalysisData.polygons.find(p => p.id === polygonId);
        if (!poly) return;

        const polyEl = canvasSvg.querySelector(`[data-id="${polygonId}"]`);
        if (!polyEl) return;

        const pRect = polyEl.getBoundingClientRect();
        const clientX = pRect.left + pRect.width / 2;
        const clientY = pRect.top + pRect.height / 2;

        showTooltip({ clientX, clientY }, poly, state.lastAnalysisData.line_items);
    }

    // =========================================================================
    // 10. Itemized Cost Table & Bidirectional Binding
    // =========================================================================
    function renderCostTable(lineItems) {
        if (!lineItems || lineItems.length === 0) {
            tableBody.innerHTML = `
                <tr class="empty-row">
                    <td colspan="6">No visible collision damage associated with recognized body panels.</td>
                </tr>
            `;
            return;
        }

        tableBody.innerHTML = lineItems.map((item, idx) => {
            const polyId = item.damage_polygon_id || '';
            const actionClass = item.action === 'REPLACE' ? 'action-replace' : 'action-repair';
            return `
                <tr data-poly-id="${polyId}" class="table-row-item">
                    <td class="font-mono tabular-nums">${idx + 1}</td>
                    <td>
                        <strong>${escapeHtml(item.part_name)}</strong>
                        ${item.is_structural ? '<span class="pill-badge pill-abstain">STRUCTURAL</span>' : ''}
                    </td>
                    <td>${escapeHtml(item.damage_type)}</td>
                    <td><span class="action-pill ${actionClass}">${item.action}</span></td>
                    <td class="font-mono tabular-nums">${item.formatted_range}</td>
                    <td class="font-mono tabular-nums"><strong>AED ${item.median_cost_aed.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong></td>
                </tr>
            `;
        }).join('');

        // Attach bidirectional hover on table rows
        tableBody.querySelectorAll('.table-row-item').forEach(row => {
            const polyId = row.getAttribute('data-poly-id');
            if (!polyId) return;

            row.addEventListener('mouseenter', () => {
                highlightPolygonAndRow(polyId, true);
                showTooltipForPolygonId(polyId);
            });

            row.addEventListener('mouseleave', () => {
                highlightPolygonAndRow(polyId, false);
                hideTooltip();
            });
        });
    }

    function escapeHtml(str) {
        if (!str) return '';
        return str.replace(/[&<>"']/g, m => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        }[m]));
    }

    // =========================================================================
    // 11. Policy Guidance Clauses
    // =========================================================================
    function renderPolicyClauses(clauses) {
        if (!clauses || clauses.length === 0) {
            policyClausesContainer.innerHTML = '<p class="empty-hint">No specific statutory exclusions triggered.</p>';
            return;
        }

        policyClausesContainer.innerHTML = clauses.map(c => `
            <div class="policy-card">
                <div class="policy-card-top">
                    <span class="policy-article-badge">${escapeHtml(c.article)}</span>
                    <span class="policy-score font-mono">Relevance: ${(c.relevance_score * 100).toFixed(0)}%</span>
                </div>
                <h4 class="policy-title">${escapeHtml(c.title)}</h4>
                <p class="policy-summary">${escapeHtml(c.rule_summary)}</p>
                <div class="policy-legal-quote">"${escapeHtml(c.statutory_text)}"</div>
            </div>
        `).join('');
    }

    // =========================================================================
    // 12. Instant Real-Time Recalculate (<5ms Endpoint Integration)
    // =========================================================================
    async function triggerRecalculate() {
        if (!state.lastAnalysisData) return;

        const currentMedian = state.lastAnalysisData.financials.repair_cost_median_aed;
        const currentAcv = parseFloat(inputAcv.value) || 120000;
        const currentThresh = parseFloat(sliderThreshold.value) || 50;
        const currentJurisdiction = selectJurisdiction.value;
        const hasItems = state.lastAnalysisData.line_items.length > 0;
        const structuralFlag = state.lastAnalysisData.financials.structural_risk_flag;

        const startRecalc = performance.now();

        try {
            const resp = await fetch('/api/recalculate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    repair_cost_median_aed: currentMedian,
                    acv_aed: currentAcv,
                    jurisdiction: currentJurisdiction,
                    custom_threshold: currentThresh,
                    structural_risk_flag: structuralFlag,
                    has_line_items: hasItems
                })
            });

            if (resp.ok) {
                const rec = await resp.json();
                const duration = Math.round(performance.now() - startRecalc);
                if (latencyVal) {
                    latencyVal.textContent = `${duration}ms RECALC`;
                }

                // Update Triage Banner
                const color = rec.status_color || 'emerald';
                triageBanner.className = `triage-banner status-${color}`;
                triageIcon.innerHTML = STATUS_ICONS[color] || STATUS_ICONS.emerald;
                triageHeadline.textContent = rec.headline;
                triageSummary.textContent = rec.summary_reason;
                triageAction.textContent = rec.recommended_action;

                // Update Loss Ratio Gauge
                const ratio = Math.min(100.0, Math.max(0.0, rec.financials.loss_ratio_pct));
                gaugeLossRatio.textContent = `${ratio.toFixed(1)}%`;
                const circumference = 314.159;
                const offset = circumference - (ratio / 100.0) * circumference;
                gaugeBar.style.strokeDashoffset = offset;
                gaugeBar.style.stroke = color === 'emerald' ? '#10B981' : (color === 'ruby' ? '#F43F5E' : '#F59E0B');

                // Update Telemetry KPIs
                kpiAcv.textContent = `AED ${rec.financials.acv_aed.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                kpiThreshold.textContent = `${rec.financials.threshold_pct.toFixed(1)}%`;

                // Update state copy
                state.lastAnalysisData.financials.acv_aed = rec.financials.acv_aed;
                state.lastAnalysisData.financials.loss_ratio_pct = rec.financials.loss_ratio_pct;
                state.lastAnalysisData.financials.threshold_pct = rec.financials.threshold_pct;
                state.lastAnalysisData.financials.is_total_loss = rec.financials.is_total_loss;

                populateAppraisalReport(state.lastAnalysisData);
            }
        } catch (err) {
            console.error('Recalculation error:', err);
        }
    }

    // =========================================================================
    // 13. Layer Visibility Toggles
    // =========================================================================
    document.querySelectorAll('.toggle-pill').forEach(pill => {
        pill.addEventListener('click', () => {
            const layer = pill.getAttribute('data-layer');
            state.activeLayers[layer] = !state.activeLayers[layer];
            if (state.activeLayers[layer]) {
                pill.classList.add('active');
            } else {
                pill.classList.remove('active');
            }
            applyLayerVisibility();
        });
    });

    function applyLayerVisibility() {
        canvasSvg.querySelectorAll('.svg-part').forEach(el => {
            el.style.display = state.activeLayers.parts ? 'block' : 'none';
        });
        canvasSvg.querySelectorAll('.svg-damage').forEach(el => {
            el.style.display = state.activeLayers.damages ? 'block' : 'none';
        });
    }

    // =========================================================================
    // 14. Adjuster Appraisal Survey Report (Executive Modal & Printout)
    // =========================================================================
    function populateAppraisalReport(data) {
        if (!data) return;

        if (rptClaimId) rptClaimId.textContent = state.claimReferenceId;
        if (rptDate) rptDate.textContent = new Date().toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
        if (rptBrand) rptBrand.textContent = selectBrand.value;

        const outcomeText = data.triage.headline;
        if (rptVerdictBadge) rptVerdictBadge.textContent = outcomeText;

        if (rptAcv) rptAcv.textContent = `AED ${data.financials.acv_aed.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        if (rptRepair) rptRepair.textContent = `AED ${data.financials.repair_cost_median_aed.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        if (rptLossRatio) rptLossRatio.textContent = `${data.financials.loss_ratio_pct.toFixed(2)}%`;
        if (rptThreshold) rptThreshold.textContent = `${data.financials.threshold_pct.toFixed(2)}%`;
        if (rptStatementText) rptStatementText.textContent = data.triage.summary_reason;

        // Render report line items
        if (rptTableBody) {
            if (data.line_items && data.line_items.length > 0) {
                rptTableBody.innerHTML = data.line_items.map((item, idx) => `
                    <tr>
                        <td class="font-mono tabular-nums">${idx + 1}</td>
                        <td><strong>${escapeHtml(item.part_name)}</strong> ${item.is_structural ? '(Structural Frame)' : ''}</td>
                        <td>${escapeHtml(item.damage_type)}</td>
                        <td>${item.action}</td>
                        <td class="font-mono tabular-nums">${item.formatted_range}</td>
                        <td class="font-mono tabular-nums"><strong>AED ${item.median_cost_aed.toLocaleString('en-US', { minimumFractionDigits: 2 })}</strong></td>
                    </tr>
                `).join('');
            } else {
                rptTableBody.innerHTML = '<tr><td colspan="6" class="text-center">No active repair line items identified.</td></tr>';
            }
        }

        // Render primary regulatory clause
        if (data.policy_guidance && data.policy_guidance.length > 0) {
            const topClause = data.policy_guidance[0];
            if (rptClauseTitle) rptClauseTitle.textContent = `${topClause.title} — ${topClause.article}`;
            if (rptClauseText) rptClauseText.textContent = `"${topClause.statutory_text}"`;
        }
    }

    if (btnOpenAppraisal) {
        btnOpenAppraisal.addEventListener('click', () => {
            if (!state.lastAnalysisData) {
                alert('Please run an inspection or select a scenario before generating the survey appraisal.');
                return;
            }
            populateAppraisalReport(state.lastAnalysisData);
            adjusterModalBackdrop.classList.remove('hidden');
        });
    }

    if (btnCloseModal) {
        btnCloseModal.addEventListener('click', () => {
            adjusterModalBackdrop.classList.add('hidden');
        });
    }

    if (adjusterModalBackdrop) {
        adjusterModalBackdrop.addEventListener('click', (e) => {
            if (e.target === adjusterModalBackdrop) {
                adjusterModalBackdrop.classList.add('hidden');
            }
        });
    }

    if (btnModalPrint) {
        btnModalPrint.addEventListener('click', () => {
            window.print();
        });
    }

    if (btnPrintReport) {
        btnPrintReport.addEventListener('click', () => {
            if (!state.lastAnalysisData) {
                alert('Please run an inspection before printing the appraisal report.');
                return;
            }
            populateAppraisalReport(state.lastAnalysisData);
            window.print();
        });
    }

    if (btnExportJson) {
        btnExportJson.addEventListener('click', () => {
            if (!state.lastAnalysisData) {
                alert('Please run an analysis before exporting data.');
                return;
            }
            const exportPayload = {
                claim_reference: state.claimReferenceId,
                timestamp: new Date().toISOString(),
                platform: 'ClaimLens Insurtech Cockpit v2.4',
                regulatory_standard: 'CBUAE Unified Motor Vehicle Insurance Policy Standard',
                ...state.lastAnalysisData
            };
            const blob = new Blob([JSON.stringify(exportPayload, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `ClaimLens_Appraisal_${state.claimReferenceId}_${Date.now()}.json`;
            a.click();
            URL.revokeObjectURL(url);
        });
    }
});
