// Run with: playwright-cli open http://localhost:8000 && playwright-cli run-code --filename scripts/frontend-smoke.js
async (page) => {
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const check = (condition, message) => { if (!condition) throw new Error(message); };
    const text = selector => page.locator(selector).textContent();
    await page.setViewportSize({width: 1440, height: 900});
    await page.reload();

    // Landing sequence: preloader, then the pinned lens story.
    await page.waitForFunction(() => !document.getElementById('preloader'), null, {timeout: 20000});
    // A reload restores the previous scroll position; the sequence starts at the top.
    await page.evaluate(() => window.__claimlensLenis?.scrollTo(0, {immediate: true}));
    await page.waitForTimeout(500);
    const wordOpacity = () => page.locator('.lens-wordmark span').first().evaluate(el => Number(getComputedStyle(el).opacity));
    check(await page.locator('.hero-copy').evaluate(el => getComputedStyle(el).opacity) === '1', 'Hero copy stayed hidden');
    check(await wordOpacity() === 0, 'Wordmark showed before the scroll revealed it');

    const seqEnd = await page.evaluate(() => ScrollTrigger.getAll()[0].end);
    await page.evaluate(e => window.__claimlensLenis.scrollTo(e * 0.6, {immediate: true}), seqEnd);
    await page.waitForTimeout(700);
    check(await wordOpacity() === 1, 'Wordmark never resolved inside the glass');
    check(await page.locator('#hero-curtain').evaluate(el => getComputedStyle(el).maskImage.includes('radial-gradient')), 'Curtain lost its aperture mask');

    await page.evaluate(e => window.__claimlensLenis.scrollTo(e, {immediate: true}), seqEnd);
    await page.waitForTimeout(900);
    const hole = await page.locator('#hero-curtain').evaluate(el => parseFloat(getComputedStyle(el).getPropertyValue('--hole')));
    check(hole > Math.hypot(1440, 900) / 2, `Aperture never covered the viewport (${hole}px)`);
    check(await page.locator('.app-header').evaluate(el => getComputedStyle(el).opacity) === '1', 'Header never returned after the reveal');
    check((await page.locator('#project-heading').boundingBox()).y > 0, 'Reveal did not land on the project section');

    await page.evaluate(() => window.__claimlensLenis.scrollTo(0, {immediate: true}));
    await page.waitForTimeout(400);
    await page.locator('#btn-hero-demo').click();
    await page.waitForFunction(() => document.querySelector('#triage-headline').textContent === 'CONSTRUCTIVE TOTAL LOSS REVIEW');
    await page.evaluate(() => window.__claimlensLenis.scrollTo(0, {immediate: true}));

    await page.locator('#btn-case-a').click();
    await page.waitForFunction(() => !document.querySelector('#btn-open-appraisal').disabled);
    check(await text('#triage-headline') === 'ECONOMICALLY REPAIRABLE', 'Case A verdict');
    check(await page.locator('.svg-polygon').count() > 0, 'Evidence overlay missing');

    await page.locator('#input-acv').fill('1000');
    await page.waitForFunction(() => document.querySelector('#triage-headline').textContent === 'CONSTRUCTIVE TOTAL LOSS REVIEW');
    check(await text('#rpt-verdict-badge') === await text('#triage-headline'), 'Report verdict is stale');
    check(parseFloat(await text('#gauge-loss-ratio')) > 100, 'Loss ratio was capped');
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
    await page.waitForTimeout(800);  // gsap.matchMedia tears the desktop sequence down
    check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Mobile page overflows');
    check(await page.locator('.lens-hud-row').first().evaluate(el => el.getBoundingClientRect().height) < 20, 'Lens readout wraps on mobile');
    check(await page.locator('.hero-runway').evaluate(el => getComputedStyle(el).display) === 'none', 'Scroll runway left an empty gap on mobile');
    check(await page.locator('.lens-wordmark').evaluate(el => getComputedStyle(el).display) === 'none', 'Wordmark overlaps the readout on mobile');
    check(await page.locator('.lens-hud').evaluate(el => Number(getComputedStyle(el).opacity)) === 1, 'Readout hidden on mobile');
    await page.screenshot({path: 'output/playwright/mobile.png', fullPage: true});
    await page.setViewportSize({width: 1440, height: 1000});
    await page.locator('#btn-case-a').click();
    await page.waitForFunction(() => !document.querySelector('#btn-open-appraisal').disabled);
    await page.screenshot({path: 'output/playwright/desktop.png', fullPage: true});
    // Reduced motion must land on the finished state, not a half-played one.
    await page.emulateMedia({reducedMotion: 'reduce'});
    await page.reload();
    await page.waitForTimeout(900);
    check(await page.locator('.lens-wordmark span').first().evaluate(el => Number(getComputedStyle(el).opacity)) === 1, 'Reduced motion hid the wordmark');
    check(await page.locator('.hero-copy').evaluate(el => getComputedStyle(el).opacity) === '1', 'Reduced motion hid the hero copy');
    check(await page.locator('.app-header').evaluate(el => getComputedStyle(el).opacity) === '1', 'Reduced motion hid the header');
    check(await page.locator('.reveal-on-scroll').first().evaluate(el => getComputedStyle(el).opacity) === '1', 'Reduced motion hid the cockpit');
    await page.emulateMedia({reducedMotion: null});

    check(errors.length === 0, `Browser errors: ${errors.join('; ')}`);
    console.log('Frontend smoke passed: hero, scenarios, recalculation, report, export, rejection, keyboard, reduced motion and mobile.');
}
