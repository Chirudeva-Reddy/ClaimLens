/**
 * ClaimLens Enterprise Interactive Client
 * Real-time SVG polygon overlay, bidirectional table-canvas synchronization,
 * instant economic recalculation, and CBUAE policy guidance.
 */

document.addEventListener('DOMContentLoaded', () => {
    // State management
    const state = {
        activeScenarioId: null,
        uploadedFile: null,
        lastAnalysisData: null,
        imageDimensions: { width: 1000, height: 1000 },
        activeLayers: { parts: true, damages: true, labels: true }
    };

    // DOM Elements
    const dropzone = document.getElementById('upload-dropzone');
    const fileInput = document.getElementById('image-file-input');
    const dropzoneIdle = document.getElementById('dropzone-idle');
    const dropzonePreview = document.getElementById('dropzone-preview');
    const previewImg = document.getElementById('preview-img');
    const btnClearPreview = document.getElementById('btn-clear-preview');
    const qualityGateBanner = document.getElementById('quality-gate-banner');

    const selectBrand = document.getElementById('select-brand');
    const inputAcv = document.getElementById('input-acv');
    const selectJurisdiction = document.getElementById('select-jurisdiction');
    const sliderThreshold = document.getElementById('slider-threshold');
    const sliderThresholdVal = document.getElementById('slider-threshold-val');
    const btnRunInspection = document.getElementById('btn-run-inspection');
    const btnSpinner = document.getElementById('btn-spinner');

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

    const tableBody = document.getElementById('table-body');
    const assumptionsList = document.getElementById('assumptions-list');
    const policyClausesContainer = document.getElementById('policy-clauses-container');

    // 1. Tab Navigation
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            const targetId = btn.getAttribute('data-tab');
            const targetPane = document.getElementById(targetId);
            if (targetPane) targetPane.classList.add('active');
        });
    });

    // 2. ACV Quick Chips
    document.querySelectorAll('.chip-btn').forEach(chip => {
        chip.addEventListener('click', () => {
            document.querySelectorAll('.chip-btn').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            inputAcv.value = chip.getAttribute('data-val');
            triggerRecalculate();
        });
    });

    inputAcv.addEventListener('input', () => {
        document.querySelectorAll('.chip-btn').forEach(c => c.classList.remove('active'));
        triggerRecalculate();
    });

    // 3. Threshold Slider & Jurisdiction Handling
    sliderThreshold.addEventListener('input', (e) => {
        sliderThresholdVal.textContent = `${e.target.value}%`;
        if (selectJurisdiction.value !== 'custom') {
            selectJurisdiction.value = 'custom';
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

    // 4. File Upload & Dropzone Handling
    dropzone.addEventListener('click', () => {
        if (!state.uploadedFile && !state.activeScenarioId) {
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
        document.querySelectorAll('.scenario-card').forEach(c => c.classList.remove('active-scenario'));

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
        document.querySelectorAll('.scenario-card').forEach(c => c.classList.remove('active-scenario'));
    }

    // 5. Quick-Launch Scenario Buttons
    document.querySelectorAll('.scenario-card').forEach(card => {
        card.addEventListener('click', () => {
            const caseId = card.getAttribute('data-case');
            loadAndRunScenario(caseId);
        });
    });

    async function loadAndRunScenario(caseId) {
        document.querySelectorAll('.scenario-card').forEach(c => c.classList.remove('active-scenario'));
        const activeCard = document.querySelector(`[data-case="${caseId}"]`);
        if (activeCard) activeCard.classList.add('active-scenario');

        state.activeScenarioId = caseId;
        state.uploadedFile = null;

        // Set preset metadata
        if (caseId === 'case_a') {
            selectBrand.value = 'Toyota';
            inputAcv.value = 120000;
            selectJurisdiction.value = 'uae_50';
            sliderThreshold.value = 50;
            sliderThresholdVal.textContent = '50%';
        } else if (caseId === 'case_b') {
            selectBrand.value = 'General Market Standard';
            inputAcv.value = 15000;
            selectJurisdiction.value = 'uae_50';
            sliderThreshold.value = 50;
            sliderThresholdVal.textContent = '50%';
        } else if (caseId === 'case_c') {
            selectBrand.value = 'Toyota';
            inputAcv.value = 85000;
            selectJurisdiction.value = 'uae_50';
            sliderThreshold.value = 50;
            sliderThresholdVal.textContent = '50%';
        }

        // Show image preview
        previewImg.src = `/api/scenarios/${caseId}/image`;
        dropzoneIdle.classList.add('hidden');
        dropzonePreview.classList.remove('hidden');
        qualityGateBanner.classList.add('hidden');

        // Automatically run analysis
        await executeAnalysis();
    }

    // 6. Primary Action Execution
    btnRunInspection.addEventListener('click', async () => {
        await executeAnalysis();
    });

    async function executeAnalysis() {
        if (!state.uploadedFile && !state.activeScenarioId) {
            alert('Please select a collision photograph or click one of the Quick-Launch validation scenarios above.');
            return;
        }

        btnSpinner.classList.remove('hidden');
        btnRunInspection.disabled = true;

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
            state.lastAnalysisData = data;
            renderAnalysisResults(data);

        } catch (err) {
            console.error('Inspection failed:', err);
            alert(`Analysis encountered an error: ${err.message}`);
        } finally {
            btnSpinner.classList.add('hidden');
            btnRunInspection.disabled = false;
        }
    }

    // 7. Render Analysis Results
    function renderAnalysisResults(data) {
        // Quality Gate check
        if (!data.quality_gate.accepted) {
            qualityGateBanner.textContent = `❌ Quality Gate Rejected: ${data.quality_gate.reason}. ${data.quality_gate.actionable_guidance}`;
            qualityGateBanner.className = 'quality-gate-banner rejected';
            qualityGateBanner.classList.remove('hidden');
        } else {
            qualityGateBanner.classList.add('hidden');
        }

        // Triage Banner
        triageBanner.className = `triage-banner status-${data.triage.status_color}`;
        triageIcon.textContent = data.triage.icon;
        triageHeadline.textContent = data.triage.headline;
        triageSummary.textContent = data.triage.summary_reason;
        triageAction.textContent = data.triage.recommended_action;

        // Gauge Ring
        const ratio = Math.min(100.0, Math.max(0.0, data.financials.loss_ratio_pct));
        gaugeLossRatio.textContent = `${ratio.toFixed(1)}%`;
        const circumference = 314.159;
        const offset = circumference - (ratio / 100.0) * circumference;
        gaugeBar.style.strokeDashoffset = offset;
        gaugeBar.style.stroke = data.triage.status_color === 'emerald' ? '#10b981' : (data.triage.status_color === 'ruby' ? '#f43f5e' : '#f59e0b');

        // KPI Cards
        kpiRepairCost.textContent = `AED ${data.financials.repair_cost_median_aed.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        kpiRepairRange.textContent = `Min: AED ${data.financials.repair_cost_min_aed.toLocaleString()} • Max: AED ${data.financials.repair_cost_max_aed.toLocaleString()}`;
        kpiAcv.textContent = `AED ${data.financials.acv_aed.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        kpiThreshold.textContent = `${data.financials.threshold_pct.toFixed(1)}%`;

        // Canvas & SVG Polygons
        if (data.image_meta && data.image_meta.raw_base64) {
            canvasPlaceholder.classList.add('hidden');
            canvasBaseImg.src = data.image_meta.raw_base64;
            state.imageDimensions = {
                width: data.image_meta.width,
                height: data.image_meta.height
            };
            canvasSvg.setAttribute('viewBox', `0 0 ${data.image_meta.width} ${data.image_meta.height}`);
            renderSvgPolygons(data.polygons, data.line_items);
        }

        // Itemized Cost Table
        renderCostTable(data.line_items);

        // Assumptions
        if (data.assumptions) {
            assumptionsList.innerHTML = data.assumptions.map(a => `<li>${a}</li>`).join('');
        }

        // CBUAE Statutory Guidance
        if (data.policy_guidance) {
            renderPolicyClauses(data.policy_guidance);
        }

        // Scroll smoothly to results
        document.getElementById('triage-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // 8. Render SVG Polygons with Bidirectional Highlighting
    function renderSvgPolygons(polygons, lineItems) {
        canvasSvg.innerHTML = '';

        polygons.forEach((poly) => {
            if (!poly.polygon || poly.polygon.length < 3) return;

            const pointsStr = poly.polygon.map(p => `${p[0]},${p[1]}`).join(' ');
            const el = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
            el.setAttribute('points', pointsStr);
            el.setAttribute('data-id', poly.id);
            el.setAttribute('data-type', poly.type);
            el.setAttribute('data-label', poly.label);
            el.setAttribute('data-conf', `${(poly.confidence * 100).toFixed(0)}%`);

            let cssClass = 'svg-polygon ';
            if (poly.type === 'part') {
                cssClass += poly.is_structural ? 'svg-structural' : 'svg-part';
            } else {
                cssClass += poly.is_structural ? 'svg-structural' : 'svg-damage';
            }
            el.setAttribute('class', cssClass);

            // Link to line item
            if (poly.type === 'damage' && poly.line_item_index !== undefined) {
                el.setAttribute('data-line-item-index', poly.line_item_index);
            }

            // Hover events
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

    // 9. Tooltip HUD Management
    function showTooltip(event, poly, lineItems) {
        ttHeader.textContent = poly.label.toUpperCase().replace('-', ' ');
        ttDamage.textContent = poly.type === 'damage' ? poly.label : 'Component Frame';
        ttConf.textContent = `${(poly.confidence * 100).toFixed(1)}%`;

        let costText = 'Included in panel overhaul';
        if (poly.line_item_index !== undefined && lineItems && lineItems[poly.line_item_index]) {
            const item = lineItems[poly.line_item_index];
            costText = `AED ${item.median_cost_aed.toLocaleString()}`;
        }
        ttCost.textContent = costText;

        canvasTooltip.classList.remove('hidden');
        updateTooltipPos(event);
    }

    function updateTooltipPos(event) {
        const rect = canvasViewport.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        canvasTooltip.style.left = `${x}px`;
        canvasTooltip.style.top = `${y}px`;
    }

    function hideTooltip() {
        canvasTooltip.classList.add('hidden');
    }

    // 10. Bidirectional Highlighting
    function highlightPolygonAndRow(polygonId, isHighlighted) {
        // Highlight SVG polygon
        const polyEl = canvasSvg.querySelector(`[data-id="${polygonId}"]`);
        if (polyEl) {
            if (isHighlighted) {
                polyEl.classList.add('is-highlighted');
            } else {
                polyEl.classList.remove('is-highlighted');
            }
        }

        // Highlight matching table row
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

    // 11. Render Itemized Cost Table
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
                    <td class="font-mono">${idx + 1}</td>
                    <td><strong>${item.part_name}</strong> ${item.is_structural ? '<span class="scenario-pill pill-abstain">STRUCTURAL</span>' : ''}</td>
                    <td>${item.damage_type}</td>
                    <td><span class="action-pill ${actionClass}">${item.action}</span></td>
                    <td class="font-mono">${item.formatted_range}</td>
                    <td class="font-mono"><strong>AED ${item.median_cost_aed.toLocaleString('en-US', { minimumFractionDigits: 2 })}</strong></td>
                </tr>
            `;
        }).join('');

        // Attach bidirectional hover on table rows
        tableBody.querySelectorAll('.table-row-item').forEach(row => {
            const polyId = row.getAttribute('data-poly-id');
            if (!polyId) return;

            row.addEventListener('mouseenter', () => {
                highlightPolygonAndRow(polyId, true);
            });

            row.addEventListener('mouseleave', () => {
                highlightPolygonAndRow(polyId, false);
            });
        });
    }

    // 12. Render Policy Guidance
    function renderPolicyClauses(clauses) {
        if (!clauses || clauses.length === 0) {
            policyClausesContainer.innerHTML = '<p class="empty-hint">No specific statutory exclusions triggered.</p>';
            return;
        }

        policyClausesContainer.innerHTML = clauses.map(c => `
            <div class="policy-card">
                <div class="policy-card-top">
                    <span class="policy-article-badge">${c.article}</span>
                    <span class="policy-score">Relevance: ${(c.relevance_score * 100).toFixed(0)}%</span>
                </div>
                <h4 class="policy-title">${c.title}</h4>
                <p class="policy-summary">${c.rule_summary}</p>
                <div class="policy-legal-quote">"${c.statutory_text}"</div>
            </div>
        `).join('');
    }

    // 13. Instant 0ms Recalculate Simulator
    async function triggerRecalculate() {
        if (!state.lastAnalysisData) return;

        const currentMedian = state.lastAnalysisData.financials.repair_cost_median_aed;
        const currentAcv = parseFloat(inputAcv.value) || 120000;
        const currentThresh = parseFloat(sliderThreshold.value) || 50;
        const currentJurisdiction = selectJurisdiction.value;
        const hasItems = state.lastAnalysisData.line_items.length > 0;
        const structuralFlag = state.lastAnalysisData.financials.structural_risk_flag;

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
                triageBanner.className = `triage-banner status-${rec.status_color}`;
                triageIcon.textContent = rec.icon;
                triageHeadline.textContent = rec.headline;
                triageSummary.textContent = rec.summary_reason;
                triageAction.textContent = rec.recommended_action;

                const ratio = Math.min(100.0, Math.max(0.0, rec.financials.loss_ratio_pct));
                gaugeLossRatio.textContent = `${ratio.toFixed(1)}%`;
                const circumference = 314.159;
                const offset = circumference - (ratio / 100.0) * circumference;
                gaugeBar.style.strokeDashoffset = offset;
                gaugeBar.style.stroke = rec.status_color === 'emerald' ? '#10b981' : (rec.status_color === 'ruby' ? '#f43f5e' : '#f59e0b');

                kpiAcv.textContent = `AED ${rec.financials.acv_aed.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
                kpiThreshold.textContent = `${rec.financials.threshold_pct.toFixed(1)}%`;
            }
        } catch (err) {
            console.error('Recalculation error:', err);
        }
    }

    // 14. Layer Toggles
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

    // 15. Export & Print
    document.getElementById('btn-print-report').addEventListener('click', () => {
        window.print();
    });

    document.getElementById('btn-export-json').addEventListener('click', () => {
        if (!state.lastAnalysisData) {
            alert('Please run an analysis before exporting data.');
            return;
        }
        const blob = new Blob([JSON.stringify(state.lastAnalysisData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `ClaimLens_Appraisal_${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
    });
});
