import React, { useState, useCallback, useEffect, useRef } from 'react';
import { Search, X, Loader2 } from 'lucide-react';
import { useDebounce } from '@/hooks/useDebounce';
import { searchApi } from '@/api/search';
import { cn } from '@/lib/utils';

interface SearchBarProps {
  onSearch: (query: string) => void;
  placeholder?: string;
  className?: string;
  autoFocus?: boolean;
  showSuggestions?: boolean;
}

export function SearchBar({
  onSearch,
  placeholder = 'Search models, messages, media...',
  className,
  autoFocus = false,
  showSuggestions = true,
}: SearchBarProps) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [isLoadingSuggestions, setIsLoadingSuggestions] = useState(false);
  const [showSuggestionsDropdown, setShowSuggestionsDropdown] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);
  
  const debouncedQuery = useDebounce(query, 300);

  // Fetch suggestions
  useEffect(() => {
    if (debouncedQuery.length >= 2 && showSuggestions) {
      setIsLoadingSuggestions(true);
      searchApi.getSuggestions(debouncedQuery)
        .then((response) => {
          setSuggestions(response.data.suggestions);
          setShowSuggestionsDropdown(true);
        })
        .catch((error) => {
          console.error('Failed to fetch suggestions:', error);
          setSuggestions([]);
        })
        .finally(() => {
          setIsLoadingSuggestions(false);
        });
    } else {
      setSuggestions([]);
      setShowSuggestionsDropdown(false);
    }
  }, [debouncedQuery, showSuggestions]);

  // Handle click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        suggestionsRef.current &&
        !suggestionsRef.current.contains(event.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(event.target as Node)
      ) {
        setShowSuggestionsDropdown(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const handleSubmit = useCallback((e?: React.FormEvent) => {
    e?.preventDefault();
    if (query.trim()) {
      onSearch(query.trim());
      setShowSuggestionsDropdown(false);
    }
  }, [query, onSearch]);

  const handleSuggestionClick = useCallback((suggestion: string) => {
    setQuery(suggestion);
    onSearch(suggestion);
    setShowSuggestionsDropdown(false);
    inputRef.current?.focus();
  }, [onSearch]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (!showSuggestionsDropdown || suggestions.length === 0) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex((prev) => 
          prev < suggestions.length - 1 ? prev + 1 : 0
        );
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex((prev) => 
          prev > 0 ? prev - 1 : suggestions.length - 1
        );
        break;
      case 'Enter':
        e.preventDefault();
        if (selectedIndex >= 0) {
          handleSuggestionClick(suggestions[selectedIndex]);
        } else {
          handleSubmit();
        }
        break;
      case 'Escape':
        e.preventDefault();
        setShowSuggestionsDropdown(false);
        setSelectedIndex(-1);
        break;
    }
  }, [showSuggestionsDropdown, suggestions, selectedIndex, handleSuggestionClick, handleSubmit]);

  const clearSearch = useCallback(() => {
    setQuery('');
    setSuggestions([]);
    setShowSuggestionsDropdown(false);
    inputRef.current?.focus();
  }, []);

  return (
    <div className={cn('relative', className)}>
      <form onSubmit={handleSubmit} className="relative">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => {
              if (suggestions.length > 0) {
                setShowSuggestionsDropdown(true);
              }
            }}
            placeholder={placeholder}
            autoFocus={autoFocus}
            className={cn(
              'h-10 w-full rounded-md border border-input bg-background pl-10 pr-10',
              'text-sm placeholder:text-muted-foreground',
              'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
              'disabled:cursor-not-allowed disabled:opacity-50'
            )}
          />
          {query && (
            <button
              type="button"
              onClick={clearSearch}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </form>

      {/* Suggestions dropdown */}
      {showSuggestionsDropdown && suggestions.length > 0 && (
        <div
          ref={suggestionsRef}
          className={cn(
            'absolute z-50 mt-1 w-full rounded-md border bg-popover p-1',
            'shadow-md animate-in fade-in-0 zoom-in-95'
          )}
        >
          {suggestions.map((suggestion, index) => (
            <button
              key={index}
              type="button"
              onClick={() => handleSuggestionClick(suggestion)}
              onMouseEnter={() => setSelectedIndex(index)}
              className={cn(
                'flex w-full items-center rounded-sm px-3 py-2 text-sm',
                'hover:bg-accent hover:text-accent-foreground',
                'focus:bg-accent focus:text-accent-foreground focus:outline-none',
                selectedIndex === index && 'bg-accent text-accent-foreground'
              )}
            >
              <Search className="mr-2 h-3 w-3 text-muted-foreground" />
              <span className="flex-1 text-left">{suggestion}</span>
            </button>
          ))}
        </div>
      )}

      {/* Loading indicator */}
      {isLoadingSuggestions && (
        <div className="absolute right-12 top-1/2 -translate-y-1/2">
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        </div>
      )}
    </div>
  );
}