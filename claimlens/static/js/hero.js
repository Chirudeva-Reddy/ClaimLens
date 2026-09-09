/* ==========================================================================
   ClaimLens landing sequence.

   Ownership split (Motion and GSAP must never write transforms to the same
   element):
     GSAP + ScrollTrigger -> the pinned hero: lens, copy layer, curtain mask
     Motion               -> wordmark letters, below-fold section reveals
     Lenis                -> smooth scrolling and in-page anchors

   Scroll story: headline leaves, the wordmark resolves inside the glass,
   then the glass opens past the viewport and the page comes through it.

   Hero copy entrance is pure CSS, so the page still reads if this module
   fails to load.
   ========================================================================== */

import { animate, inView, stagger } from 'https://cdn.jsdelivr.net/npm/motion@13.2.0/+esm';

// A reload would otherwise restore the previous scroll position and drop the
// visitor into the middle of a half-played sequence.
if ('scrollRestoration' in history) history.scrollRestoration = 'manual';

const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const root = document.documentElement;
const lens = document.getElementById('hero-lens');
const curtain = document.getElementById('hero-curtain');
const copy = document.getElementById('hero-copy');
const letters = document.querySelectorAll('.lens-wordmark span');

/* ---------- Preloader ---------------------------------------------------- */

function runPreloader() {
    const box = document.getElementById('preloader');
    const fill = document.getElementById('preloader-fill');
    const reticle = document.getElementById('preloader-reticle');
    const label = document.getElementById('preloader-pct');
    const stage = document.getElementById('preloader-stage');
    if (!box) return Promise.resolve();

    let pct = 0;
    const set = (v) => {
        pct = Math.max(pct, Math.min(100, Math.round(v)));
        if (fill) fill.style.width = pct + '%';
        if (reticle) reticle.style.left = pct + '%';
        if (label) label.textContent = String(pct);
        if (stage) stage.textContent = pct < 55 ? 'Decoding evidence' : pct < 100 ? 'Calibrating scale' : 'Ready';
    };
    set(6);

    const photo = document.querySelector('.lens-media');
    const settled = (el, ev) => new Promise((resolve) => {
        el.addEventListener(ev, resolve, { once: true });
        el.addEventListener('error', resolve, { once: true });
    });

    const ready = Promise.all([
        photo && !photo.complete ? settled(photo, 'load') : Promise.resolve(),
        document.readyState === 'complete' ? Promise.resolve() : settled(window, 'load'),
        new Promise((r) => setTimeout(r, 650)),
    ]);

    // Creep forward while waiting so the bar never looks stalled.
    const creep = setInterval(() => set(Math.min(pct + 4, 88)), 170);

    return ready.then(() => {
        clearInterval(creep);
        set(100);
        return new Promise((r) => setTimeout(r, 320));
    }).then(() => {
        box.dataset.done = 'true';
        setTimeout(() => box.remove(), 700);
    });
}

/* ---------- Below-fold reveals ------------------------------------------- */

const EASE = [0.16, 1, 0.3, 1];

function countUp(el) {
    const target = Number(el.dataset.countTo);
    if (!Number.isFinite(target)) return;
    const decimals = (el.dataset.countTo.split('.')[1] || '').length;
    el.textContent = target.toFixed(decimals).replace(/\d/g, '0');
    animate(0, target, {
        duration: 1.1,
        ease: EASE,
        onUpdate: (v) => { el.textContent = v.toFixed(decimals); },
    });
}

function wireReveals() {
    root.dataset.motion = 'on';
    const stops = [
        inView('.reveal-on-scroll', (el) => {
            animate(el, { opacity: [0, 1], y: [26, 0] }, { duration: 0.62, ease: EASE });
        }, { amount: 0.12, margin: '0px 0px -6% 0px' }),

        // Groups arrive in sequence, so a row of cards reads left to right.
        inView('.reveal-group', (el) => {
            animate([...el.children], { opacity: [0, 1], y: [24, 0] },
                { duration: 0.6, ease: EASE, delay: stagger(0.07) });
        }, { amount: 0.1, margin: '0px 0px -6% 0px' }),

        // Figures settle before their number runs.
        inView('[data-count-to]', (el) => { countUp(el); }, { amount: 0.6 }),
    ];
    return () => stops.forEach((stop) => stop());
}

/* ---------- The pinned sequence (GSAP owns every element it touches) ------ */

function wireSequence() {
    if (!window.gsap || !window.ScrollTrigger || !lens || !curtain) return null;
    gsap.registerPlugin(ScrollTrigger);

    const mm = gsap.matchMedia();
    mm.add({
        isDesktop: '(min-width: 901px)',
        reduce: '(prefers-reduced-motion: reduce)',
    }, (ctx) => {
        if (ctx.conditions.reduce || !ctx.conditions.isDesktop) return;

        root.dataset.sequence = 'on';
        curtain.classList.add('is-sequenced');
        gsap.set(letters, { opacity: 0, y: 16, filter: 'blur(8px)' });
        gsap.set(lens, { transformOrigin: '50% 50%' });

        // Offsets that carry the glass from its resting place to the middle.
        const centre = (axis) => () => {
            const b = lens.getBoundingClientRect();
            const current = gsap.getProperty(lens, axis === 'x' ? 'x' : 'y');
            return axis === 'x'
                ? current + (innerWidth / 2 - (b.left + b.width / 2))
                : current + (innerHeight / 2 - (b.top + b.height / 2));
        };

        // The hole and the glass grow together, so the rim always rides its edge.
        const maxHole = () => Math.hypot(innerWidth, innerHeight) / 2 * 1.08;
        const holeScale = () => maxHole() / (lens.offsetWidth / 2);

        let exiting = false;
        const tl = gsap.timeline({
            scrollTrigger: {
                trigger: '#hero',
                start: 'top top',
                // The page keeps scrolling behind the fixed glass, so the hole
                // opens onto the first content section rather than onto nothing.
                endTrigger: '#project',
                // Stop just short, so the heading clears the fixed header.
                end: 'top 90px',
                pin: true,
                pinSpacing: false,
                scrub: 0.25,
                invalidateOnRefresh: true,
                onUpdate: (self) => {
                    const past = self.progress > 0.6;
                    if (past !== exiting) { exiting = past; lens.classList.toggle('is-exiting', past); }
                },
                onLeave: () => { root.dataset.revealed = 'true'; },
                onEnterBack: () => { root.dataset.revealed = 'false'; },
                // Scrolling back above the start leaves the trigger inactive, so
                // reset the reveal here rather than waiting for an update tick.
                onLeaveBack: () => {
                    exiting = false;
                    lens.classList.remove('is-exiting');
                },
            },
        });

        // 1. The headline hands the frame to the glass.
        tl.to(copy, { yPercent: -34, opacity: 0, ease: 'power1.in', duration: 0.22 }, 0)
          .to(lens, { x: centre('x'), y: centre('y'), scale: 1.1, ease: 'power1.inOut', duration: 0.45 }, 0)

        // 2. The evidence layer dims out, leaving the wordmark on dark glass (0.38-0.52).
          .to(['.lens-media', '.lens-annotations', '.lens-hud', '.lens-sweep', '.lens-shine'],
              { opacity: 0, ease: 'none', duration: 0.14 }, 0.38)
          .to('.lens-tint', { opacity: 0, ease: 'none', duration: 0.14 }, 0.44)
          .to(['.hero-veil', '.hero-beams', '.hero-rules'],
              { autoAlpha: 0, ease: 'none', duration: 0.16 }, 0.42)

        // 3. The letters scrub in with staggered rise and blur on dark glass (0.44-0.58).
          .fromTo(letters,
              { opacity: 0, y: 16, filter: 'blur(8px)' },
              { opacity: 1, y: 0, filter: 'blur(0px)', stagger: 0.008, ease: 'power1.out', duration: 0.04 },
              0.44)

        // 4. The page comes through the glass (0.62-0.78), aperture finishes at 1.0.
          .to('.lens-wordmark', { scale: 1.35, opacity: 0, ease: 'power1.in', duration: 0.16 }, 0.62)
          .to(lens, { scale: holeScale, ease: 'power1.in', duration: 0.32 }, 0.68)
          .to(curtain, { '--hole': () => maxHole() + 'px', ease: 'power1.in', duration: 0.32 }, 0.68)
          .to('.lens-glass', { opacity: 0, ease: 'none', duration: 0.08 }, 0.92);

        return () => {
            tl.kill();
            curtain.classList.remove('is-sequenced');
            delete root.dataset.sequence;
            delete root.dataset.revealed;
            gsap.set([lens, copy, letters, '.lens-glass', '.lens-wordmark', '.lens-media', '.lens-annotations',
                      '.lens-sweep', '.lens-shine', '.lens-hud', '.lens-tint',
                      '.hero-veil', '.hero-beams', '.hero-rules'], { clearProps: 'all' });
            lens.classList.remove('is-exiting');
            letters.forEach((el) => { el.style.cssText = ''; });
        };
    });
    return mm;
}

/* ---------- Smooth scrolling --------------------------------------------- */

function wireLenis() {
    if (!window.Lenis || !window.gsap) return null;
    const lenis = new Lenis({ lerp: 0.16, anchors: { offset: -84 } });
    lenis.on('scroll', ScrollTrigger.update);
    const tick = (time) => lenis.raf(time * 1000);
    gsap.ticker.add(tick);
    gsap.ticker.lagSmoothing(0);
    return { lenis, tick };
}

/* ---------- Demo CTA: run a real claim in the cockpit --------------------- */

document.getElementById('btn-hero-demo')?.addEventListener('click', () => {
    const cockpit = document.getElementById('cockpit');
    document.getElementById('btn-case-b')?.click();
    if (window.__claimlensLenis) {
        window.__claimlensLenis.scrollTo(cockpit, { offset: -84 });
    } else {
        cockpit?.scrollIntoView({ behavior: reduceMotion.matches ? 'auto' : 'smooth', block: 'start' });
    }
});

/* ---------- Build / rebuild on preference change -------------------------- */

let teardown = [];

function build() {
    teardown.splice(0).forEach((fn) => fn());

    if (reduceMotion.matches) {
        delete root.dataset.motion;
        document.querySelectorAll('.reveal-on-scroll, .reveal-group > *').forEach((el) => {
            el.style.opacity = '1';
            el.style.transform = 'none';
        });
        document.querySelectorAll('[data-count-to]').forEach((el) => {
            el.textContent = el.dataset.countTo;
        });
        return;
    }

    const stopReveals = wireReveals();
    if (stopReveals) teardown.push(stopReveals);

    const mm = wireSequence();
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
}

runPreloader().then(() => {
    build();
    // Pin distances depend on images that land after first layout.
    window.ScrollTrigger?.refresh();
});

reduceMotion.addEventListener('change', build);
