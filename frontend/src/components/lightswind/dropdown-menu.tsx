import * as React from "react";
import ReactDOM from "react-dom";
import { cva } from "class-variance-authority";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

interface DropdownMenuContextType {
  open: boolean;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
  hoverMode?: boolean;
  triggerRef: React.MutableRefObject<HTMLElement | null>;
  timeoutRef: React.MutableRefObject<NodeJS.Timeout | null>;
  /** Ids wiring the trigger and the menu together for assistive tech. */
  menuId: string;
  triggerId: string;
  /** Which end of the list to focus when the menu opens from the keyboard. */
  focusOnOpenRef: React.MutableRefObject<"first" | "last" | null>;
  /** Set by the content so the trigger can hand focus back on close. */
  returnFocusRef: React.MutableRefObject<boolean>;
}

const DropdownMenuContext = React.createContext<DropdownMenuContextType | undefined>(undefined);

interface DropdownMenuProps {
  children: React.ReactNode;
  defaultOpen?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  hoverMode?: boolean;
}

const DropdownMenu: React.FC<DropdownMenuProps> = ({
  children,
  defaultOpen = false,
  open: controlledOpen,
  onOpenChange,
  hoverMode = false,
}) => {
  const [uncontrolledOpen, setUncontrolledOpen] = React.useState(defaultOpen);
  const triggerRef = React.useRef<HTMLElement | null>(null);

  const isControlled = controlledOpen !== undefined;
  const open = isControlled ? controlledOpen : uncontrolledOpen;

  const setOpen = React.useCallback(
    (value: React.SetStateAction<boolean>) => {
      if (!isControlled) {
        setUncontrolledOpen(value);
      } else if (onOpenChange) {
        const nextOpen = typeof value === "function" ? (value as (p: boolean) => boolean)(controlledOpen ?? false) : value;
        onOpenChange(nextOpen);
      }
    },
    [isControlled, onOpenChange, controlledOpen]
  );

  // Notify parent of uncontrolled state changes — outside state updaters to avoid Strict Mode issues
  React.useEffect(() => {
    if (!isControlled && onOpenChange) {
      onOpenChange(uncontrolledOpen);
    }
  }, [uncontrolledOpen, isControlled, onOpenChange]);

  const timeoutRef = React.useRef<NodeJS.Timeout | null>(null);
  const focusOnOpenRef = React.useRef<"first" | "last" | null>(null);
  const returnFocusRef = React.useRef(false);

  // Stable, SSR-safe ids so the trigger can point at the menu it controls.
  const reactId = React.useId();
  const menuId = `dropdown-menu-${reactId}`;
  const triggerId = `dropdown-trigger-${reactId}`;

  React.useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  const value = React.useMemo(
    () => ({
      open: open || false,
      setOpen,
      hoverMode,
      triggerRef,
      timeoutRef,
      menuId,
      triggerId,
      focusOnOpenRef,
      returnFocusRef,
    }),
    [open, setOpen, hoverMode, menuId, triggerId]
  );

  return (
    <DropdownMenuContext.Provider value={value}>
      {children}
    </DropdownMenuContext.Provider>
  );
};

interface DropdownMenuTriggerProps {
  children: React.ReactNode;
  asChild?: boolean;
}

const DropdownMenuTrigger = React.forwardRef<
  HTMLButtonElement,
  DropdownMenuTriggerProps & React.ButtonHTMLAttributes<HTMLButtonElement>
>(({ children, asChild, ...props }, ref) => {
  const context = React.useContext(DropdownMenuContext);
  if (!context) throw new Error("DropdownMenuTrigger must be used within a DropdownMenu");

  const { open, setOpen, hoverMode, triggerRef, timeoutRef, menuId, triggerId, focusOnOpenRef } =
    context;

  // ArrowDown/ArrowUp open the menu and land on an item, per the WAI-ARIA
  // menu-button pattern. Enter and Space already work: the trigger is a real
  // <button>, so the browser synthesises a click.
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      focusOnOpenRef.current = e.key === "ArrowDown" ? "first" : "last";
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      setOpen(true);
    }
  };

  // ARIA attributes every trigger needs, whether it renders its own button or
  // borrows a child element through `asChild`.
  const ariaProps = {
    "aria-haspopup": "menu" as const,
    "aria-expanded": open,
    "aria-controls": open ? menuId : undefined,
    id: triggerId,
  };

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    // A pointer click should land on the menu, not on an item.
    focusOnOpenRef.current = null;
    if (hoverMode) {
      // In hover mode, click should only open (not toggle), to avoid
      // fighting with the hover timers on first interaction
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      setOpen(true);
    } else {
      setOpen((prev) => !prev);
    }
    if (props.onClick) props.onClick(e);
  };

  React.useImperativeHandle(ref, () => {
    if (!triggerRef.current) return document.createElement("button");
    return triggerRef.current as HTMLButtonElement;
  }, [triggerRef]);

  const handleMouseEnter = (e: React.MouseEvent<HTMLElement>) => {
    if (hoverMode) {
      // Always clear any pending timer (open or close)
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      // Schedule open — setOpen(true) is idempotent if already open
      timeoutRef.current = setTimeout(() => setOpen(true), 150);
    }
    if (props.onMouseEnter) props.onMouseEnter(e as React.MouseEvent<HTMLButtonElement>);
  };

  const handleMouseLeaveTrigger = (e: React.MouseEvent<HTMLElement>) => {
    if (hoverMode) {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => setOpen(false), 200);
    }
    if (props.onMouseLeave) props.onMouseLeave(e as React.MouseEvent<HTMLButtonElement>);
  };

  const { onClick, onMouseEnter, onMouseLeave, onKeyDown, ...otherProps } = props;
  void onClick;
  void onMouseEnter;
  void onMouseLeave;

  if (asChild) {
    const child = React.Children.only(children) as React.ReactElement<any>;
    return React.cloneElement(child, {
      ...child.props,
      ...ariaProps,
      ref: (node: HTMLElement | null) => {
        triggerRef.current = node;
        if (typeof ref === "function") ref(node as HTMLButtonElement);
        else if (ref) (ref as React.MutableRefObject<HTMLElement | null>).current = node;

        // Handle child's original ref
        const childRef = (child as any).ref;
        if (childRef) {
          if (typeof childRef === "function") childRef(node);
          else if (childRef.hasOwnProperty("current")) childRef.current = node;
        }
      },
      onClick: (e: React.MouseEvent) => {
        handleClick(e as React.MouseEvent<HTMLButtonElement>);
        if (child.props.onClick) child.props.onClick(e);
      },
      onMouseEnter: (e: React.MouseEvent) => {
        handleMouseEnter(e as React.MouseEvent<HTMLElement>);
        if (child.props.onMouseEnter) child.props.onMouseEnter(e);
      },
      onMouseLeave: (e: React.MouseEvent) => {
        // Start a close timer; the content's onMouseEnter will cancel it if
        // the cursor moves into the portal-rendered dropdown before the timer fires.
        handleMouseLeaveTrigger(e as React.MouseEvent<HTMLElement>);
        if (child.props.onMouseLeave) child.props.onMouseLeave(e);
      },
      onKeyDown: (e: React.KeyboardEvent) => {
        handleKeyDown(e);
        if (onKeyDown) onKeyDown(e as React.KeyboardEvent<HTMLButtonElement>);
        if (child.props.onKeyDown) child.props.onKeyDown(e);
      },
      ...otherProps,
    });
  }

  return (
    <button
      ref={(node) => {
        triggerRef.current = node;
        if (typeof ref === "function") ref(node);
        else if (ref) ref.current = node;
      }}
      type="button"
      {...ariaProps}
      onClick={handleClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeaveTrigger}
      onKeyDown={(e) => {
        handleKeyDown(e);
        if (onKeyDown) onKeyDown(e);
      }}
      {...otherProps}
    >
      {children}
    </button>
  );
});
DropdownMenuTrigger.displayName = "DropdownMenuTrigger";

const dropdownMenuContentVariants = cva(
  "z-50 min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md",
  {
    variants: {
      variant: {
        default: "",
        contextMenu: "min-w-0",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

interface DropdownMenuContentProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "onDrag" | "onDragStart" | "onDragEnd" | "onAnimationStart" | "onAnimationEnd"> {
  align?: "start" | "center" | "end";
  alignOffset?: number;
  side?: "top" | "right" | "bottom" | "left";
  sideOffset?: number;
  variant?: "default" | "contextMenu";
}

const DropdownMenuContent = React.forwardRef<HTMLDivElement, DropdownMenuContentProps>(
  ({ className, children, align = "center", alignOffset = 0, side = "bottom", sideOffset = 4, variant, ...props }, ref) => {
    const context = React.useContext(DropdownMenuContext);
    if (!context) throw new Error("DropdownMenuContent must be used within a DropdownMenu");

    const { open, setOpen, hoverMode, triggerRef, menuId, triggerId, focusOnOpenRef, returnFocusRef } =
      context;
    const menuRef = React.useRef<HTMLDivElement | null>(null);
    const [position, setPosition] = React.useState({ top: 0, left: 0 });
    const [mounted, setMounted] = React.useState(false);
    const [positioned, setPositioned] = React.useState(false);

    React.useEffect(() => {
      setMounted(true);
    }, []);

    // Reset positioned to false ONLY when closed, avoids flickering when children change
    React.useEffect(() => {
      if (!open) {
        setPositioned(false);
      }
    }, [open]);

    // Body scroll lock removed
    // Previous logic was interfering with page navigation

    // Close on click outside
    React.useEffect(() => {
      if (!open) return;
      const handleClickOutside = (e: MouseEvent) => {
        if (
          menuRef.current &&
          !menuRef.current.contains(e.target as Node) &&
          triggerRef.current &&
          !triggerRef.current.contains(e.target as Node)
        ) {
          setOpen(false);
        }
      };
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }, [open, setOpen, triggerRef]);

    // -- keyboard: focus management and navigation -------------------------

    const enabledItems = React.useCallback(
      () =>
        menuRef.current
          ? Array.from(
              menuRef.current.querySelectorAll<HTMLElement>(
                '[role="menuitem"]:not([aria-disabled="true"])'
              )
            )
          : [],
      []
    );

    // Move focus into the menu when it opens, and hand it back to the trigger
    // when it closes — otherwise a keyboard user is stranded at the top of the
    // document with nothing focused.
    React.useEffect(() => {
      if (!open) {
        if (returnFocusRef.current) {
          returnFocusRef.current = false;
          triggerRef.current?.focus();
        }
        return;
      }
      returnFocusRef.current = true;
      const frame = requestAnimationFrame(() => {
        const items = enabledItems();
        const where = focusOnOpenRef.current;
        focusOnOpenRef.current = null;
        if (where === "last") items[items.length - 1]?.focus();
        else if (where === "first") items[0]?.focus();
        else menuRef.current?.focus();
      });
      return () => cancelAnimationFrame(frame);
    }, [open, enabledItems, focusOnOpenRef, returnFocusRef, triggerRef]);

    const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
      const items = enabledItems();
      const index = items.indexOf(document.activeElement as HTMLElement);

      switch (e.key) {
        case "Escape":
          e.preventDefault();
          e.stopPropagation();
          setOpen(false);
          break;
        case "Tab":
          // A menu is a single stop in the tab order: leaving it closes it.
          setOpen(false);
          break;
        case "ArrowDown":
          e.preventDefault();
          items[index < 0 || index === items.length - 1 ? 0 : index + 1]?.focus();
          break;
        case "ArrowUp":
          e.preventDefault();
          items[index <= 0 ? items.length - 1 : index - 1]?.focus();
          break;
        case "Home":
          e.preventDefault();
          items[0]?.focus();
          break;
        case "End":
          e.preventDefault();
          items[items.length - 1]?.focus();
          break;
        default:
          break;
      }
      if (props.onKeyDown) props.onKeyDown(e);
    };

    // Position updates
    React.useEffect(() => {
      if (!open || !triggerRef.current) return;

      const updatePosition = () => {
        if (!triggerRef.current) return;
        const triggerRect = triggerRef.current.getBoundingClientRect();
        
        // Use offsetWidth / offsetHeight to get unscaled layout dimensions
        const menuWidth = menuRef.current ? menuRef.current.offsetWidth : 0;
        const menuHeight = menuRef.current ? menuRef.current.offsetHeight : 0;

        let top = 0;
        let left = 0;

        // Basic positioning logic tailored for Portal (relative to viewport)
        if (side === "bottom") {
          top = triggerRect.bottom + sideOffset;
        } else if (side === "top") {
          top = triggerRect.top - menuHeight - sideOffset;
        } else if (side === "left" || side === "right") {
          top = triggerRect.top + triggerRect.height / 2 - menuHeight / 2;
        }

        if (side === "right") {
          left = triggerRect.right + sideOffset;
        } else if (side === "left") {
          left = triggerRect.left - menuWidth - sideOffset;
        } else {
          if (align === "start") left = triggerRect.left + alignOffset;
          else if (align === "center") left = triggerRect.left + triggerRect.width / 2 - menuWidth / 2 + alignOffset;
          else if (align === "end") left = triggerRect.right - menuWidth - alignOffset;
        }

        // Viewport collision detection
        const windowWidth = window.innerWidth;
        const windowHeight = window.innerHeight;

        if (left + menuWidth > windowWidth) left = windowWidth - menuWidth - 8;
        if (left < 8) left = 8;

        if (top + menuHeight > windowHeight) {
          if (side === "bottom" && triggerRect.top > menuHeight + sideOffset) {
            top = triggerRect.top - menuHeight - sideOffset;
          } else {
            const maxHeight = windowHeight - top - 8;
            if (menuRef.current) menuRef.current.style.maxHeight = `${maxHeight}px`;
          }
        }

        setPosition({ top, left });
      };

      // Run update immediately and on scroll/resize
      // Use rAF to ensure the DOM has painted the portal content before measuring
      const raf = requestAnimationFrame(() => {
        updatePosition();
        setPositioned(true);
      });
      window.addEventListener("scroll", updatePosition, true);
      window.addEventListener("resize", updatePosition);

      // Set up ResizeObserver to recalculate if the size of the menu changes during mount/styling/render
      const resizeObserver = new ResizeObserver(() => {
        updatePosition();
      });
      if (menuRef.current) {
        resizeObserver.observe(menuRef.current);
      }

      // Also update after a short delay to ensure Framer Motion has rendered the initial frame
      const timeout = setTimeout(() => {
        updatePosition();
        setPositioned(true);
      }, 0);

      return () => {
        window.removeEventListener("scroll", updatePosition, true);
        window.removeEventListener("resize", updatePosition);
        cancelAnimationFrame(raf);
        clearTimeout(timeout);
        resizeObserver.disconnect();
      };
    }, [open, align, alignOffset, side, sideOffset, triggerRef, children, variant, className, mounted]);

    if (!mounted) return null;

    return ReactDOM.createPortal(
      <AnimatePresence>
        {open && (
          <motion.div
            ref={(node) => {
              if (typeof ref === "function") ref(node);
              else if (ref) (ref as React.MutableRefObject<HTMLDivElement | null>).current = node;
              menuRef.current = node;
            }}
            // Caller props go first, deliberately. Everything below composes
            // with them (the handlers call `props.on*` themselves), so
            // spreading last would silently replace the menu's own keyboard
            // handling and its fixed positioning with whatever a caller passed.
            data-lenis-prevent
            {...props}
            role="menu"
            id={menuId}
            aria-labelledby={triggerId}
            tabIndex={-1}
            onKeyDown={handleKeyDown}
            className={cn(dropdownMenuContentVariants({ variant }), "dropdown-scrollbar", className)}
            style={{
              position: "fixed",
              top: `${position.top}px`,
              left: `${position.left}px`,
              zIndex: 99999,
              maxHeight: "calc(90vh - 60px)",
              overflowY: "auto",
              transformOrigin: side === "bottom" ? "top center" : side === "top" ? "bottom center" : side === "left" ? "center right" : "center left",
            }}
            initial={{ opacity: 0, scale: 0.9, y: side === "bottom" ? -4 : side === "top" ? 4 : 0 }}
            animate={positioned ? { opacity: 1, scale: 1, y: 0, pointerEvents: "auto" as const } : { opacity: 0, scale: 0.9, pointerEvents: "none" as const }}
            exit={{ opacity: 0, scale: 0.9, y: side === "bottom" ? -4 : side === "top" ? 4 : 0, transition: { duration: 0.15 }, pointerEvents: "none" as const }}
            transition={{
              type: "spring",
              damping: 20,
              stiffness: 300
            }}
            onMouseEnter={(e) => {
              if (hoverMode && context.timeoutRef.current) {
                clearTimeout(context.timeoutRef.current);
              }
              if (props.onMouseEnter) props.onMouseEnter(e as any);
            }}
            onMouseLeave={(e) => {
              if (hoverMode) {
                context.timeoutRef.current = setTimeout(() => setOpen(false), 200);
              }
              if (props.onMouseLeave) props.onMouseLeave(e as any);
            }}
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>,
      document.body
    );
  }
);
DropdownMenuContent.displayName = "DropdownMenuContent";

const DropdownMenuLabel = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      role="presentation"
      className={cn("px-2 py-1.5 text-sm font-semibold", className)}
      {...props}
    />
  )
);
DropdownMenuLabel.displayName = "DropdownMenuLabel";

interface DropdownMenuItemProps extends React.HTMLAttributes<HTMLDivElement> {
  inset?: boolean;
  disabled?: boolean;
}

/**
 * A single command in the menu.
 *
 * It is a `div` rather than a `button` so callers can drop arbitrary content
 * inside it, which means the roles and the keyboard have to be supplied by
 * hand: `role="menuitem"` so screen readers announce it as a command,
 * `tabIndex={-1}` so it is programmatically focusable (the menu owns the tab
 * stop and moves focus with the arrow keys), and Enter/Space to activate —
 * exactly what a real button would have given us for free.
 */
const DropdownMenuItem = React.forwardRef<HTMLDivElement, DropdownMenuItemProps>(
  ({ className, inset, disabled = false, onClick, onKeyDown, ...props }, ref) => {
    const context = React.useContext(DropdownMenuContext);
    if (!context) throw new Error("DropdownMenuItem must be used within a DropdownMenu");
    const { setOpen } = context;

    const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
      if (disabled) {
        e.preventDefault();
        return;
      }
      setOpen(false);
      if (onClick) onClick(e);
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (onKeyDown) onKeyDown(e);
      if (e.defaultPrevented) return;
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        // Not stopped: the menu's own handler ignores these keys, and letting
        // it bubble keeps any wrapper listeners working.
        if (disabled) return;
        e.currentTarget.click();
      }
    };

    return (
      <div
        ref={ref}
        role="menuitem"
        tabIndex={disabled ? undefined : -1}
        aria-disabled={disabled || undefined}
        className={cn(
          "relative flex gap-1 cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring focus:bg-accent focus:text-accent-foreground hover:bg-accent hover:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
          inset && "pl-8",
          className
        )}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        data-disabled={disabled ? "" : undefined}
        {...props}
      />
    );
  }
);
DropdownMenuItem.displayName = "DropdownMenuItem";

const DropdownMenuSeparator = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      role="separator"
      aria-orientation="horizontal"
      className={cn("-mx-1 my-1 h-px bg-muted", className)}
      {...props}
    />
  )
);
DropdownMenuSeparator.displayName = "DropdownMenuSeparator";

const DropdownMenuGroup = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} role="group" className={cn("space-y-1", className)} {...props} />
  )
);
DropdownMenuGroup.displayName = "DropdownMenuGroup";

export {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuGroup,
};
