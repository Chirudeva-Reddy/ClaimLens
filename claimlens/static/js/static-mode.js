/* ==========================================================================
   Static demo shim, loaded only in the published GitHub Pages build.

   Pages serves files; it cannot run the models. So the three validation
   scenarios replay responses frozen from a real pipeline run
   (scripts/bake-site-fixtures.py), and the threshold simulation is mirrored
   from claimlens/api.py::recalculate_loss_ratio so the sliders stay live.

   Anything that genuinely needs inference (uploading your own photograph,
   switching the OEM pricing tier) is disabled here and works when the app is
   run locally.
   ========================================================================== */

(() => {
    const PRESETS = { uae_50: 50, us_70: 70, us_75: 75, uk_60: 60 };
    const money = (n) => n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const round2 = (n) => Math.round(n * 100) / 100;

    // Mirrors claimlens/api.py::recalculate_loss_ratio. Keep the two in step.
    function triage({ repair, acv, jurisdiction, customThreshold, structural, hasItems }) {
        const threshold = jurisdiction === 'custom' ? customThreshold : PRESETS[jurisdiction];
        const ratio = (repair / acv) * 100;
        let outcome, headline, color, icon, summary, action;

        if (structural) {
            outcome = 'INSUFFICIENT_EVIDENCE_INSPECTION_REQUIRED';
            headline = 'PHYSICAL TEARDOWN INSPECTION MANDATED';
            color = 'amber'; icon = '⚠️';
            summary = 'Potential unibody/structural damage detected. Camera-only estimation cannot guarantee chassis integrity.';
            action = 'Dispatch accredited field appraiser for laser chassis alignment check.';
        } else if (!hasItems) {
            outcome = 'INSUFFICIENT_EVIDENCE_INSPECTION_REQUIRED';
            headline = 'INSUFFICIENT EVIDENCE DETECTED';
            color = 'amber'; icon = '⚠️';
            summary = 'No visible collision damage associated with recognized body panels.';
            action = 'Request supplementary collision documentation or physical inspection.';
        } else if (ratio >= threshold) {
            outcome = 'PROBABLE_TOTAL_LOSS_REVIEW';
            headline = 'CONSTRUCTIVE TOTAL LOSS REVIEW';
            color = 'ruby'; icon = '🚨';
            summary = `Estimated repair cost of AED ${money(repair)} represents ${ratio.toFixed(1)}% of Pre-Accident Cash Value (threshold: ${threshold.toFixed(0)}%).`;
            action = 'Initiate salvage valuation and total-loss settlement workflow.';
        } else {
            outcome = 'PROBABLY_REPAIRABLE';
            headline = 'ECONOMICALLY REPAIRABLE';
            color = 'emerald'; icon = '✅';
            summary = `Estimated visible repair cost of AED ${money(repair)} represents ${ratio.toFixed(1)}% of Pre-Accident Cash Value (threshold: ${threshold.toFixed(0)}%).`;
            action = 'Issue digital repair authorization to certified bodyshop network.';
        }

        return {
            outcome, headline, status_color: color, icon,
            summary_reason: summary, recommended_action: action,
            financials: {
                repair_cost_median_aed: round2(repair),
                acv_aed: round2(acv),
                loss_ratio_pct: round2(ratio),
                threshold_pct: round2(threshold),
                is_total_loss: outcome === 'PROBABLE_TOTAL_LOSS_REVIEW',
                currency: 'AED',
            },
        };
    }

    const json = (body, status = 200) =>
        new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

    const nativeFetch = window.fetch.bind(window);

    window.fetch = async (input, init = {}) => {
        const url = typeof input === 'string' ? input : input.url;

        if (url.includes('/api/recalculate')) {
            const req = JSON.parse(init.body);
            return json(triage({
                repair: req.repair_cost_median_aed,
                acv: req.acv_aed,
                jurisdiction: req.jurisdiction,
                customThreshold: req.custom_threshold,
                structural: req.structural_risk_flag,
                hasItems: req.has_line_items,
            }));
        }

        if (url.includes('/api/analyze')) {
            const form = init.body;
            const scenarioId = form.get('scenario_id');
            if (!scenarioId) {
                return json({ detail: 'This published demo replays three frozen inspections. Run ClaimLens locally to inspect your own photograph.' }, 400);
            }
            const res = await nativeFetch(`./fixtures/${scenarioId}.json`);
            const data = await res.json();
            // Re-decide against whatever the operator has dialled in.
            const decided = triage({
                repair: data.financials.repair_cost_median_aed,
                acv: Number(form.get('acv')),
                jurisdiction: form.get('jurisdiction'),
                customThreshold: Number(form.get('custom_threshold')),
                structural: data.financials.structural_risk_flag,
                hasItems: data.line_items.length > 0,
            });
            data.triage = {
                outcome: decided.outcome, headline: decided.headline,
                status_color: decided.status_color, icon: decided.icon,
                summary_reason: decided.summary_reason, recommended_action: decided.recommended_action,
            };
            Object.assign(data.financials, decided.financials);
            return json(data);
        }

        return nativeFetch(input, init);
    };

    // Controls that need inference are disabled rather than left to fail. The
    // cockpit re-enables every form control after each run, so hold these.
    document.addEventListener('DOMContentLoaded', () => {
        const note = 'Available when ClaimLens runs locally, where the models are loaded.';
        const locked = ['select-brand', 'image-file-input']
            .map((id) => document.getElementById(id))
            .filter(Boolean);

        const hold = () => locked.forEach((el) => {
            if (!el.disabled) el.disabled = true;
            el.title = note;
        });

        hold();
        const keeper = new MutationObserver(hold);
        locked.forEach((el) => keeper.observe(el, { attributes: true, attributeFilter: ['disabled'] }));
    });
})();
