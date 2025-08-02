import React, { useState, useEffect } from 'react';
import {
  Database,
  Activity,
  RefreshCw,
  Trash2,
  AlertCircle,
  CheckCircle,
  BarChart3,
  Zap,
  TrendingUp,
  Clock
} from 'lucide-react';
// import { format } from 'date-fns';
import { apiClient } from '../services/api';
import { cn } from '../lib/utils';

interface CacheStats {
  memory_cache_size: number;
  write_behind_queue_size: number;
  refresh_tasks_count: number;
  redis_connected: boolean;
  redis_info?: {
    used_memory_human: string;
    connected_clients: number;
    total_commands_processed: number;
    keyspace_hits: number;
    keyspace_misses: number;
  };
  hit_rate?: {
    hits: number;
    misses: number;
    rate: string;
  };
}

interface CacheHealth {
  status: 'healthy' | 'warning' | 'unhealthy';
  issues: string[];
  details: any;
}

export const CacheMonitor: React.FC = () => {
  const [stats, setStats] = useState<CacheStats | null>(null);
  const [health, setHealth] = useState<CacheHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    fetchCacheData();
    const interval = setInterval(fetchCacheData, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchCacheData = async () => {
    try {
      const [statsResponse, healthResponse] = await Promise.all([
        apiClient.get('/cache/stats'),
        apiClient.get('/cache/health')
      ]);
      
      setStats(statsResponse.data);
      setHealth(healthResponse.data);
    } catch (error) {
      console.error('Failed to fetch cache data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchCacheData();
    setRefreshing(false);
  };

  const handleWarmup = async () => {
    try {
      await apiClient.post('/cache/warmup');
      // Show success notification
    } catch (error) {
      console.error('Failed to trigger cache warmup:', error);
    }
  };

  const handleCleanup = async () => {
    if (!confirm('Are you sure you want to clean up the cache?')) return;
    
    try {
      await apiClient.post('/cache/cleanup');
      await fetchCacheData();
    } catch (error) {
      console.error('Failed to trigger cache cleanup:', error);
    }
  };

  const handleInvalidateTag = async (tag: string) => {
    if (!confirm(`Invalidate all cache entries tagged with "${tag}"?`)) return;
    
    try {
      await apiClient.delete(`/cache/invalidate/tag/${tag}`);
      await fetchCacheData();
    } catch (error) {
      console.error('Failed to invalidate cache tag:', error);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-gray-400 animate-spin" />
      </div>
    );
  }

  const getHealthIcon = () => {
    if (!health) return null;
    
    switch (health.status) {
      case 'healthy':
        return <CheckCircle className="w-6 h-6 text-green-500" />;
      case 'warning':
        return <AlertCircle className="w-6 h-6 text-yellow-500" />;
      case 'unhealthy':
        return <AlertCircle className="w-6 h-6 text-red-500" />;
    }
  };

  const hitRate = stats?.hit_rate ? parseFloat(stats.hit_rate.rate) : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Database className="w-8 h-8 text-primary-400" />
          <h1 className="text-2xl font-bold text-white">Cache Monitor</h1>
        </div>
        
        <div className="flex items-center gap-3">
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className={cn(
              "flex items-center gap-2 px-4 py-2 bg-gray-700 text-white rounded-md hover:bg-gray-600 transition-colors",
              refreshing && "opacity-50 cursor-not-allowed"
            )}
          >
            <RefreshCw className={cn("w-4 h-4", refreshing && "animate-spin")} />
            Refresh
          </button>
          
          <button
            onClick={handleWarmup}
            className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 transition-colors"
          >
            <Zap className="w-4 h-4" />
            Warmup
          </button>
          
          <button
            onClick={handleCleanup}
            className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
          >
            <Trash2 className="w-4 h-4" />
            Cleanup
          </button>
        </div>
      </div>

      {/* Health Status */}
      {health && (
        <div className={cn(
          "rounded-lg p-6",
          health.status === 'healthy' ? "bg-green-900/20" : 
          health.status === 'warning' ? "bg-yellow-900/20" : "bg-red-900/20"
        )}>
          <div className="flex items-center gap-3 mb-4">
            {getHealthIcon()}
            <h2 className="text-lg font-semibold text-white">
              Cache Health: {health.status.charAt(0).toUpperCase() + health.status.slice(1)}
            </h2>
          </div>
          
          {health.issues.length > 0 && (
            <ul className="space-y-2">
              {health.issues.map((issue, index) => (
                <li key={index} className="text-sm text-gray-300 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-yellow-500" />
                  {issue}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Cache Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Hit Rate */}
        <div className="bg-gray-800 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-gray-400">Hit Rate</h3>
            <TrendingUp className="w-5 h-5 text-gray-500" />
          </div>
          <div className="space-y-2">
            <p className="text-3xl font-bold text-white">{stats?.hit_rate?.rate || '0%'}</p>
            <div className="w-full bg-gray-700 rounded-full h-2">
              <div
                className={cn(
                  "h-2 rounded-full transition-all duration-300",
                  hitRate >= 80 ? "bg-green-500" :
                  hitRate >= 60 ? "bg-yellow-500" : "bg-red-500"
                )}
                style={{ width: `${hitRate}%` }}
              />
            </div>
            <p className="text-xs text-gray-500">
              {stats?.hit_rate?.hits || 0} hits / {stats?.hit_rate?.misses || 0} misses
            </p>
          </div>
        </div>

        {/* Memory Usage */}
        <div className="bg-gray-800 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-gray-400">Memory Usage</h3>
            <Database className="w-5 h-5 text-gray-500" />
          </div>
          <div className="space-y-2">
            <p className="text-3xl font-bold text-white">
              {stats?.redis_info?.used_memory_human || 'N/A'}
            </p>
            <p className="text-sm text-gray-400">
              Memory Cache: {stats?.memory_cache_size || 0} items
            </p>
            <p className="text-sm text-gray-400">
              Connected Clients: {stats?.redis_info?.connected_clients || 0}
            </p>
          </div>
        </div>

        {/* Commands Processed */}
        <div className="bg-gray-800 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-gray-400">Commands</h3>
            <Activity className="w-5 h-5 text-gray-500" />
          </div>
          <div className="space-y-2">
            <p className="text-3xl font-bold text-white">
              {stats?.redis_info?.total_commands_processed?.toLocaleString() || '0'}
            </p>
            <p className="text-sm text-gray-400">Total processed</p>
            <p className="text-sm text-gray-400">
              Queue: {stats?.write_behind_queue_size || 0} pending
            </p>
          </div>
        </div>

        {/* Active Tasks */}
        <div className="bg-gray-800 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-gray-400">Active Tasks</h3>
            <Clock className="w-5 h-5 text-gray-500" />
          </div>
          <div className="space-y-2">
            <p className="text-3xl font-bold text-white">
              {stats?.refresh_tasks_count || 0}
            </p>
            <p className="text-sm text-gray-400">Refresh tasks running</p>
            <p className="text-sm text-gray-400">
              Status: {stats?.redis_connected ? 
                <span className="text-green-400">Connected</span> : 
                <span className="text-red-400">Disconnected</span>
              }
            </p>
          </div>
        </div>
      </div>

      {/* Cache Tags */}
      <div className="bg-gray-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Cache Tags</h2>
        <p className="text-sm text-gray-400 mb-4">
          Click on a tag to invalidate all associated cache entries
        </p>
        <div className="flex flex-wrap gap-2">
          {['user', 'model', 'agency', 'transaction', 'message', 'analytics', 'search', 'api'].map(tag => (
            <button
              key={tag}
              onClick={() => handleInvalidateTag(tag)}
              className="px-3 py-1 bg-gray-700 text-gray-300 rounded-full text-sm hover:bg-red-600 hover:text-white transition-colors"
            >
              {tag}
            </button>
          ))}
        </div>
      </div>

      {/* Performance Chart */}
      <div className="bg-gray-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Cache Performance</h2>
        <div className="h-64 flex items-center justify-center text-gray-500">
          <BarChart3 className="w-12 h-12" />
          <p className="ml-4">Performance charts coming soon...</p>
        </div>
      </div>
    </div>
  );
};