import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { ScrollArea } from '@/components/ui/scroll-area';
import { 
  User, 
  MessageSquare, 
  Image as ImageIcon, 
  DollarSign,
  FileText,
  Calendar,
  Eye
} from 'lucide-react';
import { format } from 'date-fns';
import { cn } from '@/lib/utils';

interface SearchHit {
  id: string;
  score: number;
  source: any;
  highlight: Record<string, string[]>;
}

interface SearchResultGroup {
  total: number;
  hits: SearchHit[];
  aggregations?: any;
  error?: string;
}

interface SearchResultsProps {
  results: Record<string, SearchResultGroup>;
  query: string;
  onResultClick?: (type: string, id: string) => void;
}

export function SearchResults({ results, query, onResultClick }: SearchResultsProps) {
  const getIcon = (type: string) => {
    switch (type) {
      case 'models':
        return User;
      case 'messages':
        return MessageSquare;
      case 'media':
        return ImageIcon;
      case 'transactions':
        return DollarSign;
      case 'users':
        return User;
      default:
        return FileText;
    }
  };

  const getTypeLabel = (type: string) => {
    switch (type) {
      case 'models':
        return 'Models';
      case 'messages':
        return 'Messages';
      case 'media':
        return 'Media';
      case 'transactions':
        return 'Transactions';
      case 'users':
        return 'Users';
      default:
        return type;
    }
  };

  const renderHighlight = (highlight: Record<string, string[]>) => {
    const entries = Object.entries(highlight);
    if (entries.length === 0) return null;

    return (
      <div className="mt-2 space-y-1">
        {entries.map(([field, snippets]) => (
          <div key={field} className="text-sm text-muted-foreground">
            {snippets.map((snippet, index) => (
              <p
                key={index}
                dangerouslySetInnerHTML={{ __html: snippet }}
                className="line-clamp-2"
              />
            ))}
          </div>
        ))}
      </div>
    );
  };

  const renderModelResult = (hit: SearchHit) => {
    const model = hit.source;
    return (
      <div className="flex items-start space-x-3">
        <Avatar className="h-10 w-10">
          <AvatarImage src={model.avatar_url} alt={model.display_name} />
          <AvatarFallback>{model.display_name?.[0] || model.username?.[0]}</AvatarFallback>
        </Avatar>
        <div className="flex-1">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="font-medium">{model.display_name || model.username}</h4>
              <p className="text-sm text-muted-foreground">@{model.username}</p>
            </div>
            <div className="text-right text-sm">
              <p className="font-medium">${model.stats?.total_revenue || 0}</p>
              <p className="text-muted-foreground">{model.stats?.total_fans || 0} fans</p>
            </div>
          </div>
          {model.bio && (
            <p className="mt-1 text-sm text-muted-foreground line-clamp-2">{model.bio}</p>
          )}
          {renderHighlight(hit.highlight)}
        </div>
      </div>
    );
  };

  const renderMessageResult = (hit: SearchHit) => {
    const message = hit.source;
    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Badge variant={message.is_from_fan ? 'secondary' : 'default'}>
            {message.is_from_fan ? 'Fan' : 'Model'}
          </Badge>
          <span className="text-xs text-muted-foreground">
            {format(new Date(message.created_at), 'MMM d, yyyy h:mm a')}
          </span>
        </div>
        <p className="text-sm line-clamp-2">{message.content}</p>
        {message.tip_amount > 0 && (
          <Badge variant="outline" className="gap-1">
            <DollarSign className="h-3 w-3" />
            {message.tip_amount}
          </Badge>
        )}
        {renderHighlight(hit.highlight)}
      </div>
    );
  };

  const renderMediaResult = (hit: SearchHit) => {
    const media = hit.source;
    return (
      <div className="space-y-2">
        <div className="flex items-start justify-between">
          <div>
            <h4 className="font-medium">{media.title || media.original_filename}</h4>
            <p className="text-sm text-muted-foreground">
              {media.media_type} • {formatFileSize(media.file_size)}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {media.is_nsfw && <Badge variant="destructive">NSFW</Badge>}
            <Badge variant="outline" className="gap-1">
              <Eye className="h-3 w-3" />
              {media.view_count || 0}
            </Badge>
          </div>
        </div>
        {media.description && (
          <p className="text-sm text-muted-foreground line-clamp-2">{media.description}</p>
        )}
        {media.tags && media.tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {media.tags.slice(0, 5).map((tag: string) => (
              <Badge key={tag} variant="secondary" className="text-xs">
                {tag}
              </Badge>
            ))}
          </div>
        )}
        {renderHighlight(hit.highlight)}
      </div>
    );
  };

  const renderTransactionResult = (hit: SearchHit) => {
    const transaction = hit.source;
    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Badge variant={transaction.type === 'tip' ? 'default' : 'secondary'}>
              {transaction.type}
            </Badge>
            <Badge
              variant={
                transaction.status === 'completed'
                  ? 'success'
                  : transaction.status === 'failed'
                  ? 'destructive'
                  : 'secondary'
              }
            >
              {transaction.status}
            </Badge>
          </div>
          <span className="font-medium">
            ${transaction.amount} {transaction.currency}
          </span>
        </div>
        {transaction.description && (
          <p className="text-sm text-muted-foreground">{transaction.description}</p>
        )}
        <p className="text-xs text-muted-foreground">
          <Calendar className="inline h-3 w-3 mr-1" />
          {format(new Date(transaction.created_at), 'MMM d, yyyy h:mm a')}
        </p>
        {renderHighlight(hit.highlight)}
      </div>
    );
  };

  const renderResult = (type: string, hit: SearchHit) => {
    switch (type) {
      case 'models':
        return renderModelResult(hit);
      case 'messages':
        return renderMessageResult(hit);
      case 'media':
        return renderMediaResult(hit);
      case 'transactions':
        return renderTransactionResult(hit);
      default:
        return (
          <div>
            <pre className="text-xs">{JSON.stringify(hit.source, null, 2)}</pre>
            {renderHighlight(hit.highlight)}
          </div>
        );
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const hasResults = Object.values(results).some(group => group.hits.length > 0);

  if (!hasResults) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12">
          <p className="text-lg font-medium">No results found</p>
          <p className="text-sm text-muted-foreground mt-1">
            Try adjusting your search query for "{query}"
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {Object.entries(results).map(([type, group]) => {
        if (group.error) {
          return (
            <Card key={type}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  {React.createElement(getIcon(type), { className: 'h-5 w-5' })}
                  {getTypeLabel(type)}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-destructive">
                  Error searching {type}: {group.error}
                </p>
              </CardContent>
            </Card>
          );
        }

        if (group.hits.length === 0) return null;

        return (
          <Card key={type}>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {React.createElement(getIcon(type), { className: 'h-5 w-5' })}
                  {getTypeLabel(type)}
                </div>
                <Badge variant="secondary">{group.total} results</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[400px] pr-4">
                <div className="space-y-4">
                  {group.hits.map((hit) => (
                    <div
                      key={hit.id}
                      onClick={() => onResultClick?.(type, hit.id)}
                      className={cn(
                        'p-4 rounded-lg border bg-card',
                        'hover:bg-accent/50 cursor-pointer transition-colors'
                      )}
                    >
                      {renderResult(type, hit)}
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}