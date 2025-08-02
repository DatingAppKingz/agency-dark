// import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Badge } from '@/components/ui/badge';
import { CalendarIcon, X } from 'lucide-react';
import { format } from 'date-fns';
import { cn } from '@/lib/utils';

interface SearchFiltersProps {
  type: string;
  filters: any;
  onFiltersChange: (filters: any) => void;
  onApply: () => void;
}

export function SearchFilters({ type, filters, onFiltersChange, onApply }: SearchFiltersProps) {
  const updateFilter = (key: string, value: any) => {
    if (value === undefined || value === null || value === '') {
      const { [key]: _, ...rest } = filters;
      onFiltersChange(rest);
    } else {
      onFiltersChange({ ...filters, [key]: value });
    }
  };

  const renderModelFilters = () => (
    <>
      <div className="space-y-2">
        <Label htmlFor="platform">Platform</Label>
        <Select
          value={filters.platform || ''}
          onValueChange={(value) => updateFilter('platform', value || undefined)}
        >
          <SelectTrigger id="platform">
            <SelectValue placeholder="All platforms" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">All platforms</SelectItem>
            <SelectItem value="onlyfans">OnlyFans</SelectItem>
            <SelectItem value="fansly">Fansly</SelectItem>
            <SelectItem value="chaturbate">Chaturbate</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label htmlFor="is_active">Active only</Label>
          <Switch
            id="is_active"
            checked={filters.is_active || false}
            onCheckedChange={(checked) => updateFilter('is_active', checked || undefined)}
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label>Revenue Range</Label>
        <div className="grid grid-cols-2 gap-2">
          <Input
            type="number"
            placeholder="Min"
            value={filters.min_revenue || ''}
            onChange={(e) => updateFilter('min_revenue', e.target.value ? Number(e.target.value) : undefined)}
          />
          <Input
            type="number"
            placeholder="Max"
            value={filters.max_revenue || ''}
            onChange={(e) => updateFilter('max_revenue', e.target.value ? Number(e.target.value) : undefined)}
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label>Fan Count Range</Label>
        <div className="grid grid-cols-2 gap-2">
          <Input
            type="number"
            placeholder="Min"
            value={filters.min_fans || ''}
            onChange={(e) => updateFilter('min_fans', e.target.value ? Number(e.target.value) : undefined)}
          />
          <Input
            type="number"
            placeholder="Max"
            value={filters.max_fans || ''}
            onChange={(e) => updateFilter('max_fans', e.target.value ? Number(e.target.value) : undefined)}
          />
        </div>
      </div>
    </>
  );

  const renderMessageFilters = () => (
    <>
      <div className="space-y-2">
        <Label htmlFor="model_id">Model</Label>
        <Input
          id="model_id"
          placeholder="Model ID"
          value={filters.model_id || ''}
          onChange={(e) => updateFilter('model_id', e.target.value || undefined)}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="fan_id">Fan</Label>
        <Input
          id="fan_id"
          placeholder="Fan ID"
          value={filters.fan_id || ''}
          onChange={(e) => updateFilter('fan_id', e.target.value || undefined)}
        />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label htmlFor="has_media">Has media</Label>
          <Switch
            id="has_media"
            checked={filters.has_media || false}
            onCheckedChange={(checked) => updateFilter('has_media', checked || undefined)}
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="sentiment">Sentiment</Label>
        <Select
          value={filters.sentiment || ''}
          onValueChange={(value) => updateFilter('sentiment', value || undefined)}
        >
          <SelectTrigger id="sentiment">
            <SelectValue placeholder="All sentiments" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">All sentiments</SelectItem>
            <SelectItem value="positive">Positive</SelectItem>
            <SelectItem value="negative">Negative</SelectItem>
            <SelectItem value="neutral">Neutral</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label>Date Range</Label>
        <div className="space-y-2">
          <Popover>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                className={cn(
                  "w-full justify-start text-left font-normal",
                  !filters.date_from && "text-muted-foreground"
                )}
              >
                <CalendarIcon className="mr-2 h-4 w-4" />
                {filters.date_from ? format(new Date(filters.date_from), 'PPP') : 'From date'}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0">
              <Calendar
                mode="single"
                selected={filters.date_from ? new Date(filters.date_from) : undefined}
                onSelect={(date) => updateFilter('date_from', date?.toISOString())}
                initialFocus
              />
            </PopoverContent>
          </Popover>

          <Popover>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                className={cn(
                  "w-full justify-start text-left font-normal",
                  !filters.date_to && "text-muted-foreground"
                )}
              >
                <CalendarIcon className="mr-2 h-4 w-4" />
                {filters.date_to ? format(new Date(filters.date_to), 'PPP') : 'To date'}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0">
              <Calendar
                mode="single"
                selected={filters.date_to ? new Date(filters.date_to) : undefined}
                onSelect={(date) => updateFilter('date_to', date?.toISOString())}
                initialFocus
              />
            </PopoverContent>
          </Popover>
        </div>
      </div>
    </>
  );

  const renderMediaFilters = () => (
    <>
      <div className="space-y-2">
        <Label htmlFor="media_type">Media Type</Label>
        <Select
          value={filters.media_type || ''}
          onValueChange={(value) => updateFilter('media_type', value || undefined)}
        >
          <SelectTrigger id="media_type">
            <SelectValue placeholder="All types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">All types</SelectItem>
            <SelectItem value="image">Image</SelectItem>
            <SelectItem value="video">Video</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label>Tags</Label>
        <div className="space-y-2">
          <Input
            placeholder="Add tag..."
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                const value = e.currentTarget.value.trim();
                if (value) {
                  const tags = filters.tags || [];
                  if (!tags.includes(value)) {
                    updateFilter('tags', [...tags, value]);
                    e.currentTarget.value = '';
                  }
                }
              }
            }}
          />
          {filters.tags && filters.tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {filters.tags.map((tag: string) => (
                <Badge key={tag} variant="secondary" className="pr-1">
                  {tag}
                  <button
                    onClick={() => {
                      updateFilter('tags', filters.tags.filter((t: string) => t !== tag));
                    }}
                    className="ml-1 hover:text-destructive"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label htmlFor="is_nsfw">NSFW only</Label>
          <Switch
            id="is_nsfw"
            checked={filters.is_nsfw || false}
            onCheckedChange={(checked) => updateFilter('is_nsfw', checked || undefined)}
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label>File Size Range (MB)</Label>
        <div className="grid grid-cols-2 gap-2">
          <Input
            type="number"
            placeholder="Min"
            value={filters.min_size ? filters.min_size / (1024 * 1024) : ''}
            onChange={(e) => updateFilter('min_size', e.target.value ? Number(e.target.value) * 1024 * 1024 : undefined)}
          />
          <Input
            type="number"
            placeholder="Max"
            value={filters.max_size ? filters.max_size / (1024 * 1024) : ''}
            onChange={(e) => updateFilter('max_size', e.target.value ? Number(e.target.value) * 1024 * 1024 : undefined)}
          />
        </div>
      </div>
    </>
  );

  const renderTransactionFilters = () => (
    <>
      <div className="space-y-2">
        <Label htmlFor="transaction_type">Type</Label>
        <Select
          value={filters.transaction_type || ''}
          onValueChange={(value) => updateFilter('transaction_type', value || undefined)}
        >
          <SelectTrigger id="transaction_type">
            <SelectValue placeholder="All types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">All types</SelectItem>
            <SelectItem value="tip">Tip</SelectItem>
            <SelectItem value="subscription">Subscription</SelectItem>
            <SelectItem value="ppv">PPV</SelectItem>
            <SelectItem value="message">Message</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="status">Status</Label>
        <Select
          value={filters.status || ''}
          onValueChange={(value) => updateFilter('status', value || undefined)}
        >
          <SelectTrigger id="status">
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">All statuses</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="failed">Failed</SelectItem>
            <SelectItem value="refunded">Refunded</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label>Amount Range</Label>
        <div className="grid grid-cols-2 gap-2">
          <Input
            type="number"
            placeholder="Min"
            value={filters.min_amount || ''}
            onChange={(e) => updateFilter('min_amount', e.target.value ? Number(e.target.value) : undefined)}
          />
          <Input
            type="number"
            placeholder="Max"
            value={filters.max_amount || ''}
            onChange={(e) => updateFilter('max_amount', e.target.value ? Number(e.target.value) : undefined)}
          />
        </div>
      </div>
    </>
  );

  const renderFilters = () => {
    switch (type) {
      case 'models':
        return renderModelFilters();
      case 'messages':
        return renderMessageFilters();
      case 'media':
        return renderMediaFilters();
      case 'transactions':
        return renderTransactionFilters();
      default:
        return null;
    }
  };

  const hasFilters = Object.keys(filters).length > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Filters</span>
          {hasFilters && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onFiltersChange({})}
            >
              Clear
            </Button>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {renderFilters()}
        <Button onClick={onApply} className="w-full">
          Apply Filters
        </Button>
      </CardContent>
    </Card>
  );
}