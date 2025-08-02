import { renderHook, act } from '@testing-library/react';
import { useDebounce } from '@/hooks/useDebounce';

describe('useDebounce Hook', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('returns initial value immediately', () => {
    const { result } = renderHook(() => useDebounce('initial value'));
    
    expect(result.current).toBe('initial value');
  });

  it('debounces value changes with default delay', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value),
      { initialProps: { value: 'initial' } }
    );

    expect(result.current).toBe('initial');

    // Update value
    rerender({ value: 'updated' });
    
    // Value should not change immediately
    expect(result.current).toBe('initial');

    // Fast forward time but not enough
    act(() => {
      jest.advanceTimersByTime(400);
    });
    expect(result.current).toBe('initial');

    // Fast forward past default delay (500ms)
    act(() => {
      jest.advanceTimersByTime(100);
    });
    expect(result.current).toBe('updated');
  });

  it('uses custom delay', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 1000),
      { initialProps: { value: 'initial' } }
    );

    expect(result.current).toBe('initial');

    rerender({ value: 'updated' });
    
    // Should not update after 500ms
    act(() => {
      jest.advanceTimersByTime(500);
    });
    expect(result.current).toBe('initial');

    // Should update after 1000ms
    act(() => {
      jest.advanceTimersByTime(500);
    });
    expect(result.current).toBe('updated');
  });

  it('cancels pending updates when value changes again', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 500),
      { initialProps: { value: 'first' } }
    );

    expect(result.current).toBe('first');

    // First update
    rerender({ value: 'second' });
    
    act(() => {
      jest.advanceTimersByTime(300);
    });
    expect(result.current).toBe('first');

    // Second update before first completes
    rerender({ value: 'third' });
    
    // Advance past first timer
    act(() => {
      jest.advanceTimersByTime(300);
    });
    // Should still be initial value because first update was cancelled
    expect(result.current).toBe('first');

    // Complete second timer
    act(() => {
      jest.advanceTimersByTime(200);
    });
    expect(result.current).toBe('third');
  });

  it('handles rapid successive updates', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 300),
      { initialProps: { value: 'a' } }
    );

    // Rapid updates
    rerender({ value: 'ab' });
    act(() => jest.advanceTimersByTime(100));
    
    rerender({ value: 'abc' });
    act(() => jest.advanceTimersByTime(100));
    
    rerender({ value: 'abcd' });
    act(() => jest.advanceTimersByTime(100));
    
    // None should have applied yet
    expect(result.current).toBe('a');

    // Complete the last timer
    act(() => jest.advanceTimersByTime(200));
    expect(result.current).toBe('abcd');
  });

  it('works with different data types', () => {
    // Number
    const { result: numberResult, rerender: rerenderNumber } = renderHook(
      ({ value }) => useDebounce(value, 100),
      { initialProps: { value: 42 } }
    );
    
    rerenderNumber({ value: 100 });
    act(() => jest.advanceTimersByTime(100));
    expect(numberResult.current).toBe(100);

    // Object
    const { result: objectResult, rerender: rerenderObject } = renderHook(
      ({ value }) => useDebounce(value, 100),
      { initialProps: { value: { count: 1 } } }
    );
    
    const newObject = { count: 2 };
    rerenderObject({ value: newObject });
    act(() => jest.advanceTimersByTime(100));
    expect(objectResult.current).toBe(newObject);

    // Array
    const { result: arrayResult, rerender: rerenderArray } = renderHook(
      ({ value }) => useDebounce(value, 100),
      { initialProps: { value: [1, 2, 3] } }
    );
    
    const newArray = [4, 5, 6];
    rerenderArray({ value: newArray });
    act(() => jest.advanceTimersByTime(100));
    expect(arrayResult.current).toBe(newArray);
  });

  it('handles null and undefined values', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 200),
      { initialProps: { value: null as string | null } }
    );

    expect(result.current).toBeNull();

    rerender({ value: 'value' });
    act(() => jest.advanceTimersByTime(200));
    expect(result.current).toBe('value');

    rerender({ value: undefined as string | undefined });
    act(() => jest.advanceTimersByTime(200));
    expect(result.current).toBeUndefined();
  });

  it('cleans up timeout on unmount', () => {
    const clearTimeoutSpy = jest.spyOn(global, 'clearTimeout');
    
    const { unmount, rerender } = renderHook(
      ({ value }) => useDebounce(value, 500),
      { initialProps: { value: 'initial' } }
    );

    rerender({ value: 'updated' });
    
    // Unmount before timeout completes
    unmount();

    expect(clearTimeoutSpy).toHaveBeenCalled();
    clearTimeoutSpy.mockRestore();
  });

  it('handles delay changes', () => {
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: 'initial', delay: 500 } }
    );

    expect(result.current).toBe('initial');

    // Change both value and delay
    rerender({ value: 'updated', delay: 200 });
    
    // Old timer should be cancelled, new one with 200ms delay
    act(() => {
      jest.advanceTimersByTime(200);
    });
    expect(result.current).toBe('updated');
  });

  describe('Real-world scenarios', () => {
    it('debounces search input', () => {
      const mockSearch = jest.fn();
      
      const { result, rerender } = renderHook(
        ({ query }) => {
          const debouncedQuery = useDebounce(query, 300);
          return debouncedQuery;
        },
        { initialProps: { query: '' } }
      );

      // User types "react"
      rerender({ query: 'r' });
      act(() => jest.advanceTimersByTime(100));
      
      rerender({ query: 're' });
      act(() => jest.advanceTimersByTime(100));
      
      rerender({ query: 'rea' });
      act(() => jest.advanceTimersByTime(100));
      
      rerender({ query: 'reac' });
      act(() => jest.advanceTimersByTime(100));
      
      rerender({ query: 'react' });
      
      // No search should have been triggered yet
      if (result.current) mockSearch(result.current);
      expect(mockSearch).not.toHaveBeenCalled();

      // Complete debounce
      act(() => jest.advanceTimersByTime(300));
      
      // Now search should be triggered with final value
      if (result.current) mockSearch(result.current);
      expect(mockSearch).toHaveBeenCalledWith('react');
    });

    it('debounces API calls', () => {
      const mockApiCall = jest.fn();
      
      const { rerender } = renderHook(
        ({ filters }) => {
          const debouncedFilters = useDebounce(filters, 500);
          
          // Simulate effect that makes API call
          if (debouncedFilters) {
            mockApiCall(debouncedFilters);
          }
          
          return debouncedFilters;
        },
        { initialProps: { filters: { category: 'all' } } }
      );

      // Multiple filter changes
      rerender({ filters: { category: 'electronics' } });
      rerender({ filters: { category: 'electronics', price: 100 } });
      rerender({ filters: { category: 'electronics', price: 100, brand: 'Apple' } });

      // No API calls yet
      expect(mockApiCall).toHaveBeenCalledTimes(1); // Initial render

      // Complete debounce
      act(() => jest.advanceTimersByTime(500));
      
      // Should call with final filters
      expect(mockApiCall).toHaveBeenCalledWith({
        category: 'electronics',
        price: 100,
        brand: 'Apple'
      });
    });

    it('handles form validation debouncing', () => {
      const mockValidate = jest.fn();
      
      const { result, rerender } = renderHook(
        ({ email }) => {
          const debouncedEmail = useDebounce(email, 400);
          return { email, debouncedEmail };
        },
        { initialProps: { email: '' } }
      );

      // User types email
      rerender({ email: 'user' });
      expect(result.current.email).toBe('user');
      expect(result.current.debouncedEmail).toBe('');

      rerender({ email: 'user@' });
      rerender({ email: 'user@example' });
      rerender({ email: 'user@example.com' });

      // Validation shouldn't run until debounce completes
      if (result.current.debouncedEmail) {
        mockValidate(result.current.debouncedEmail);
      }
      expect(mockValidate).not.toHaveBeenCalled();

      act(() => jest.advanceTimersByTime(400));

      // Now validation can run
      if (result.current.debouncedEmail) {
        mockValidate(result.current.debouncedEmail);
      }
      expect(mockValidate).toHaveBeenCalledWith('user@example.com');
    });
  });

  describe('Edge cases', () => {
    it('handles zero delay', () => {
      const { result, rerender } = renderHook(
        ({ value }) => useDebounce(value, 0),
        { initialProps: { value: 'initial' } }
      );

      rerender({ value: 'updated' });
      
      // Should update immediately (next tick)
      act(() => {
        jest.advanceTimersByTime(0);
      });
      expect(result.current).toBe('updated');
    });

    it('handles negative delay as zero', () => {
      const { result, rerender } = renderHook(
        ({ value }) => useDebounce(value, -100),
        { initialProps: { value: 'initial' } }
      );

      rerender({ value: 'updated' });
      
      act(() => {
        jest.advanceTimersByTime(0);
      });
      expect(result.current).toBe('updated');
    });

    it('maintains referential equality for unchanged objects', () => {
      const obj = { data: 'test' };
      const { result, rerender } = renderHook(
        () => useDebounce(obj, 100)
      );

      const firstResult = result.current;
      
      // Rerender without changing the object
      rerender();
      
      act(() => jest.advanceTimersByTime(100));
      
      // Should be the same reference
      expect(result.current).toBe(firstResult);
    });
  });
});