// Accessibility utilities and helpers

// ARIA live region announcer for screen readers
export class AriaAnnouncer {
  private static instance: AriaAnnouncer;
  private announcer: HTMLDivElement;

  private constructor() {
    this.announcer = document.createElement('div');
    this.announcer.setAttribute('role', 'status');
    this.announcer.setAttribute('aria-live', 'polite');
    this.announcer.setAttribute('aria-atomic', 'true');
    this.announcer.style.position = 'absolute';
    this.announcer.style.left = '-10000px';
    this.announcer.style.width = '1px';
    this.announcer.style.height = '1px';
    this.announcer.style.overflow = 'hidden';
    document.body.appendChild(this.announcer);
  }

  static getInstance(): AriaAnnouncer {
    if (!AriaAnnouncer.instance) {
      AriaAnnouncer.instance = new AriaAnnouncer();
    }
    return AriaAnnouncer.instance;
  }

  announce(message: string, priority: 'polite' | 'assertive' = 'polite'): void {
    this.announcer.setAttribute('aria-live', priority);
    this.announcer.textContent = message;
    
    // Clear after announcement
    setTimeout(() => {
      this.announcer.textContent = '';
    }, 1000);
  }
}

// Focus management utilities
export const focusManagement = {
  // Trap focus within a container (useful for modals)
  trapFocus(container: HTMLElement): () => void {
    const focusableElements = container.querySelectorAll(
      'a[href], button, textarea, input[type="text"], input[type="radio"], input[type="checkbox"], select, [tabindex]:not([tabindex="-1"])'
    );
    
    const firstFocusable = focusableElements[0] as HTMLElement;
    const lastFocusable = focusableElements[focusableElements.length - 1] as HTMLElement;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;

      if (e.shiftKey) {
        if (document.activeElement === firstFocusable) {
          e.preventDefault();
          lastFocusable.focus();
        }
      } else {
        if (document.activeElement === lastFocusable) {
          e.preventDefault();
          firstFocusable.focus();
        }
      }
    };

    container.addEventListener('keydown', handleKeyDown);
    firstFocusable?.focus();

    return () => {
      container.removeEventListener('keydown', handleKeyDown);
    };
  },

  // Save and restore focus (useful for modals/drawers)
  saveFocus(): HTMLElement | null {
    return document.activeElement as HTMLElement;
  },

  restoreFocus(element: HTMLElement | null): void {
    if (element && typeof element.focus === 'function') {
      element.focus();
    }
  },
};

// Keyboard navigation helpers
export const keyboardNavigation = {
  // Handle arrow key navigation in lists
  handleListNavigation(
    e: KeyboardEvent,
    currentIndex: number,
    totalItems: number,
    onNavigate: (index: number) => void
  ): void {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        onNavigate((currentIndex + 1) % totalItems);
        break;
      case 'ArrowUp':
        e.preventDefault();
        onNavigate(currentIndex > 0 ? currentIndex - 1 : totalItems - 1);
        break;
      case 'Home':
        e.preventDefault();
        onNavigate(0);
        break;
      case 'End':
        e.preventDefault();
        onNavigate(totalItems - 1);
        break;
    }
  },

  // Check if user prefers reduced motion
  prefersReducedMotion(): boolean {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  },
};

// Color contrast utilities
export const colorContrast = {
  // Calculate relative luminance
  relativeLuminance(rgb: { r: number; g: number; b: number }): number {
    const { r, g, b } = rgb;
    const rsRGB = r / 255;
    const gsRGB = g / 255;
    const bsRGB = b / 255;

    const rLin = rsRGB <= 0.03928 ? rsRGB / 12.92 : Math.pow((rsRGB + 0.055) / 1.055, 2.4);
    const gLin = gsRGB <= 0.03928 ? gsRGB / 12.92 : Math.pow((gsRGB + 0.055) / 1.055, 2.4);
    const bLin = bsRGB <= 0.03928 ? bsRGB / 12.92 : Math.pow((bsRGB + 0.055) / 1.055, 2.4);

    return 0.2126 * rLin + 0.7152 * gLin + 0.0722 * bLin;
  },

  // Calculate contrast ratio between two colors
  contrastRatio(color1: { r: number; g: number; b: number }, color2: { r: number; g: number; b: number }): number {
    const lum1 = this.relativeLuminance(color1);
    const lum2 = this.relativeLuminance(color2);
    const lighter = Math.max(lum1, lum2);
    const darker = Math.min(lum1, lum2);
    return (lighter + 0.05) / (darker + 0.05);
  },

  // Check if contrast meets WCAG AA standards
  meetsWCAGAA(foreground: { r: number; g: number; b: number }, background: { r: number; g: number; b: number }, isLargeText: boolean = false): boolean {
    const ratio = this.contrastRatio(foreground, background);
    return isLargeText ? ratio >= 3 : ratio >= 4.5;
  },

  // Check if contrast meets WCAG AAA standards
  meetsWCAGAAA(foreground: { r: number; g: number; b: number }, background: { r: number; g: number; b: number }, isLargeText: boolean = false): boolean {
    const ratio = this.contrastRatio(foreground, background);
    return isLargeText ? ratio >= 4.5 : ratio >= 7;
  },
};

// Screen reader only text component
export const srOnly: React.CSSProperties = {
  position: 'absolute',
  width: '1px',
  height: '1px',
  padding: 0,
  margin: '-1px',
  overflow: 'hidden',
  clip: 'rect(0, 0, 0, 0)',
  whiteSpace: 'nowrap',
  border: 0,
};

// Accessible ID generator
let idCounter = 0;
export const generateId = (prefix: string = 'accessible'): string => {
  idCounter += 1;
  return `${prefix}-${idCounter}`;
};