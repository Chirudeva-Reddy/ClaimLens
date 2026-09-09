// Run with: playwright-cli open http://localhost:8000 && playwright-cli run-code --filename scripts/frontend-smoke.js
async (page) => {
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const check = (condition, message) => { if (!condition) throw new Error(message); };
    const text = selector => page.locator(selector).textContent();
    await page.setViewportSize({width: 1440, height: 900});
    // A previous run that threw can leave emulation on, which would poison this one.
    await page.emulateMedia({media: 'screen', reducedMotion: null});
    await page.reload();

    // Landing sequence: preloader, then the pinned lens story.
    await page.waitForFunction(() => !document.getElementById('preloader'), null, {timeout: 20000});
    // A reload restores the previous scroll position; the sequence starts at the top.
    await page.evaluate(() => window.__claimlensLenis?.scrollTo(0, {immediate: true}));
    await page.waitForTimeout(500);
    const wordOpacity = () => page.locator('.lens-wordmark span').first().evaluate(el => Number(getComputedStyle(el).opacity));
    const minWordOpacity = () => page.evaluate(() => Math.min(...Array.from(document.querySelectorAll('.lens-wordmark span')).map(el => Number(getComputedStyle(el).opacity))));
    const maxWordOpacity = () => page.evaluate(() => Math.max(...Array.from(document.querySelectorAll('.lens-wordmark span')).map(el => Number(getComputedStyle(el).opacity))));

    check(await page.locator('.hero-copy').evaluate(el => getComputedStyle(el).opacity) === '1', 'Hero copy stayed hidden');
    check(await maxWordOpacity() === 0, 'Wordmark showed before the scroll revealed it');

    const seqEnd = await page.evaluate(() => ScrollTrigger.getAll()[0].end);
    await page.evaluate(e => window.__claimlensLenis.scrollTo(e * 0.6, {immediate: true}), seqEnd);
    await page.waitForTimeout(700);
    check(await minWordOpacity() === 1, 'Wordmark never resolved inside the glass');
    check(await page.locator('#hero-curtain').evaluate(el => getComputedStyle(el).maskImage.includes('radial-gradient')), 'Curtain lost its aperture mask');

    await page.evaluate(e => window.__claimlensLenis.scrollTo(e, {immediate: true}), seqEnd);
    await page.waitForTimeout(900);
    const hole = await page.locator('#hero-curtain').evaluate(el => parseFloat(getComputedStyle(el).getPropertyValue('--hole')));
    check(hole > Math.hypot(1440, 900) / 2, `Aperture never covered the viewport (${hole}px)`);
    check(await page.locator('.app-header').evaluate(el => getComputedStyle(el).opacity) === '1', 'Header never returned after the reveal');
    check((await page.locator('#project-heading').boundingBox()).y > 0, 'Reveal did not land on the project section');

    // Bi-directional scroll: scrolling back up to 0.55 restores the wordmark inside the glass.
    await page.evaluate(e => window.__claimlensLenis.scrollTo(e * 0.55, {immediate: true}), seqEnd);
    await page.waitForTimeout(600);
    check(await minWordOpacity() > 0.95, 'Wordmark did not persist when scrolling back up into the lens');

    // Scrolling back up to the top restores the headline and hides the wordmark.
    await page.evaluate(() => window.__claimlensLenis.scrollTo(0, {immediate: true}));
    await page.waitForTimeout(500);
    check(await maxWordOpacity() === 0, 'Wordmark stayed visible at hero start');
    check(await page.locator('.hero-copy').evaluate(el => getComputedStyle(el).opacity) === '1', 'Hero copy did not return at top');

    await page.locator('#btn-hero-demo').click();
    await page.waitForFunction(() => document.querySelector('#triage-headline').textContent === 'CONSTRUCTIVE TOTAL LOSS REVIEW');
    await page.evaluate(() => window.__claimlensLenis.scrollTo(0, {immediate: true}));

    await page.locator('#btn-case-a').click();
    await page.waitForFunction(() => !document.querySelector('#btn-open-appraisal').disabled);
    check(await text('#triage-headline') === 'ECONOMICALLY REPAIRABLE', 'Case A verdict');
    check(await page.locator('.svg-polygon').count() > 0, 'Evidence overlay missing');

    // Figures travel rather than snap, and results arrive in sequence.
    const travelled = await page.evaluate(async () => {
        const el = document.getElementById('kpi-repair-cost');
        const waitFor = (predicate) => new Promise(resolve => {
            const poll = setInterval(() => { if (predicate()) { clearInterval(poll); resolve(); } }, 20);
        });
        const seen = new Set();
        const sampler = setInterval(() => seen.add(el.textContent), 40);
        document.getElementById('btn-case-b').click();
        // The run has to start before it can finish, or this resolves against
        // the previous result.
        await waitFor(() => el.classList.contains('skeleton'));
        await waitFor(() => !el.classList.contains('skeleton'));
        await new Promise(r => setTimeout(r, 700));
        clearInterval(sampler);
        return [...seen].filter(v => v && v !== '\u2014' && !/^\s*$/.test(v)).length;
    });
    check(travelled > 3, `Repair figure snapped instead of travelling (${travelled} frames)`);
    check(await page.locator('#table-body tr.table-row-item').first().evaluate(el => el.classList.contains('enters')), 'Line items did not cascade in');
    check(await page.locator('.svg-polygon').first().evaluate(el => el.classList.contains('traces')), 'Detections did not trace themselves');
    await page.locator('#btn-case-a').click();
    await page.waitForFunction(() => !document.querySelector('#btn-open-appraisal').disabled);
    await page.waitForFunction(() => !document.getElementById('kpi-repair-cost').classList.contains('skeleton'));

    await page.locator('#input-acv').fill('1000');
    await page.waitForFunction(() => document.querySelector('#triage-headline').textContent === 'CONSTRUCTIVE TOTAL LOSS REVIEW');
    check(await text('#rpt-verdict-badge') === await text('#triage-headline'), 'Report verdict is stale');
    // The figure animates to its value, so wait for it to settle rather than
    // reading it mid-flight.
    await page.waitForFunction(() => parseFloat(document.querySelector('#gauge-loss-ratio').textContent) > 100,
        null, {timeout: 4000}).catch(() => { throw new Error('Loss ratio was capped'); });
    await page.locator('#select-jurisdiction').selectOption('uk_60');
    await page.waitForFunction(() => document.querySelector('#kpi-threshold').textContent === '60.0%');

    await page.locator('#btn-open-appraisal').click();
    check(await page.locator('#btn-close-modal').evaluate(el => el === document.activeElement), 'Dialog focus');
    await page.keyboard.press('Tab');
    check(await page.locator('#btn-modal-print').evaluate(el => el === document.activeElement), 'Dialog focus trap');
    await page.keyboard.press('Escape');
    check(await page.locator('#adjuster-modal-backdrop').isHidden(), 'Escape did not close report');
    check(await page.locator('#btn-open-appraisal').evaluate(el => el === document.activeElement), 'Focus not restored');
    await page.emulateMedia({ media: 'print' });
    check(await page.locator('main').isHidden(), 'Dashboard leaks into print');
    check(await page.locator('.printable-appraisal').isVisible(), 'Report missing from print');
    await page.emulateMedia({ media: 'screen' });

    const downloadPromise = page.waitForEvent('download');
    await page.locator('#btn-export-json').click();
    const download = await downloadPromise;
    check(download.suggestedFilename().endsWith('.json'), 'JSON export missing');
    await download.saveAs('output/playwright/report.json');

    await page.locator('#btn-case-b').click();
    await page.waitForFunction(() => !document.querySelector('#btn-open-appraisal').disabled);
    check(await text('#triage-headline') === 'CONSTRUCTIVE TOTAL LOSS REVIEW', 'Case B verdict');
    await page.locator('#btn-case-c').click();
    await page.waitForFunction(() => !document.querySelector('#btn-open-appraisal').disabled);
    const structuralVerdict = await text('#triage-headline');
    await page.locator('#input-acv').fill('250000');
    await page.waitForFunction(() => document.querySelector('#kpi-acv').textContent.includes('250,000'));
    check(await text('#triage-headline') === structuralVerdict, 'Simulation removed safe abstention');

    await page.locator('#select-brand').selectOption('Nissan');
    check(await page.locator('#btn-open-appraisal').isDisabled(), 'Brand change retained stale appraisal');
    check(await page.locator('.svg-polygon').count() === 0, 'Brand change retained old overlays');
    await page.locator('#image-file-input').setInputFiles('scripts/tiny.png');
    await page.locator('#btn-run-inspection').click();
    await page.waitForFunction(() => !document.querySelector('#btn-open-appraisal').disabled);
    check((await text('#triage-headline')).includes('REJECTED'), 'Tiny photo was not rejected');
    check(await page.locator('#canvas-wrapper').isHidden(), 'Rejected evidence retained old canvas');
    check((await text('#rpt-quality-status')).includes('rejected'), 'Report claims quality gate passed');
    check((await text('#rpt-clause-title')).includes('not established'), 'Old policy clause retained');
    await page.locator('#input-acv').fill('50000');
    await page.waitForTimeout(250);
    check((await text('#triage-headline')).includes('REJECTED'), 'Recalculation replaced rejection');

    await page.setViewportSize({width: 375, height: 812});
    await page.evaluate(() => { window.scrollTo(0, 0); window.__claimlensLenis?.scrollTo(0, {immediate: true}); });
    await page.waitForTimeout(800);  // gsap.matchMedia tears the desktop sequence down
    check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Mobile page overflows');
    check(await page.locator('.lens-hud-row').first().evaluate(el => el.getBoundingClientRect().height) < 20, 'Lens readout wraps on mobile');
    check(await page.locator('.hero-runway').evaluate(el => getComputedStyle(el).display) === 'none', 'Scroll runway left an empty gap on mobile');
    check(await page.locator('.lens-wordmark').evaluate(el => getComputedStyle(el).display) === 'none', 'Wordmark overlaps the readout on mobile');
    check(await page.locator('.lens-hud').evaluate(el => Number(getComputedStyle(el).opacity)) === 1, 'Readout hidden on mobile');
    const heroTitleTop = await page.locator('.hero-title').evaluate(el => el.getBoundingClientRect().top);
    const headerBottom = await page.locator('.app-header').evaluate(el => el.getBoundingClientRect().bottom);
    check(heroTitleTop >= headerBottom, `Mobile hero title is covered by header (${heroTitleTop} < ${headerBottom})`);
    await page.screenshot({path: 'output/playwright/mobile.png', fullPage: true});
    await page.setViewportSize({width: 1440, height: 1000});
    await page.locator('#btn-case-a').click();
    await page.waitForFunction(() => !document.querySelector('#btn-open-appraisal').disabled);
    await page.screenshot({path: 'output/playwright/desktop.png', fullPage: true});

    // 2K resolution (2560x1440) viewport check
    await page.setViewportSize({width: 2560, height: 1440});
    await page.waitForTimeout(600);
    check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), '2K page overflows horizontally');
    const lensWidth = await page.locator('.lens').evaluate(el => el.getBoundingClientRect().width);
    check(lensWidth >= 600, `2K lens size too small (${lensWidth}px)`);
    const canvasH = await page.locator('#canvas-viewport').evaluate(el => el.getBoundingClientRect().height);
    check(canvasH >= 640, `2K canvas height too small (${canvasH}px)`);
    const mainWidth = await page.locator('.main-container').evaluate(el => el.getBoundingClientRect().width);
    check(mainWidth >= 1800, `2K main container did not expand (${mainWidth}px)`);
    await page.screenshot({path: 'output/playwright/desktop-2k.png'});
    // Reduced motion must land on the finished state, not a half-played one.
    await page.emulateMedia({reducedMotion: 'reduce'});
    await page.reload();
    await page.waitForTimeout(900);
    check(await page.locator('.lens-wordmark span').first().evaluate(el => Number(getComputedStyle(el).opacity)) === 1, 'Reduced motion hid the wordmark');
    check(await page.locator('.hero-copy').evaluate(el => getComputedStyle(el).opacity) === '1', 'Reduced motion hid the hero copy');
    check(await page.locator('.app-header').evaluate(el => getComputedStyle(el).opacity) === '1', 'Reduced motion hid the header');
    check(await page.locator('.reveal-on-scroll').first().evaluate(el => getComputedStyle(el).opacity) === '1', 'Reduced motion hid the cockpit');
    // No analysis has run on this reload, so test the rule itself.
    const cascadeRule = await page.evaluate(() => {
        const row = document.createElement('tr');
        row.className = 'table-row-item enters';
        document.getElementById('table-body').appendChild(row);
        const name = getComputedStyle(row).animationName;
        row.remove();
        return name;
    });
    check(cascadeRule === 'none', 'Reduced motion still cascades the line items');
    await page.emulateMedia({reducedMotion: null});

    check(errors.length === 0, `Browser errors: ${errors.join('; ')}`);
    console.log('Frontend smoke passed: hero, scenarios, recalculation, report, export, rejection, keyboard, reduced motion and mobile.');
}
