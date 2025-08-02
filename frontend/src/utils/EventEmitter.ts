// Browser-compatible EventEmitter implementation
export class EventEmitter {
  private events: Map<string, Set<(...args: any[]) => void>> = new Map();
  private maxListeners = 10;

  on(event: string, listener: (...args: any[]) => void): this {
    if (!this.events.has(event)) {
      this.events.set(event, new Set());
    }
    this.events.get(event)!.add(listener);
    return this;
  }

  off(event: string, listener: (...args: any[]) => void): this {
    const listeners = this.events.get(event);
    if (listeners) {
      listeners.delete(listener);
      if (listeners.size === 0) {
        this.events.delete(event);
      }
    }
    return this;
  }

  emit(event: string, ...args: any[]): boolean {
    const listeners = this.events.get(event);
    if (!listeners || listeners.size === 0) {
      return false;
    }
    listeners.forEach(listener => {
      try {
        listener(...args);
      } catch (error) {
        console.error(`Error in event listener for "${event}":`, error);
      }
    });
    return true;
  }

  removeAllListeners(event?: string): this {
    if (event) {
      this.events.delete(event);
    } else {
      this.events.clear();
    }
    return this;
  }

  setMaxListeners(n: number): this {
    this.maxListeners = n;
    return this;
  }

  getMaxListeners(): number {
    return this.maxListeners;
  }

  listenerCount(event: string): number {
    const listeners = this.events.get(event);
    return listeners ? listeners.size : 0;
  }

  eventNames(): string[] {
    return Array.from(this.events.keys());
  }

  // Alias methods
  addListener = this.on;
  removeListener = this.off;
}