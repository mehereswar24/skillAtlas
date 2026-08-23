'use client';

import { useEffect } from 'react';
import Lenis from 'lenis';

/**
 * Eased, momentum-style scrolling for the whole document.
 *
 * CSS `scroll-behavior: smooth` was not enough on its own: it only affects
 * *programmatic* scrolls — anchor jumps and `scrollTo` — and leaves the wheel
 * alone, so on a page with no in-page anchors it changes nothing a visitor can
 * see. Lenis interpolates the wheel itself, which is the thing being asked for.
 *
 * It drives the real document scroll (it calls `window.scrollTo` under the
 * hood) rather than transforming a container, so everything that reads scroll
 * position keeps working — notably the framer-motion `useScroll` parallax on
 * the landing hero, which would break under a transform-based implementation.
 *
 * Renders nothing.
 */
/**
 * True for an element that scrolls on its own, so Lenis leaves it to the
 * browser.
 *
 * Without this, a wheel over any inner panel scrolls the *page* behind it and
 * the panel never moves — measurably: wheeling over the route picker's list
 * moved the document 399px and the list 0. Every overflowing panel in the app
 * is affected, the route picker, the tutor transcript and the CodeMirror
 * editors among them, so this detects the condition rather than tagging each
 * one with `data-lenis-prevent` and waiting to miss the next one.
 *
 * The root elements are excluded deliberately: `html`/`body` overflow *is* the
 * page scroll, and treating them as nested scrollers would switch smoothing off
 * everywhere.
 */
function isNestedScroller(node: HTMLElement): boolean {
  if (node === document.documentElement || node === document.body) return false;
  // The explicit opt-out Lenis documents, honoured first so a component can
  // always override the heuristic.
  if (node.dataset?.lenisPrevent !== undefined) return true;
  if (node.scrollHeight <= node.clientHeight) return false;
  const overflowY = getComputedStyle(node).overflowY;
  return overflowY === 'auto' || overflowY === 'scroll';
}

export function SmoothScroll() {
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    let lenis: Lenis | null = null;

    const start = () => {
      if (lenis) return;
      lenis = new Lenis({
        // Long enough to read as eased rather than laggy. Past ~1.5s the page
        // feels like it is resisting the wheel.
        duration: 1.05,
        smoothWheel: true,
        // Leave touch alone. Phones and trackpads already have inertia in the
        // compositor; interpolating on top of it fights the platform and drops
        // frames on exactly the devices that can least afford it.
        syncTouch: false,
        // Ease in-page anchor jumps too, so a future `href="#..."` glides
        // instead of teleporting.
        anchors: true,
        prevent: isNestedScroller,
        // Lenis runs its own requestAnimationFrame loop.
        autoRaf: true,
      });
    };

    const stop = () => {
      lenis?.destroy();
      lenis = null;
    };

    // Reduced motion is not a preference to smooth over: hijacking the wheel is
    // precisely the kind of motion the setting asks us not to do. Bound to the
    // media query rather than read once, so toggling it at the OS level takes
    // effect without a reload.
    const sync = () => (media.matches ? stop() : start());
    sync();
    media.addEventListener('change', sync);

    return () => {
      media.removeEventListener('change', sync);
      stop();
    };
  }, []);

  return null;
}
