import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Track whether an element is intersecting the viewport.
 *
 * Returns a `[callbackRef, isIntersecting]` tuple.  Attach the callback ref to
 * the target element — the observer is (re-)created automatically whenever the
 * element mounts, unmounts, or changes, which makes it safe for conditionally
 * rendered elements.
 *
 * The previous `RefObject`-based overload is still supported for backwards
 * compatibility but is **not** recommended for elements that mount later or
 * conditionally.
 */

// --- Overload 1: callback-ref API (preferred) ---
export function useIntersectionObserver(
  options?: IntersectionObserverInit,
): [React.RefCallback<Element>, boolean];

// --- Overload 2: legacy ref-object API ---
export function useIntersectionObserver(
  ref: React.RefObject<Element | null>,
  options?: IntersectionObserverInit,
): boolean;

// --- Implementation ---
export function useIntersectionObserver(
  refOrOptions?: React.RefObject<Element | null> | IntersectionObserverInit,
  maybeOptions?: IntersectionObserverInit,
): [React.RefCallback<Element>, boolean] | boolean {
  // Distinguish the two overloads: RefObject has a `current` property.
  const isRefOverload =
    refOrOptions != null &&
    typeof refOrOptions === 'object' &&
    'current' in refOrOptions;

  const legacyRef = isRefOverload
    ? (refOrOptions as React.RefObject<Element | null>)
    : null;
  const options = isRefOverload
    ? maybeOptions
    : (refOrOptions as IntersectionObserverInit | undefined);

  const [element, setElement] = useState<Element | null>(null);
  const [isIntersecting, setIsIntersecting] = useState(false);
  const optionsRef = useRef(options);

  // Callback ref for the preferred API.
  const callbackRef = useCallback((node: Element | null) => {
    setElement(node);
  }, []);

  // Legacy ref: sync ref.current → element state on every render.
  const prevLegacyCurrent = useRef<Element | null>(null);
  if (legacyRef && legacyRef.current !== prevLegacyCurrent.current) {
    prevLegacyCurrent.current = legacyRef.current;
    setElement(legacyRef.current);
  }

  useEffect(() => {
    if (!element) {
      setIsIntersecting(false);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => setIsIntersecting(entry?.isIntersecting ?? false),
      optionsRef.current,
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [element]);

  if (legacyRef) return isIntersecting;
  return [callbackRef, isIntersecting];
}
