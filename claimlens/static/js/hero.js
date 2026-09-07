/* ==========================================================================
   ClaimLens hero motion layer.

   Ownership split (Motion and GSAP must never write transforms to the same
   element):
     GSAP + ScrollTrigger -> .lens, .hero-veil   (pinned / scrubbed work)
     Motion               -> .lens-glass clip, wordmark letters, counters,
                             cockpit section reveals
     Lenis                -> smooth scrolling and in-page anchors

   Copy entrance is pure CSS, so the hero still reads correctly if this
   module fails to load.
   ========================================================================== */

import { animate, inView, stagger } from 'https://cdn.jsdelivr.net/npm/motion@13.2.0/+esm';

const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const lens = document.getElementById('hero-lens');
const glass = document.querySelector('.lens-glass');
const letters = document.querySelectorAll('.lens-wordmark span');
const counters = document.querySelectorAll('[data-count-to]');

/* ---------- Static end-state, used under reduced motion ---------- */

function settle() {
    if (glass) glass.style.clipPath = 'circle(52% at 50% 50%)';
    letters.forEach((el) => { el.style.opacity = '1'; el.style.transform = 'none'; el.style.filter = 'none'; });
    counters.forEach((el) => { el.textContent = format(el, Number(el.dataset.countTo)); });
    document.querySelectorAll('.reveal-on-scroll').forEach((el) => {
        el.style.opacity = '1';
        el.style.transform = 'none';
    });
}

function format(el, value) {
    // Whole numbers stay whole; ratios keep one decimal, matching the cockpit readouts.
    return Number.isInteger(Number(el.dataset.countTo)) ? String(Math.round(value)) : value.toFixed(1);
}

/* ---------- Intro: the glass irises open, then the wordmark resolves ---------- */

function playIntro() {
    if (glass) {
        glass.style.clipPath = 'circle(0% at 50% 50%)';
        animate(glass,
            { clipPath: ['circle(0% at 50% 50%)', 'circle(52% at 50% 50%)'] },
            { duration: 0.9, ease: [0.16, 1, 0.3, 1], delay: 0.15 });
    }

    if (letters.length) {
        animate(letters,
            { opacity: [0, 1], y: [18, 0], filter: ['blur(9px)', 'blur(0px)'] },
            { type: 'spring', visualDuration: 0.55, bounce: 0.28, delay: stagger(0.045, { startDelay: 0.7 }) });
    }

    counters.forEach((el) => {
        const target = Number(el.dataset.countTo);
        // Markup carries the true value so a failed module load still reads correctly.
        el.textContent = format(el, 0);
        animate(0, target, {
            duration: 1.4,
            delay: 1.05,
            ease: [0.16, 1, 0.3, 1],
            onUpdate: (v) => { el.textContent = format(el, v); },
        });
    });
}

/* ---------- Scroll reveals for the cockpit below the fold ---------- */

function wireReveals() {
    return inView('.reveal-on-scroll', (el) => {
        animate(el, { opacity: [0, 1], y: [26, 0] }, { duration: 0.62, ease: [0.16, 1, 0.3, 1] });
    }, { amount: 0.15, margin: '0px 0px -8% 0px' });
}

/* ---------- Scroll-linked lens handoff (GSAP owns .lens) ---------- */

function wireScrollScrub() {
    if (!window.gsap || !window.ScrollTrigger || !lens) return null;
    gsap.registerPlugin(ScrollTrigger);

    const mm = gsap.matchMedia();
    mm.add({
        isDesktop: '(min-width: 769px)',
        reduce: '(prefers-reduced-motion: reduce)',
    }, (ctx) => {
        if (ctx.conditions.reduce || !ctx.conditions.isDesktop) return;

        // The lens tracks the reader down the page and hands off to the cockpit.
        gsap.to(lens, {
            yPercent: -14,
            scale: 1.16,
            rotate: -4,
            ease: 'none',
            scrollTrigger: { trigger: '#hero', start: 'top top', end: 'bottom top', scrub: 0.5 },
        });

        gsap.to('.hero-veil', {
            yPercent: 12,
            opacity: 0.04,
            ease: 'none',
            scrollTrigger: { trigger: '#hero', start: 'top top', end: 'bottom top', scrub: 0.5 },
        });
    });
    return mm;
}

/* ---------- Smooth scrolling ---------- */

function wireLenis() {
    if (!window.Lenis || !window.gsap) return null;
    const lenis = new Lenis({ anchors: { offset: -84 } });
    lenis.on('scroll', ScrollTrigger.update);
    const tick = (time) => lenis.raf(time * 1000);
    gsap.ticker.add(tick);
    gsap.ticker.lagSmoothing(0);
    return { lenis, tick };
}

/* ---------- Demo CTA: run a real claim in the cockpit ---------- */

document.getElementById('btn-hero-demo')?.addEventListener('click', () => {
    const cockpit = document.getElementById('cockpit');
    const caseB = document.getElementById('btn-case-b');
    if (window.__claimlensLenis) {
        window.__claimlensLenis.scrollTo(cockpit, { offset: -84 });
    } else {
        cockpit?.scrollIntoView({ behavior: reduceMotion.matches ? 'auto' : 'smooth', block: 'start' });
    }
    caseB?.click();
});

/* ---------- Build / rebuild on preference change ---------- */

let teardown = [];

function build() {
    teardown.splice(0).forEach((fn) => fn());

    if (reduceMotion.matches) {
        delete document.documentElement.dataset.motion;
        settle();
        return;
    }

    document.documentElement.dataset.motion = 'on';
    playIntro();

    const stopReveals = wireReveals();
    if (stopReveals) teardown.push(stopReveals);

    const mm = wireScrollScrub();
    if (mm) teardown.push(() => mm.revert());

    const smooth = wireLenis();
    if (smooth) {
        window.__claimlensLenis = smooth.lenis;
        teardown.push(() => {
            gsap.ticker.remove(smooth.tick);
            smooth.lenis.destroy();
            delete window.__claimlensLenis;
        });
    }

    // Images arrive after layout; ScrollTrigger needs the corrected offsets.
    window.addEventListener('load', () => window.ScrollTrigger?.refresh(), { once: true });
}

build();
reduceMotion.addEventListener('change', build);
