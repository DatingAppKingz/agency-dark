"""
Connection pool manager for backward compatibility
"""
from .connection_pool_optimizer import ConnectionPoolOptimizer, connection_pool_optimizer

# Create a wrapper class that acts as connection_pool_manager
class ConnectionPoolManager:
    """Wrapper for connection pool optimizer to maintain compatibility."""
    
    def __init__(self):
        self.optimizer = connection_pool_optimizer
    
    def get_stats(self):
        """Get connection pool statistics."""
        if self.optimizer:
            return self.optimizer.get_pool_stats()
        return {}
    
    def optimize(self):
        """Trigger pool optimization."""
        if self.optimizer:
            return self.optimizer.optimize_pools()
        return None
    
    def get_session(self, pool_name: str = "default"):
        """Get a database session from the pool."""
        if self.optimizer:
            session_maker = self.optimizer.get_session_maker(pool_name)
            if session_maker:
                return session_maker()
        return None


# Create global instance
connection_pool_manager = ConnectionPoolManager()