import React, { useRef, useState, useEffect, useCallback, useMemo } from 'react';
import { Box } from '@mui/material';
import { debounce } from 'lodash';

interface VirtualListProps<T> {
  items: T[];
  itemHeight: number | ((index: number) => number);
  renderItem: (item: T, index: number) => React.ReactNode;
  overscan?: number;
  height: string | number;
  width?: string | number;
  onScroll?: (scrollTop: number) => void;
  onEndReached?: () => void;
  endReachedThreshold?: number;
  estimatedItemHeight?: number;
  getItemKey?: (item: T, index: number) => string | number;
  className?: string;
}

interface VisibleRange {
  start: number;
  end: number;
}

export function VirtualList<T>({
  items,
  itemHeight,
  renderItem,
  overscan = 3,
  height,
  width = '100%',
  onScroll,
  onEndReached,
  endReachedThreshold = 100,
  estimatedItemHeight = 50,
  getItemKey,
  className,
}: VirtualListProps<T>) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [containerHeight, setContainerHeight] = useState(0);
  const [visibleRange, setVisibleRange] = useState<VisibleRange>({ start: 0, end: 0 });
  
  // Cache for dynamic heights
  const heightCache = useRef<Map<number, number>>(new Map());
  const itemRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  
  const isFixedHeight = typeof itemHeight === 'number';
  
  // Calculate item positions
  const itemPositions = useMemo(() => {
    const positions: number[] = [];
    let currentPosition = 0;
    
    for (let i = 0; i < items.length; i++) {
      positions[i] = currentPosition;
      
      if (isFixedHeight) {
        currentPosition += itemHeight;
      } else {
        const cachedHeight = heightCache.current.get(i);
        const height = cachedHeight || itemHeight(i) || estimatedItemHeight;
        currentPosition += height;
      }
    }
    
    return positions;
  }, [items.length, itemHeight, isFixedHeight, estimatedItemHeight]);
  
  const totalHeight = useMemo(() => {
    if (items.length === 0) return 0;
    
    const lastItemPosition = itemPositions[items.length - 1];
    if (isFixedHeight) {
      return lastItemPosition + itemHeight;
    } else {
      const lastItemHeight = heightCache.current.get(items.length - 1) || 
                            (typeof itemHeight === 'function' ? itemHeight(items.length - 1) : estimatedItemHeight);
      return lastItemPosition + lastItemHeight;
    }
  }, [items.length, itemPositions, itemHeight, isFixedHeight, estimatedItemHeight]);
  
  // Calculate visible range
  const calculateVisibleRange = useCallback((scrollTop: number, containerHeight: number) => {
    if (items.length === 0 || containerHeight === 0) {
      return { start: 0, end: 0 };
    }
    
    // Binary search for start index
    let start = 0;
    let end = items.length - 1;
    
    while (start < end) {
      const mid = Math.floor((start + end) / 2);
      if (itemPositions[mid] < scrollTop) {
        start = mid + 1;
      } else {
        end = mid;
      }
    }
    
    // Apply overscan
    start = Math.max(0, start - overscan);
    
    // Find end index
    const viewportEnd = scrollTop + containerHeight;
    end = start;
    
    while (end < items.length && itemPositions[end] < viewportEnd) {
      end++;
    }
    
    // Apply overscan
    end = Math.min(items.length - 1, end + overscan);
    
    return { start, end };
  }, [items.length, itemPositions, overscan]);
  
  // Update visible range on scroll
  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    const target = e.currentTarget;
    const newScrollTop = target.scrollTop;
    
    setScrollTop(newScrollTop);
    onScroll?.(newScrollTop);
    
    // Check if end reached
    if (onEndReached && newScrollTop + containerHeight >= totalHeight - endReachedThreshold) {
      onEndReached();
    }
  }, [containerHeight, totalHeight, endReachedThreshold, onScroll, onEndReached]);
  
  // Debounced scroll handler for performance
  const debouncedHandleScroll = useMemo(
    () => debounce(handleScroll, 16), // ~60fps
    [handleScroll]
  );
  
  // Update container height on resize
  useEffect(() => {
    const updateContainerHeight = () => {
      if (scrollContainerRef.current) {
        setContainerHeight(scrollContainerRef.current.clientHeight);
      }
    };
    
    updateContainerHeight();
    
    const resizeObserver = new ResizeObserver(updateContainerHeight);
    if (scrollContainerRef.current) {
      resizeObserver.observe(scrollContainerRef.current);
    }
    
    return () => {
      resizeObserver.disconnect();
    };
  }, []);
  
  // Update visible range when dependencies change
  useEffect(() => {
    const newRange = calculateVisibleRange(scrollTop, containerHeight);
    setVisibleRange(newRange);
  }, [scrollTop, containerHeight, calculateVisibleRange]);
  
  // Measure dynamic heights
  useEffect(() => {
    if (isFixedHeight) return;
    
    // Measure visible items
    itemRefs.current.forEach((element, index) => {
      if (index >= visibleRange.start && index <= visibleRange.end) {
        const height = element.getBoundingClientRect().height;
        const cachedHeight = heightCache.current.get(index);
        
        if (cachedHeight !== height) {
          heightCache.current.set(index, height);
          // Trigger re-render if height changed
          setVisibleRange(prev => ({ ...prev }));
        }
      }
    });
  }, [visibleRange, isFixedHeight]);
  
  // Render visible items
  const visibleItems = [];
  
  for (let i = visibleRange.start; i <= visibleRange.end; i++) {
    if (i >= items.length) break;
    
    const item = items[i];
    const key = getItemKey ? getItemKey(item, i) : i;
    const top = itemPositions[i];
    
    visibleItems.push(
      <Box
        key={key}
        ref={(el) => {
          if (el) {
            itemRefs.current.set(i, el);
          } else {
            itemRefs.current.delete(i);
          }
        }}
        sx={{
          position: 'absolute',
          top: `${top}px`,
          left: 0,
          right: 0,
          width: '100%',
        }}
      >
        {renderItem(item, i)}
      </Box>
    );
  }
  
  return (
    <Box
      ref={scrollContainerRef}
      className={className}
      onScroll={debouncedHandleScroll}
      sx={{
        height,
        width,
        overflow: 'auto',
        position: 'relative',
      }}
    >
      {/* Total height container */}
      <Box
        sx={{
          height: `${totalHeight}px`,
          position: 'relative',
        }}
      >
        {visibleItems}
      </Box>
    </Box>
  );
}

// Hook for virtual list state management
export const useVirtualList = <T,>(
  items: T[],
  options: {
    itemHeight: number | ((index: number) => number);
    containerHeight: number;
    overscan?: number;
  }
) => {
  const { itemHeight, containerHeight, overscan = 3 } = options;
  const [scrollTop, setScrollTop] = useState(0);
  
  const isFixedHeight = typeof itemHeight === 'number';
  
  const { visibleRange, totalHeight } = useMemo(() => {
    let start = 0;
    let end = 0;
    let totalHeight = 0;
    
    if (isFixedHeight) {
      totalHeight = items.length * itemHeight;
      start = Math.floor(scrollTop / itemHeight);
      end = Math.ceil((scrollTop + containerHeight) / itemHeight);
    } else {
      // For dynamic heights, simplified calculation
      // In production, you'd want to maintain a height cache
      let currentHeight = 0;
      for (let i = 0; i < items.length; i++) {
        const h = itemHeight(i);
        if (currentHeight < scrollTop && currentHeight + h > scrollTop) {
          start = i;
        }
        if (currentHeight < scrollTop + containerHeight) {
          end = i;
        }
        currentHeight += h;
      }
      totalHeight = currentHeight;
    }
    
    // Apply overscan
    start = Math.max(0, start - overscan);
    end = Math.min(items.length - 1, end + overscan);
    
    return {
      visibleRange: { start, end },
      totalHeight,
    };
  }, [items.length, itemHeight, containerHeight, scrollTop, overscan, isFixedHeight]);
  
  return {
    scrollTop,
    setScrollTop,
    visibleRange,
    totalHeight,
    visibleItems: items.slice(visibleRange.start, visibleRange.end + 1),
  };
};