"use client";

import React, { useEffect, useRef, useState } from "react";
import gsap from "gsap";
import { CustomEase } from "gsap/CustomEase";


// Register GSAP Plugins safely
if (typeof window !== "undefined") {
  gsap.registerPlugin(CustomEase);
}

/**
 * `user` is null for a signed-out visitor, which is what the last menu entry
 * keys off: signed out it offers Sign in, signed in it shows who you are and
 * goes to the dashboard. Passed down from the page rather than fetched here —
 * this is a client component, and the landing page already has the user.
 */
export function SterlingGateKineticNavigation({
  user,
}: {
  user?: { display_name: string | null; email: string } | null;
}) {
  // Display name is nullable, so fall back to the local part of the email
  // before falling back to a generic label — "Account" is a worse greeting
  // than someone's own address.
  const name =
    user?.display_name?.trim() || user?.email?.split('@')[0] || 'Account';

  // We need a ref for the parent container to scope GSAP
  const containerRef = useRef<HTMLDivElement>(null);
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  // Initial Setup & Hover Effects
  useEffect(() => {
    if (!containerRef.current) return;

    // Create custom easing
    try {
        if (!gsap.parseEase("main")) {
            CustomEase.create("main", "0.65, 0.01, 0.05, 0.99");
            gsap.defaults({ ease: "main", duration: 0.7 });
        }
    } catch (e) {
        console.warn("CustomEase failed to load, falling back to default.", e);
        gsap.defaults({ ease: "power2.out", duration: 0.7 });
    }

    const ctx = gsap.context(() => {
      // 1. Arrow Animation (Removed from indicator, but keeping logic if arrow existed/restored elsewhere)
      const arrowLine = document.querySelector(".arrow-line");
      if (arrowLine) {
        const pathLength = (arrowLine as SVGPathElement).getTotalLength();
        gsap.set(arrowLine, { strokeDasharray: pathLength, strokeDashoffset: pathLength });
        const arrowTl = gsap.timeline({ repeat: -1, repeatDelay: 0.8 });
        arrowTl
          .to(arrowLine, { strokeDashoffset: 0, duration: 1, ease: "power2.out" })
          .to({}, { duration: 1.2 })
          .to(arrowLine, { strokeDashoffset: -pathLength, duration: 0.6, ease: "power2.in" })
          .set(arrowLine, { strokeDashoffset: pathLength });
      }

      // 2. Shape Hover
      const menuItems = containerRef.current!.querySelectorAll(".menu-list-item[data-shape]");
      const shapesContainer = containerRef.current!.querySelector(".ambient-background-shapes");
      
      menuItems.forEach((item) => {
        const shapeIndex = item.getAttribute("data-shape");
        const shape = shapesContainer ? shapesContainer.querySelector(`.bg-shape-${shapeIndex}`) : null;
        
        if (!shape) return;

        const shapeEls = shape.querySelectorAll(".shape-element");

        const onEnter = () => {
             if (shapesContainer) {
                 shapesContainer.querySelectorAll(".bg-shape").forEach((s) => s.classList.remove("active"));
             }
             shape.classList.add("active");
             
             gsap.fromTo(shapeEls, 
                { scale: 0.5, opacity: 0, rotation: -10 },
                { scale: 1, opacity: 1, rotation: 0, duration: 0.6, stagger: 0.08, ease: "back.out(1.7)", overwrite: "auto" }
             );
        };
        
        const onLeave = () => {
            gsap.to(shapeEls, {
                scale: 0.8, opacity: 0, duration: 0.3, ease: "power2.in",
                onComplete: () => shape.classList.remove("active"),
                overwrite: "auto"
            });
        };

        item.addEventListener("mouseenter", onEnter);
        item.addEventListener("mouseleave", onLeave);
        
        (item as any)._cleanup = () => {
            item.removeEventListener("mouseenter", onEnter);
            item.removeEventListener("mouseleave", onLeave);
        };
      });
      
    }, containerRef);

    return () => {
        ctx.revert();
        if (containerRef.current) {
            const items = containerRef.current.querySelectorAll(".menu-list-item[data-shape]");
            items.forEach((item: any) => item._cleanup && item._cleanup());
        }
    };
  }, []);

  // Menu Open/Close Animation Effect
  useEffect(() => {
      if (!containerRef.current) return;
      
      const ctx = gsap.context(() => {
        const navWrap = containerRef.current!.querySelector(".nav-overlay-wrapper");
        const menu = containerRef.current!.querySelector(".menu-content");
        const overlay = containerRef.current!.querySelector(".overlay");
        const bgPanels = containerRef.current!.querySelectorAll(".backdrop-layer");
        const menuLinks = containerRef.current!.querySelectorAll(".nav-link");
        const fadeTargets = containerRef.current!.querySelectorAll("[data-menu-fade]");
        
        const menuButton = containerRef.current!.querySelector(".nav-close-btn");
        // GSAP accepts null or an empty list as a no-op target, but not
        // `undefined` — which is what `?.` yields when the button is absent.
        const menuButtonTexts = menuButton ? menuButton.querySelectorAll("p") : [];
        const menuButtonIcon = menuButton?.querySelector(".menu-button-icon") ?? null;

        const tl = gsap.timeline();
        
        if (isMenuOpen) {
            // OPEN
            if (navWrap) navWrap.setAttribute("data-nav", "open");
            
            tl.set(navWrap, { display: "block" })
              .set(menu, { xPercent: 0 }, "<")
              .fromTo(menuButtonTexts, { yPercent: 0 }, { yPercent: -100, stagger: 0.2 })
              .fromTo(menuButtonIcon, { rotate: 0 }, { rotate: 315 }, "<")
              
              .fromTo(overlay, { autoAlpha: 0 }, { autoAlpha: 1 }, "<")
              .fromTo(bgPanels, { xPercent: 101 }, { xPercent: 0, stagger: 0.12, duration: 0.575 }, "<")
              .fromTo(menuLinks, { xPercent: 140, rotate: -10 }, { xPercent: 0, rotate: 0, stagger: 0.05 }, "<+=0.35");
              
            if (fadeTargets.length) {
                tl.fromTo(fadeTargets, { autoAlpha: 0, yPercent: 50 }, { autoAlpha: 1, yPercent: 0, stagger: 0.04, clearProps: "all" }, "<+=0.2");
            }

        } else {
            // CLOSE
            if (navWrap) navWrap.setAttribute("data-nav", "closed");

            tl.to(overlay, { autoAlpha: 0 })
              .to(menu, { xPercent: 120 }, "<")
              .to(menuButtonTexts, { yPercent: 0 }, "<")
              .to(menuButtonIcon, { rotate: 0 }, "<")
              .set(navWrap, { display: "none" });
        }

      }, containerRef);
      
      return () => ctx.revert();
  }, [isMenuOpen]);

  // keydown Escape handling
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
        if (e.key === "Escape" && isMenuOpen) {
            setIsMenuOpen(false);
        }
    };
    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [isMenuOpen]);

  const toggleMenu = () => setIsMenuOpen(prev => !prev);
  const closeMenu = () => setIsMenuOpen(false);

  return (
    <div ref={containerRef} className="fixed right-0 top-0 w-full h-full z-50 pointer-events-none">
        <div className="absolute right-6 top-6 z-50 pointer-events-auto">
          {/* Restored Menu Button */}
          <button 
            role="button" 
            className="nav-close-btn flex h-14 w-14 items-center justify-center rounded-full border border-border bg-background/80 shadow-sm backdrop-blur transition-transform hover:scale-110 overflow-hidden relative" 
            onClick={toggleMenu} 
            data-magnetic
          >
            <div className="menu-button-text absolute inset-0 flex flex-col items-center justify-center translate-y-full opacity-0 pointer-events-none">
              <p className="text-xs font-bold uppercase tracking-widest">Menu</p>
              <p className="text-xs font-bold uppercase tracking-widest">Close</p>
            </div>
            <div className="icon-wrap relative z-10 w-4 h-4 text-foreground">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="100%"
                viewBox="0 0 16 16"
                fill="none"
                className="menu-button-icon"
              >
                <path
                  d="M7.33333 16L7.33333 -3.2055e-07L8.66667 -3.78832e-07L8.66667 16L7.33333 16Z"
                  fill="currentColor"
                ></path>
                <path
                  d="M16 8.66667L-2.62269e-07 8.66667L-3.78832e-07 7.33333L16 7.33333L16 8.66667Z"
                  fill="currentColor"
                ></path>
                <path
                  d="M6 7.33333L7.33333 7.33333L7.33333 6C7.33333 6.73637 6.73638 7.33333 6 7.33333Z"
                  fill="currentColor"
                ></path>
                <path
                  d="M10 7.33333L8.66667 7.33333L8.66667 6C8.66667 6.73638 9.26362 7.33333 10 7.33333Z"
                  fill="currentColor"
                ></path>
                <path
                  d="M6 8.66667L7.33333 8.66667L7.33333 10C7.33333 9.26362 6.73638 8.66667 6 8.66667Z"
                  fill="currentColor"
                ></path>
                <path
                  d="M10 8.66667L8.66667 8.66667L8.66667 10C8.66667 9.26362 9.26362 8.66667 10 8.66667Z"
                  fill="currentColor"
                ></path>
              </svg>
            </div>
          </button>
        </div>

      {/* w-full capped at 400px: the previous fixed 400px was wider than a
          390px phone viewport, so this panel was itself what made the landing
          page scroll sideways. */}
      <section className="fullscreen-menu-container absolute right-0 top-0 h-screen w-full max-w-[400px] pointer-events-none">
        <div data-nav="closed" className="nav-overlay-wrapper hidden h-full w-full relative pointer-events-auto">
          {/* Overlay must stay above or below depending on desired clickability. */}
          <div className="overlay fixed inset-0 bg-background/20 backdrop-blur-sm opacity-0" onClick={closeMenu}></div>
          <nav className="menu-content h-full w-full bg-card border-r border-border relative overflow-hidden shadow-2xl flex flex-col justify-center">
            <div className="menu-bg absolute inset-0 pointer-events-none">
              <div className="backdrop-layer first absolute inset-0 bg-primary/5"></div>
              <div className="backdrop-layer second absolute inset-0 bg-primary/10"></div>
              <div className="backdrop-layer absolute inset-0 bg-background"></div>

              {/* Abstract shapes container */}
              <div className="ambient-background-shapes absolute inset-0 opacity-40">
                {/* Shape 1: Floating circles */}
                <svg className="bg-shape bg-shape-1 absolute inset-0 w-full h-full opacity-0 transition-opacity duration-300 [&.active]:opacity-100" viewBox="0 0 400 400" fill="none">
                  <circle className="shape-element" cx="80" cy="120" r="40" fill="var(--color-primary)" opacity="0.15" />
                  <circle className="shape-element" cx="300" cy="80" r="60" fill="var(--color-primary)" opacity="0.12" />
                  <circle className="shape-element" cx="200" cy="300" r="80" fill="var(--color-primary)" opacity="0.1" />
                  <circle className="shape-element" cx="350" cy="280" r="30" fill="var(--color-primary)" opacity="0.15" />
                </svg>

                {/* Shape 2: Wave pattern */}
                <svg className="bg-shape bg-shape-2 absolute inset-0 w-full h-full opacity-0 transition-opacity duration-300 [&.active]:opacity-100" viewBox="0 0 400 400" fill="none">
                  <path
                    className="shape-element"
                    d="M0 200 Q100 100, 200 200 T 400 200"
                    stroke="var(--color-primary)"
                    strokeOpacity="0.2"
                    strokeWidth="60"
                    fill="none"
                  />
                  <path
                    className="shape-element"
                    d="M0 280 Q100 180, 200 280 T 400 280"
                    stroke="var(--color-primary)"
                    strokeOpacity="0.15"
                    strokeWidth="40"
                    fill="none"
                  />
                </svg>

                {/* Shape 3: Grid dots */}
                <svg className="bg-shape bg-shape-3 absolute inset-0 w-full h-full opacity-0 transition-opacity duration-300 [&.active]:opacity-100" viewBox="0 0 400 400" fill="none">
                  <circle className="shape-element" cx="50" cy="50" r="8" fill="var(--color-primary)" opacity="0.3" />
                  <circle className="shape-element" cx="150" cy="50" r="8" fill="var(--color-primary)" opacity="0.3" />
                  <circle className="shape-element" cx="250" cy="50" r="8" fill="var(--color-primary)" opacity="0.3" />
                  <circle className="shape-element" cx="350" cy="50" r="8" fill="var(--color-primary)" opacity="0.3" />
                  <circle className="shape-element" cx="100" cy="150" r="12" fill="var(--color-primary)" opacity="0.25" />
                  <circle className="shape-element" cx="200" cy="150" r="12" fill="var(--color-primary)" opacity="0.25" />
                  <circle className="shape-element" cx="300" cy="150" r="12" fill="var(--color-primary)" opacity="0.25" />
                  <circle className="shape-element" cx="50" cy="250" r="10" fill="var(--color-primary)" opacity="0.3" />
                  <circle className="shape-element" cx="150" cy="250" r="10" fill="var(--color-primary)" opacity="0.3" />
                  <circle className="shape-element" cx="250" cy="250" r="10" fill="var(--color-primary)" opacity="0.3" />
                  <circle className="shape-element" cx="350" cy="250" r="10" fill="var(--color-primary)" opacity="0.3" />
                  <circle className="shape-element" cx="100" cy="350" r="6" fill="var(--color-primary)" opacity="0.3" />
                  <circle className="shape-element" cx="200" cy="350" r="6" fill="var(--color-primary)" opacity="0.3" />
                  <circle className="shape-element" cx="300" cy="350" r="6" fill="var(--color-primary)" opacity="0.3" />
                </svg>

                {/* Shape 4: Organic blobs */}
                <svg className="bg-shape bg-shape-4 absolute inset-0 w-full h-full opacity-0 transition-opacity duration-300 [&.active]:opacity-100" viewBox="0 0 400 400" fill="none">
                  <path
                    className="shape-element"
                    d="M100 100 Q150 50, 200 100 Q250 150, 200 200 Q150 250, 100 200 Q50 150, 100 100"
                    fill="var(--color-primary)"
                    opacity="0.12"
                  />
                  <path
                    className="shape-element"
                    d="M250 200 Q300 150, 350 200 Q400 250, 350 300 Q400 250, 350 300 Q300 350, 250 300 Q200 250, 250 200"
                    fill="var(--color-primary)"
                    opacity="0.1"
                  />
                </svg>

                {/* Shape 5: Diagonal lines */}
                <svg className="bg-shape bg-shape-5 absolute inset-0 w-full h-full opacity-0 transition-opacity duration-300 [&.active]:opacity-100" viewBox="0 0 400 400" fill="none">
                  <line className="shape-element" x1="0" y1="100" x2="300" y2="400" stroke="var(--color-primary)" strokeOpacity="0.15" strokeWidth="30" />
                  <line className="shape-element" x1="100" y1="0" x2="400" y2="300" stroke="var(--color-primary)" strokeOpacity="0.12" strokeWidth="25" />
                  <line className="shape-element" x1="200" y1="0" x2="400" y2="200" stroke="var(--color-primary)" strokeOpacity="0.1" strokeWidth="20" />
                </svg>
              </div>
            </div>

            <div className="menu-content-wrapper relative z-10 px-12">
              <ul className="menu-list flex flex-col gap-6 text-4xl font-display font-medium">
                <li className="menu-list-item" data-shape="1">
                  <a href="/explore" className="nav-link block overflow-hidden" data-magnetic>
                    <p className="nav-link-text transition-transform hover:translate-x-4">Explore</p>
                  </a>
                </li>
                <li className="menu-list-item" data-shape="2">
                  <a href="/companies" className="nav-link block overflow-hidden" data-magnetic>
                    <p className="nav-link-text transition-transform hover:translate-x-4">Companies</p>
                  </a>
                </li>
                <li className="menu-list-item" data-shape="3">
                  <a href="/projects" className="nav-link block overflow-hidden" data-magnetic>
                    <p className="nav-link-text transition-transform hover:translate-x-4">Projects</p>
                  </a>
                </li>
                <li className="menu-list-item" data-shape="4">
                  <a href="/community" className="nav-link block overflow-hidden" data-magnetic>
                    <p className="nav-link-text transition-transform hover:translate-x-4" data-menu-fade>Community</p>
                  </a>
                </li>
                <li className="menu-list-item" data-shape="5">
                  <a
                    href={user ? '/dashboard' : '/login'}
                    className="nav-link block overflow-hidden"
                    data-magnetic
                  >
                    <p className="nav-link-text transition-transform hover:translate-x-4 text-primary mt-8">
                      {user ? name : 'Sign in'}
                    </p>
                  </a>
                </li>
              </ul>
            </div>
          </nav>
        </div>
      </section>
    </div>
  );
}
