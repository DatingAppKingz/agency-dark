import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { SearchBar } from './SearchBar';
import { SearchResults } from './SearchResults';
import { SearchFilters } from './SearchFilters';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useToast } from '@/components/ui/use-toast';
import { searchApi } from '@/api/search';
import { Loader2, Save, History, TrendingUp } from 'lucide-react';

export function SearchPage() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [isSearching, setIsSearching] = useState(false);
  const [currentQuery, setCurrentQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any>(null);
  const [activeTab, setActiveTab] = useState('all');
  const [filters, setFilters] = useState<any>({});
  const [popularSearches, setPopularSearches] = useState<any[]>([]);
  const [savedSearches, setSavedSearches] = useState<any[]>([]);

  // Perform search
  const handleSearch = useCallback(async (query: string, searchFilters?: any) => {
    if (!query.trim()) return;

    setIsSearching(true);
    setCurrentQuery(query);
    
    try {
      let response;
      
      if (activeTab === 'all') {
        response = await searchApi.searchAll({
          query,
          filters: searchFilters || filters,
          size: 20,
          offset: 0,
        });
      } else {
        // Type-specific search
        const searchMethod = {
          models: searchApi.searchModels,
          messages: searchApi.searchMessages,
          media: searchApi.searchMedia,
          transactions: searchApi.searchTransactions,
        }[activeTab];

        if (searchMethod) {
          response = await searchMethod({
            query,
            ...filters,
            size: 50,
            offset: 0,
          });
        }
      }

      if (response) {
        if (activeTab === 'all') {
          setSearchResults(response.data);
        } else {
          // Convert single type result to multi-type format
          setSearchResults({
            query,
            total_results: response.data.total,
            results_by_type: {
              [activeTab]: response.data,
            },
          });
        }
      }
    } catch (error) {
      console.error('Search error:', error);
      toast({
        title: 'Search failed',
        description: 'An error occurred while searching. Please try again.',
        variant: 'destructive',
      });
    } finally {
      setIsSearching(false);
    }
  }, [activeTab, filters, toast]);

  // Handle result click
  const handleResultClick = useCallback((type: string, id: string) => {
    switch (type) {
      case 'models':
        navigate(`/models/${id}`);
        break;
      case 'messages':
        navigate(`/messages?highlight=${id}`);
        break;
      case 'media':
        navigate(`/media/${id}`);
        break;
      case 'transactions':
        navigate(`/transactions/${id}`);
        break;
      case 'users':
        navigate(`/users/${id}`);
        break;
    }
  }, [navigate]);

  // Save search
  const handleSaveSearch = useCallback(async () => {
    if (!currentQuery) return;

    try {
      const response = await searchApi.saveSearch({
        name: currentQuery,
        query: currentQuery,
        filters,
        search_type: activeTab,
      });

      toast({
        title: 'Search saved',
        description: 'Your search has been saved successfully.',
      });

      // Refresh saved searches
      loadSavedSearches();
    } catch (error) {
      console.error('Failed to save search:', error);
      toast({
        title: 'Failed to save search',
        description: 'An error occurred while saving your search.',
        variant: 'destructive',
      });
    }
  }, [currentQuery, filters, activeTab, toast]);

  // Load saved searches
  const loadSavedSearches = useCallback(async () => {
    try {
      const response = await searchApi.getSavedSearches();
      setSavedSearches(response.data);
    } catch (error) {
      console.error('Failed to load saved searches:', error);
    }
  }, []);

  // Load popular searches
  const loadPopularSearches = useCallback(async () => {
    try {
      const response = await searchApi.getPopularSearches(10);
      setPopularSearches(response.data);
    } catch (error) {
      console.error('Failed to load popular searches:', error);
    }
  }, []);

  // Load initial data
  React.useEffect(() => {
    loadSavedSearches();
    loadPopularSearches();
  }, [loadSavedSearches, loadPopularSearches]);

  return (
    <div className="container mx-auto py-6 space-y-6">
      {/* Search Header */}
      <div className="space-y-4">
        <h1 className="text-3xl font-bold">Search</h1>
        <SearchBar
          onSearch={handleSearch}
          autoFocus
          className="max-w-2xl"
        />
      </div>

      {/* Search Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full max-w-2xl grid-cols-5">
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="models">Models</TabsTrigger>
          <TabsTrigger value="messages">Messages</TabsTrigger>
          <TabsTrigger value="media">Media</TabsTrigger>
          <TabsTrigger value="transactions">Transactions</TabsTrigger>
        </TabsList>

        <div className="mt-6 grid gap-6 lg:grid-cols-4">
          {/* Filters Sidebar */}
          <div className="lg:col-span-1 space-y-4">
            {/* Quick Actions */}
            {currentQuery && searchResults && (
              <Card>
                <CardContent className="p-4">
                  <Button
                    onClick={handleSaveSearch}
                    className="w-full"
                    variant="outline"
                    size="sm"
                  >
                    <Save className="mr-2 h-4 w-4" />
                    Save Search
                  </Button>
                </CardContent>
              </Card>
            )}

            {/* Filters */}
            {activeTab !== 'all' && (
              <SearchFilters
                type={activeTab}
                filters={filters}
                onFiltersChange={setFilters}
                onApply={() => handleSearch(currentQuery)}
              />
            )}

            {/* Saved Searches */}
            {savedSearches.length > 0 && (
              <Card>
                <CardContent className="p-4">
                  <h3 className="font-medium mb-3 flex items-center gap-2">
                    <History className="h-4 w-4" />
                    Saved Searches
                  </h3>
                  <div className="space-y-2">
                    {savedSearches.slice(0, 5).map((search) => (
                      <button
                        key={search.id}
                        onClick={() => {
                          setActiveTab(search.search_type);
                          setFilters(search.filters || {});
                          handleSearch(search.query, search.filters);
                        }}
                        className="w-full text-left text-sm p-2 rounded hover:bg-accent"
                      >
                        <p className="font-medium truncate">{search.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {search.search_type}
                        </p>
                      </button>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Popular Searches */}
            {popularSearches.length > 0 && (
              <Card>
                <CardContent className="p-4">
                  <h3 className="font-medium mb-3 flex items-center gap-2">
                    <TrendingUp className="h-4 w-4" />
                    Popular Searches
                  </h3>
                  <div className="space-y-2">
                    {popularSearches.map((search, index) => (
                      <button
                        key={index}
                        onClick={() => handleSearch(search.query)}
                        className="w-full text-left text-sm p-2 rounded hover:bg-accent"
                      >
                        <p className="truncate">{search.query}</p>
                        <p className="text-xs text-muted-foreground">
                          {search.count} searches
                        </p>
                      </button>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Search Results */}
          <div className="lg:col-span-3">
            {isSearching ? (
              <Card>
                <CardContent className="flex items-center justify-center py-12">
                  <div className="text-center space-y-3">
                    <Loader2 className="h-8 w-8 animate-spin mx-auto" />
                    <p className="text-sm text-muted-foreground">Searching...</p>
                  </div>
                </CardContent>
              </Card>
            ) : searchResults ? (
              <SearchResults
                results={searchResults.results_by_type || {}}
                query={searchResults.query}
                onResultClick={handleResultClick}
              />
            ) : (
              <Card>
                <CardContent className="flex items-center justify-center py-12">
                  <div className="text-center space-y-3">
                    <p className="text-lg font-medium">Start searching</p>
                    <p className="text-sm text-muted-foreground">
                      Enter a query to search across all your data
                    </p>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </Tabs>
    </div>
  );
}