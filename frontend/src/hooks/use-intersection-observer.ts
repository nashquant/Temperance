import { useEffect, useRef, useState } from 'react';

export function useIntersectionObserver(
  ref: React.RefObject<Element | null>,
  options?: IntersectionObserverInit,
): boolean {
  const [isIntersecting, setIsIntersecting] = useState(false);
  const optionsRef = useRef(options); // freeze options to keep effect stable

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new IntersectionObserver(
      ([entry]) => setIsIntersecting(entry?.isIntersecting ?? false),
      optionsRef.current,
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [ref]);

  return isIntersecting;
}
