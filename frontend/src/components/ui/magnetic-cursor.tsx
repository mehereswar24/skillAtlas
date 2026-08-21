"use client";

import React, { useRef, useEffect, FC, ReactNode, useState } from 'react';
import gsap from 'gsap';
// `vecteur` exports the class as `Vector2`; `Vec2` was never a real export.
import { vec2, type Vector2 } from 'vecteur';

interface MagneticCursorProps {
  children: ReactNode;
  magneticFactor?: number;
  lerpAmount?: number;
  hoverPadding?: number;
  hoverAttribute?: string;
  cursorSize?: number;
  cursorColor?: string;
  blendMode?: 'difference' | 'exclusion' | 'normal' | 'screen' | 'overlay';
  cursorClassName?: string;
  shape?: 'circle' | 'square' | 'rounded-square';
  disableOnTouch?: boolean;
  speedMultiplier?: number;
  maxScaleX?: number;
  maxScaleY?: number;
  /** 
   * Boosts background contrast before blending. 
   * Higher values (1.5 - 2.0) fix visibility on low-contrast/dim backgrounds.
   * Default: 1.5 (150%)
   */
  contrastBoost?: number;
}

interface CursorState {
  el: HTMLDivElement | null;
  pos: {
    current: Vector2;
    target: Vector2;
    previous: Vector2;
  };
  hover: { isHovered: boolean };
  isDetaching: boolean;
}

export const MagneticCursor: FC<MagneticCursorProps> = ({
  children,
  lerpAmount = 0.1,
  magneticFactor = 0.2,
  hoverPadding = 12,
  hoverAttribute = 'data-magnetic',
  cursorSize = 24,
  cursorColor = 'white', // Pure white works best for exclusion/difference
  blendMode = 'exclusion', // Exclusion is safer than difference for text
  cursorClassName = '',
  shape = 'circle',
  disableOnTouch = true,
  speedMultiplier = 0.02,
  maxScaleX = 1,
  maxScaleY = 0.3,
  contrastBoost = 1.5, // 1.5x contrast boost by default
}) => {
  const cursorRef = useRef<HTMLDivElement>(null);
  const cursorStateRef = useRef<CursorState | null>(null);
  const [isTouchDevice, setIsTouchDevice] = useState(false);

  const configRef = useRef({
    magneticFactor,
    speedMultiplier,
    maxScaleX,
    maxScaleY,
    cursorSize,
    lerpAmount,
    hoverPadding,
  });

  useEffect(() => {
    configRef.current = {
      magneticFactor,
      speedMultiplier,
      maxScaleX,
      maxScaleY,
      cursorSize,
      lerpAmount,
      hoverPadding,
    };
  }, [magneticFactor, speedMultiplier, maxScaleX, maxScaleY, cursorSize, lerpAmount, hoverPadding]);

  useEffect(() => {
    setIsTouchDevice('ontouchstart' in window || navigator.maxTouchPoints > 0);
  }, []);

  useEffect(() => {
    if (disableOnTouch && isTouchDevice) return;
    const cursorEl = cursorRef.current;
    if (!cursorEl) return;

    gsap.set(cursorEl, { xPercent: -50, yPercent: -50 });

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const detachDuration = prefersReducedMotion ? 0.1 : 0.35;

    if (!cursorStateRef.current) {
      cursorStateRef.current = {
        el: cursorEl,
        pos: {
          current: vec2(-100, -100),
          target: vec2(-100, -100),
          previous: vec2(-100, -100),
        },
        hover: { isHovered: false },
        isDetaching: false,
      };
    }

    const update = () => {
      const state = cursorStateRef.current;
      if (!state || state.hover.isHovered) return;

      const { speedMultiplier, maxScaleX, maxScaleY, lerpAmount } = configRef.current;
      const effectiveLerp = prefersReducedMotion ? 1 : lerpAmount;

      state.pos.current.lerp(state.pos.target, effectiveLerp);
      const delta = state.pos.current.clone().sub(state.pos.previous);
      state.pos.previous.copy(state.pos.current);

      if (state.isDetaching) {
        gsap.set(state.el, {
          x: state.pos.current.x,
          y: state.pos.current.y,
          scaleX: 1,
          scaleY: 1,
          rotate: 0,
          overwrite: 'auto'
        });
      } else {
        const speed = Math.sqrt(delta.x * delta.x + delta.y * delta.y) * speedMultiplier;
        gsap.set(state.el, {
          x: state.pos.current.x,
          y: state.pos.current.y,
          rotate: Math.atan2(delta.y, delta.x) * (180 / Math.PI),
          scaleX: 1 + Math.min(speed, maxScaleX),
          scaleY: 1 - Math.min(speed, maxScaleY),
          overwrite: 'auto'
        });
      }
    };

    const initializePosition = (event: MouseEvent) => {
      const state = cursorStateRef.current;
      if (!state) return;
      const x = event.clientX;
      const y = event.clientY;
      state.pos.current.x = x;
      state.pos.current.y = y;
      state.pos.target.x = x;
      state.pos.target.y = y;
      state.pos.previous.x = x;
      state.pos.previous.y = y;
      gsap.set(cursorEl, { x, y, opacity: 1 });
    };

    let currentMagneticElement: HTMLElement | null = null;
    let magneticRafId: number | null = null;
    const quickToMap = new WeakMap<HTMLElement, { xTo: any; yTo: any }>();

    const getQuickTo = (el: HTMLElement) => {
      if (!quickToMap.has(el)) {
        quickToMap.set(el, {
          xTo: gsap.quickTo(el, 'x', { duration: 1, ease: 'elastic.out(1, 0.3)' }),
          yTo: gsap.quickTo(el, 'y', { duration: 1, ease: 'elastic.out(1, 0.3)' }),
        });
      }
      return quickToMap.get(el)!;
    };

    const handlePointerEnter = (el: HTMLElement) => {
      const state = cursorStateRef.current;
      if (!state) return;
      const { magneticFactor, hoverPadding } = configRef.current;

      state.hover.isHovered = true;
      state.isDetaching = false;

      const bounds = el.getBoundingClientRect();
      const computedStyle = window.getComputedStyle(el);
      const magneticColor = el.getAttribute('data-magnetic-color') || cursorColor;
      const dynamicPadding = hoverPadding * (1 + magneticFactor);
      const centerX = bounds.left + bounds.width / 2;
      const centerY = bounds.top + bounds.height / 2;

      gsap.killTweensOf(cursorEl);
      gsap.to(cursorEl, {
        x: centerX,
        y: centerY,
        width: bounds.width + dynamicPadding * 2,
        height: bounds.height + dynamicPadding * 2,
        borderRadius: computedStyle.borderRadius,
        backgroundColor: magneticColor,
        scaleX: 1,
        scaleY: 1,
        rotate: 0,
        duration: 0.3,
        ease: 'power3.out',
        overwrite: true,   // GSAP 3 spells "kill other tweens of these targets" as true
      });
    };

    const handlePointerLeave = (el: HTMLElement) => {
      const state = cursorStateRef.current;
      if (!state) return;
      const currentX = gsap.getProperty(cursorEl, 'x') as number;
      const currentY = gsap.getProperty(cursorEl, 'y') as number;

      state.pos.current.x = currentX;
      state.pos.current.y = currentY;
      state.pos.previous.x = currentX;
      state.pos.previous.y = currentY;

      state.hover.isHovered = false;
      state.isDetaching = true;

      const { cursorSize } = configRef.current;
      const shapeBorderRadius = shape === 'circle' ? '50%' : shape === 'square' ? '0' : '8px';

      gsap.killTweensOf(cursorEl);
      gsap.to(cursorEl, {
        width: cursorSize,
        height: cursorSize,
        borderRadius: shapeBorderRadius,
        backgroundColor: cursorColor,
        scaleX: 1,
        scaleY: 1,
        duration: detachDuration,
        ease: 'power3.out',
        overwrite: true,   // GSAP 3 spells "kill other tweens of these targets" as true
        onComplete: () => {
          state.isDetaching = false;
        },
      });

      const { xTo, yTo } = getQuickTo(el);
      xTo(0);
      yTo(0);
    };

    const onMouseMove = (event: PointerEvent) => {
      const state = cursorStateRef.current;
      if (!state) return;
      
      state.pos.target.x = event.clientX;
      state.pos.target.y = event.clientY;

      const isInViewport =
        event.clientX >= 0 &&
        event.clientX <= window.innerWidth &&
        event.clientY >= 0 &&
        event.clientY <= window.innerHeight;

      gsap.to(cursorEl, { opacity: isInViewport ? 1 : 0, duration: 0.2, overwrite: 'auto' });

      const targetEl = (event.target as Element)?.closest?.(`[${hoverAttribute}]`) as HTMLElement | null;
      if (targetEl !== currentMagneticElement) {
        if (currentMagneticElement) {
          handlePointerLeave(currentMagneticElement);
        }
        if (targetEl) {
          handlePointerEnter(targetEl);
        }
        currentMagneticElement = targetEl;
      }

      if (currentMagneticElement) {
        if (!magneticRafId) {
          magneticRafId = requestAnimationFrame(() => {
            const el = currentMagneticElement;
            if (el) {
              const { clientX, clientY } = event;
              const { height, width, left, top } = el.getBoundingClientRect();
              const { magneticFactor } = configRef.current;
              const { xTo, yTo } = getQuickTo(el);
              xTo((clientX - (left + width / 2)) * magneticFactor);
              yTo((clientY - (top + height / 2)) * magneticFactor);
            }
            magneticRafId = null;
          });
        }
      }

      const target = event.target as HTMLElement;
      const isTextContent =
        ['P', 'SPAN', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6'].includes(target?.tagName) ||
        (target && window.getComputedStyle(target).cursor === 'text');

      if (isTextContent && !state.hover.isHovered && !state.isDetaching) {
        gsap.to(cursorEl, { scaleX: 0.5, scaleY: 1.5, duration: 0.3, overwrite: 'auto' });
      }
    };

    const handleMouseLeave = () => {
      gsap.to(cursorEl, { opacity: 0, duration: 0.3 });
      if (currentMagneticElement) {
         handlePointerLeave(currentMagneticElement);
         currentMagneticElement = null;
      }
    };
    
    const handleMouseEnter = () => gsap.to(cursorEl, { opacity: 1, duration: 0.3 });
    const handleClick = (event: MouseEvent) => {};

    gsap.ticker.add(update);
    window.addEventListener('pointermove', onMouseMove);
    window.addEventListener('pointermove', initializePosition, { once: true });
    document.addEventListener('mouseleave', handleMouseLeave);
    document.addEventListener('mouseenter', handleMouseEnter);
    window.addEventListener('click', handleClick);

    return () => {
      gsap.ticker.remove(update);
      window.removeEventListener('pointermove', onMouseMove);
      document.removeEventListener('mouseleave', handleMouseLeave);
      document.removeEventListener('mouseenter', handleMouseEnter);
      window.removeEventListener('click', handleClick);
    };
  }, [disableOnTouch, isTouchDevice, hoverPadding, hoverAttribute, cursorColor, shape]);

  if (disableOnTouch && isTouchDevice) return <>{children}</>;

  const styles: React.CSSProperties = {
    position: 'fixed',
    top: 0,
    left: 0,
    zIndex: 999999,
    pointerEvents: 'none',
    willChange: 'transform, width, height, border-radius',
    backgroundColor: cursorColor,
    mixBlendMode: blendMode as any,
    width: cursorSize,
    height: cursorSize,
    borderRadius: shape === 'circle' ? '50%' : shape === 'square' ? '0' : '8px',
    // KEY FIX: Contrast Boost using backdrop-filter
    backdropFilter: contrastBoost !== 1 ? `contrast(${contrastBoost})` : 'none',
    WebkitBackdropFilter: contrastBoost !== 1 ? `contrast(${contrastBoost})` : 'none',
  };

  return (
    <>
      <div ref={cursorRef} className={`magnetic-cursor ${cursorClassName}`} style={styles} />
      {children}
    </>
  );
};
