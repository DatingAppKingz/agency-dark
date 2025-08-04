import { QueryClient } from '@tanstack/react-query';
import { cacheService } from './cacheService';

interface OptimisticUpdate<TData, TVariables> {
  mutationKey: string[];
  updateFn: (oldData: TData, variables: TVariables) => TData;
  rollbackFn?: (oldData: TData, error: Error) => TData;
}

interface OptimisticTransaction {
  id: string;
  timestamp: number;
  mutations: Array<{
    key: string[];
    oldData: any;
    newData: any;
    status: 'pending' | 'committed' | 'rolled_back';
  }>;
}

class OptimisticUpdateService {
  private queryClient: QueryClient | null = null;
  private transactions: Map<string, OptimisticTransaction> = new Map();
  private rollbackHandlers: Map<string, () => void> = new Map();

  setQueryClient(client: QueryClient) {
    this.queryClient = client;
  }

  // Perform optimistic update
  async performOptimisticUpdate<TData, TVariables>({
    mutationKey,
    variables,
    updateFn,
    rollbackFn,
    mutationFn,
  }: {
    mutationKey: string[];
    variables: TVariables;
    updateFn: (oldData: TData, variables: TVariables) => TData;
    rollbackFn?: (oldData: TData, error: Error) => TData;
    mutationFn: (variables: TVariables) => Promise<TData>;
  }): Promise<TData> {
    if (!this.queryClient) {
      throw new Error('QueryClient not set');
    }

    const transactionId = this.generateTransactionId();
    const transaction: OptimisticTransaction = {
      id: transactionId,
      timestamp: Date.now(),
      mutations: [],
    };

    try {
      // Get current data
      const oldData = this.queryClient.getQueryData<TData>(mutationKey);
      
      if (oldData === undefined) {
        // No cached data, perform regular mutation
        const result = await mutationFn(variables);
        this.queryClient.setQueryData(mutationKey, result);
        return result;
      }

      // Apply optimistic update
      const optimisticData = updateFn(oldData, variables);
      
      // Update query cache
      this.queryClient.setQueryData(mutationKey, optimisticData);
      
      // Update custom cache
      const cacheKey = cacheService.generateKey(mutationKey.join(':'));
      cacheService.set(cacheKey, optimisticData);

      // Record transaction
      transaction.mutations.push({
        key: mutationKey,
        oldData,
        newData: optimisticData,
        status: 'pending',
      });
      this.transactions.set(transactionId, transaction);

      // Set up rollback handler
      this.rollbackHandlers.set(transactionId, () => {
        if (rollbackFn) {
          const rolledBackData = rollbackFn(oldData, new Error('Mutation failed'));
          this.queryClient!.setQueryData(mutationKey, rolledBackData);
          cacheService.set(cacheKey, rolledBackData);
        } else {
          // Default rollback: restore old data
          this.queryClient!.setQueryData(mutationKey, oldData);
          cacheService.set(cacheKey, oldData);
        }
      });

      // Perform actual mutation
      const result = await mutationFn(variables);

      // Commit transaction
      this.commitTransaction(transactionId);

      // Update with server response
      this.queryClient.setQueryData(mutationKey, result);
      cacheService.set(cacheKey, result);

      return result;
    } catch (error) {
      // Rollback on error
      this.rollbackTransaction(transactionId);
      throw error;
    }
  }

  // Batch optimistic updates
  async batchOptimisticUpdates(
    updates: Array<{
      mutationKey: string[];
      variables: any;
      updateFn: (oldData: any, variables: any) => any;
      mutationFn: (variables: any) => Promise<any>;
    }>
  ): Promise<any[]> {
    const transactionId = this.generateTransactionId();
    const transaction: OptimisticTransaction = {
      id: transactionId,
      timestamp: Date.now(),
      mutations: [],
    };

    const rollbackActions: Array<() => void> = [];

    try {
      // Apply all optimistic updates
      for (const update of updates) {
        const oldData = this.queryClient!.getQueryData(update.mutationKey);
        if (oldData !== undefined) {
          const optimisticData = update.updateFn(oldData, update.variables);
          this.queryClient!.setQueryData(update.mutationKey, optimisticData);
          
          transaction.mutations.push({
            key: update.mutationKey,
            oldData,
            newData: optimisticData,
            status: 'pending',
          });

          rollbackActions.push(() => {
            this.queryClient!.setQueryData(update.mutationKey, oldData);
          });
        }
      }

      this.transactions.set(transactionId, transaction);

      // Perform all mutations
      const results = await Promise.all(
        updates.map(update => update.mutationFn(update.variables))
      );

      // Update with server responses
      updates.forEach((update, index) => {
        this.queryClient!.setQueryData(update.mutationKey, results[index]);
      });

      this.commitTransaction(transactionId);
      return results;
    } catch (error) {
      // Rollback all updates
      rollbackActions.forEach(rollback => rollback());
      this.rollbackTransaction(transactionId);
      throw error;
    }
  }

  // Optimistic delete with undo capability
  optimisticDelete<T>(
    queryKey: string[],
    itemId: string | number,
    deleteFn: () => Promise<void>,
    options?: {
      undoTimeout?: number;
      onUndo?: () => void;
    }
  ): { undo: () => void; commit: () => Promise<void> } {
    if (!this.queryClient) {
      throw new Error('QueryClient not set');
    }

    const oldData = this.queryClient.getQueryData<T[]>(queryKey);
    if (!oldData) {
      return {
        undo: () => {},
        commit: async () => await deleteFn(),
      };
    }

    // Apply optimistic delete
    const newData = oldData.filter((item: any) => item.id !== itemId);
    this.queryClient.setQueryData(queryKey, newData);

    let undoTimeout: NodeJS.Timeout | null = null;
    let isUndone = false;

    const undo = () => {
      if (!isUndone) {
        isUndone = true;
        if (undoTimeout) {
          clearTimeout(undoTimeout);
        }
        this.queryClient!.setQueryData(queryKey, oldData);
        options?.onUndo?.();
      }
    };

    const commit = async () => {
      if (!isUndone) {
        if (undoTimeout) {
          clearTimeout(undoTimeout);
        }
        try {
          await deleteFn();
        } catch (error) {
          // Rollback on error
          this.queryClient!.setQueryData(queryKey, oldData);
          throw error;
        }
      }
    };

    // Auto-commit after timeout
    if (options?.undoTimeout) {
      undoTimeout = setTimeout(() => {
        commit().catch(console.error);
      }, options.undoTimeout);
    }

    return { undo, commit };
  }

  // Optimistic reorder
  optimisticReorder<T extends { id: string | number; order?: number }>(
    queryKey: string[],
    items: T[],
    newOrder: Array<string | number>,
    reorderFn: (newOrder: Array<string | number>) => Promise<void>
  ) {
    if (!this.queryClient) {
      throw new Error('QueryClient not set');
    }

    const oldData = [...items];
    
    // Apply optimistic reorder
    const reorderedItems = newOrder.map((id, index) => {
      const item = items.find(item => item.id === id);
      return item ? { ...item, order: index } : null;
    }).filter(Boolean) as T[];

    this.queryClient.setQueryData(queryKey, reorderedItems);

    // Perform actual reorder
    reorderFn(newOrder).catch(() => {
      // Rollback on error
      this.queryClient!.setQueryData(queryKey, oldData);
    });
  }

  // Optimistic infinite query update
  optimisticInfiniteUpdate<T>(
    queryKey: string[],
    pageParam: any,
    newItem: T,
    addFn: () => Promise<T>
  ) {
    if (!this.queryClient) {
      throw new Error('QueryClient not set');
    }

    const oldData = this.queryClient.getQueryData(queryKey) as any;
    if (!oldData?.pages) return;

    // Add item to the first page optimistically
    const newData = {
      ...oldData,
      pages: [
        {
          ...oldData.pages[0],
          items: [newItem, ...oldData.pages[0].items],
        },
        ...oldData.pages.slice(1),
      ],
    };

    this.queryClient.setQueryData(queryKey, newData);

    // Perform actual add
    addFn()
      .then((serverItem) => {
        // Update with server response
        const updatedData = {
          ...oldData,
          pages: [
            {
              ...oldData.pages[0],
              items: [serverItem, ...oldData.pages[0].items.slice(1)],
            },
            ...oldData.pages.slice(1),
          ],
        };
        this.queryClient!.setQueryData(queryKey, updatedData);
      })
      .catch(() => {
        // Rollback on error
        this.queryClient!.setQueryData(queryKey, oldData);
      });
  }

  private generateTransactionId(): string {
    return `txn_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private commitTransaction(transactionId: string) {
    const transaction = this.transactions.get(transactionId);
    if (transaction) {
      transaction.mutations.forEach(mutation => {
        mutation.status = 'committed';
      });
    }
    this.rollbackHandlers.delete(transactionId);
  }

  private rollbackTransaction(transactionId: string) {
    const rollback = this.rollbackHandlers.get(transactionId);
    if (rollback) {
      rollback();
    }
    
    const transaction = this.transactions.get(transactionId);
    if (transaction) {
      transaction.mutations.forEach(mutation => {
        mutation.status = 'rolled_back';
      });
    }
    
    this.rollbackHandlers.delete(transactionId);
  }

  // Get transaction history
  getTransactionHistory(): OptimisticTransaction[] {
    return Array.from(this.transactions.values())
      .sort((a, b) => b.timestamp - a.timestamp);
  }

  // Clear old transactions
  clearOldTransactions(maxAge: number = 60 * 60 * 1000) {
    const cutoff = Date.now() - maxAge;
    this.transactions.forEach((transaction, id) => {
      if (transaction.timestamp < cutoff) {
        this.transactions.delete(id);
      }
    });
  }
}

// Create singleton instance
export const optimisticUpdateService = new OptimisticUpdateService();

// React hooks for optimistic updates
import { useMutation, useQuery } from '@tanstack/react-query';
import { useCallback } from 'react';

export const useOptimisticMutation = <TData, TVariables>({
  mutationKey,
  mutationFn,
  updateFn,
  rollbackFn,
  onSuccess,
  onError,
}: {
  mutationKey: string[];
  mutationFn: (variables: TVariables) => Promise<TData>;
  updateFn: (oldData: TData, variables: TVariables) => TData;
  rollbackFn?: (oldData: TData, error: Error) => TData;
  onSuccess?: (data: TData) => void;
  onError?: (error: Error) => void;
}) => {
  const mutation = useMutation({
    mutationFn: async (variables: TVariables) => {
      return optimisticUpdateService.performOptimisticUpdate({
        mutationKey,
        variables,
        updateFn,
        rollbackFn,
        mutationFn,
      });
    },
    onSuccess,
    onError,
  });

  return mutation;
};

export const useOptimisticDelete = <T>(
  queryKey: string[],
  deleteFn: (id: string | number) => Promise<void>,
  options?: {
    undoTimeout?: number;
    onUndo?: () => void;
    onDelete?: (id: string | number) => void;
  }
) => {
  const deleteItem = useCallback(
    (itemId: string | number) => {
      const { undo, commit } = optimisticUpdateService.optimisticDelete<T>(
        queryKey,
        itemId,
        () => deleteFn(itemId),
        options
      );

      options?.onDelete?.(itemId);

      return { undo, commit };
    },
    [queryKey, deleteFn, options]
  );

  return deleteItem;
};

export const useOptimisticReorder = <T extends { id: string | number; order?: number }>(
  queryKey: string[],
  reorderFn: (newOrder: Array<string | number>) => Promise<void>
) => {
  const { data: items = [] } = useQuery<T[]>({ queryKey });

  const reorderItems = useCallback(
    (newOrder: Array<string | number>) => {
      optimisticUpdateService.optimisticReorder(
        queryKey,
        items,
        newOrder,
        reorderFn
      );
    },
    [queryKey, items, reorderFn]
  );

  return reorderItems;
};