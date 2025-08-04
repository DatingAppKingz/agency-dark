import { io, Socket } from 'socket.io-client';
import { EventEmitter } from 'events';

export enum ConnectionState {
  DISCONNECTED = 'disconnected',
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  RECONNECTING = 'reconnecting',
  ERROR = 'error',
}

interface RealtimeConfig {
  url: string;
  autoConnect?: boolean;
  reconnection?: boolean;
  reconnectionAttempts?: number;
  reconnectionDelay?: number;
  reconnectionDelayMax?: number;
  timeout?: number;
  transports?: string[];
  heartbeatInterval?: number;
  heartbeatTimeout?: number;
}

interface QueuedMessage {
  event: string;
  data: any;
  timestamp: number;
  attempts: number;
  id: string;
}

interface PresenceData {
  userId: string;
  status: 'online' | 'away' | 'busy' | 'offline';
  lastSeen: Date;
  metadata?: Record<string, any>;
}

class RealtimeService extends EventEmitter {
  private socket: Socket | null = null;
  private config: RealtimeConfig;
  private connectionState: ConnectionState = ConnectionState.DISCONNECTED;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private messageQueue: QueuedMessage[] = [];
  private activeRooms: Set<string> = new Set();
  private presenceMap: Map<string, PresenceData> = new Map();
  private reconnectAttempt: number = 0;
  private lastConnectedAt: Date | null = null;
  private connectionListeners: Set<(state: ConnectionState) => void> = new Set();

  constructor(config: Partial<RealtimeConfig> = {}) {
    super();
    this.config = {
      url: process.env.REACT_APP_WEBSOCKET_URL || 'http://localhost:8000',
      autoConnect: true,
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      timeout: 20000,
      transports: ['websocket', 'polling'],
      heartbeatInterval: 25000,
      heartbeatTimeout: 60000,
      ...config,
    };
  }

  // Initialize connection
  async connect(auth?: { token: string }): Promise<void> {
    if (this.socket?.connected) {
      console.log('Already connected to realtime service');
      return;
    }

    this.updateConnectionState(ConnectionState.CONNECTING);

    try {
      this.socket = io(this.config.url, {
        reconnection: this.config.reconnection,
        reconnectionAttempts: this.config.reconnectionAttempts,
        reconnectionDelay: this.config.reconnectionDelay,
        reconnectionDelayMax: this.config.reconnectionDelayMax,
        timeout: this.config.timeout,
        transports: this.config.transports,
        auth: auth || {},
      });

      this.setupEventHandlers();
      
      // Wait for connection
      await this.waitForConnection();
    } catch (error) {
      console.error('Failed to connect to realtime service:', error);
      this.updateConnectionState(ConnectionState.ERROR);
      throw error;
    }
  }

  // Disconnect from service
  disconnect(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.socket) {
      this.socket.removeAllListeners();
      this.socket.disconnect();
      this.socket = null;
    }

    this.activeRooms.clear();
    this.presenceMap.clear();
    this.updateConnectionState(ConnectionState.DISCONNECTED);
  }

  // Connection state management
  private updateConnectionState(state: ConnectionState): void {
    if (this.connectionState !== state) {
      const previousState = this.connectionState;
      this.connectionState = state;
      
      this.emit('connectionStateChange', { 
        current: state, 
        previous: previousState 
      });

      // Notify all listeners
      this.connectionListeners.forEach(listener => listener(state));

      // Handle state-specific logic
      switch (state) {
        case ConnectionState.CONNECTED:
          this.lastConnectedAt = new Date();
          this.reconnectAttempt = 0;
          this.startHeartbeat();
          this.flushMessageQueue();
          break;
        case ConnectionState.DISCONNECTED:
        case ConnectionState.ERROR:
          this.stopHeartbeat();
          break;
      }
    }
  }

  getConnectionState(): ConnectionState {
    return this.connectionState;
  }

  onConnectionStateChange(listener: (state: ConnectionState) => void): () => void {
    this.connectionListeners.add(listener);
    // Call immediately with current state
    listener(this.connectionState);
    
    // Return unsubscribe function
    return () => {
      this.connectionListeners.delete(listener);
    };
  }

  // Event handlers setup
  private setupEventHandlers(): void {
    if (!this.socket) return;

    this.socket.on('connect', () => {
      console.log('Connected to realtime service');
      this.updateConnectionState(ConnectionState.CONNECTED);
      this.emit('connected');
    });

    this.socket.on('disconnect', (reason) => {
      console.log('Disconnected from realtime service:', reason);
      this.updateConnectionState(ConnectionState.DISCONNECTED);
      this.emit('disconnected', reason);
      
      if (reason === 'io server disconnect') {
        // Server disconnected us, don't auto-reconnect
        this.socket?.connect();
      }
    });

    this.socket.on('connect_error', (error) => {
      console.error('Connection error:', error);
      this.updateConnectionState(ConnectionState.ERROR);
      this.emit('error', error);
    });

    this.socket.on('reconnect_attempt', (attempt) => {
      this.reconnectAttempt = attempt;
      this.updateConnectionState(ConnectionState.RECONNECTING);
      this.emit('reconnecting', attempt);
    });

    this.socket.on('reconnect', (attempt) => {
      console.log('Reconnected after', attempt, 'attempts');
      this.updateConnectionState(ConnectionState.CONNECTED);
      this.emit('reconnected', attempt);
      
      // Rejoin rooms
      this.rejoinRooms();
    });

    this.socket.on('reconnect_error', (error) => {
      console.error('Reconnection error:', error);
      this.emit('reconnectError', error);
    });

    this.socket.on('reconnect_failed', () => {
      console.error('Failed to reconnect after max attempts');
      this.updateConnectionState(ConnectionState.ERROR);
      this.emit('reconnectFailed');
      
      // Implement custom reconnection logic
      this.scheduleReconnection();
    });

    // Heartbeat response
    this.socket.on('pong', () => {
      this.emit('heartbeat');
    });

    // Presence updates
    this.socket.on('presence:update', (data: PresenceData) => {
      this.updatePresence(data);
    });

    this.socket.on('presence:bulk', (users: PresenceData[]) => {
      users.forEach(user => this.updatePresence(user));
    });
  }

  // Wait for connection with timeout
  private waitForConnection(timeout: number = 5000): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.socket?.connected) {
        resolve();
        return;
      }

      const timer = setTimeout(() => {
        reject(new Error('Connection timeout'));
      }, timeout);

      const handleConnect = () => {
        clearTimeout(timer);
        this.socket?.off('connect', handleConnect);
        resolve();
      };

      const handleError = (error: Error) => {
        clearTimeout(timer);
        this.socket?.off('connect_error', handleError);
        reject(error);
      };

      this.socket?.once('connect', handleConnect);
      this.socket?.once('connect_error', handleError);
    });
  }

  // Custom reconnection logic
  private scheduleReconnection(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }

    const delay = Math.min(
      this.config.reconnectionDelay! * Math.pow(2, this.reconnectAttempt),
      this.config.reconnectionDelayMax!
    );

    console.log(`Scheduling reconnection in ${delay}ms`);

    this.reconnectTimer = setTimeout(() => {
      this.reconnectAttempt++;
      if (this.reconnectAttempt <= this.config.reconnectionAttempts!) {
        this.socket?.connect();
      } else {
        console.error('Max reconnection attempts reached');
        this.emit('maxReconnectAttemptsReached');
      }
    }, delay);
  }

  // Heartbeat monitoring
  private startHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
    }

    this.heartbeatTimer = setInterval(() => {
      if (this.socket?.connected) {
        this.socket.emit('ping');
        
        // Set timeout for pong response
        const pongTimeout = setTimeout(() => {
          console.warn('Heartbeat timeout - connection may be lost');
          this.socket?.disconnect();
        }, this.config.heartbeatTimeout!);

        this.once('heartbeat', () => {
          clearTimeout(pongTimeout);
        });
      }
    }, this.config.heartbeatInterval);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  // Room management
  async joinRoom(room: string): Promise<void> {
    if (!this.socket?.connected) {
      throw new Error('Not connected to realtime service');
    }

    return new Promise((resolve, reject) => {
      this.socket!.emit('join', room, (response: any) => {
        if (response?.error) {
          reject(new Error(response.error));
        } else {
          this.activeRooms.add(room);
          this.emit('roomJoined', room);
          resolve();
        }
      });
    });
  }

  async leaveRoom(room: string): Promise<void> {
    if (!this.socket?.connected) {
      throw new Error('Not connected to realtime service');
    }

    return new Promise((resolve, reject) => {
      this.socket!.emit('leave', room, (response: any) => {
        if (response?.error) {
          reject(new Error(response.error));
        } else {
          this.activeRooms.delete(room);
          this.emit('roomLeft', room);
          resolve();
        }
      });
    });
  }

  private async rejoinRooms(): Promise<void> {
    const rooms = Array.from(this.activeRooms);
    for (const room of rooms) {
      try {
        await this.joinRoom(room);
      } catch (error) {
        console.error(`Failed to rejoin room ${room}:`, error);
      }
    }
  }

  // Message queue management
  queueMessage(event: string, data: any): void {
    const message: QueuedMessage = {
      event,
      data,
      timestamp: Date.now(),
      attempts: 0,
      id: `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    };

    this.messageQueue.push(message);
    
    // Try to send immediately if connected
    if (this.socket?.connected) {
      this.flushMessageQueue();
    }
  }

  private async flushMessageQueue(): Promise<void> {
    if (!this.socket?.connected || this.messageQueue.length === 0) {
      return;
    }

    const messages = [...this.messageQueue];
    this.messageQueue = [];

    for (const message of messages) {
      try {
        await this.emitWithAck(message.event, message.data);
        this.emit('messageDelivered', message);
      } catch (error) {
        message.attempts++;
        
        if (message.attempts < 3) {
          // Re-queue for retry
          this.messageQueue.push(message);
        } else {
          console.error(`Failed to deliver message after 3 attempts:`, message);
          this.emit('messageDeliveryFailed', message);
        }
      }
    }
  }

  // Emit with acknowledgment
  emitWithAck(event: string, data: any, timeout: number = 5000): Promise<any> {
    if (!this.socket?.connected) {
      throw new Error('Not connected to realtime service');
    }

    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        reject(new Error(`Timeout waiting for acknowledgment: ${event}`));
      }, timeout);

      this.socket!.emit(event, data, (response: any) => {
        clearTimeout(timer);
        if (response?.error) {
          reject(new Error(response.error));
        } else {
          resolve(response);
        }
      });
    });
  }

  // Presence management
  private updatePresence(data: PresenceData): void {
    this.presenceMap.set(data.userId, {
      ...data,
      lastSeen: new Date(data.lastSeen),
    });
    this.emit('presenceUpdate', data);
  }

  getPresence(userId: string): PresenceData | null {
    return this.presenceMap.get(userId) || null;
  }

  getAllPresence(): PresenceData[] {
    return Array.from(this.presenceMap.values());
  }

  async updateMyPresence(status: 'online' | 'away' | 'busy', metadata?: Record<string, any>): Promise<void> {
    if (!this.socket?.connected) {
      throw new Error('Not connected to realtime service');
    }

    return this.emitWithAck('presence:update', { status, metadata });
  }

  // Utility methods
  isConnected(): boolean {
    return this.socket?.connected || false;
  }

  getConnectionInfo() {
    return {
      state: this.connectionState,
      connected: this.isConnected(),
      reconnectAttempt: this.reconnectAttempt,
      lastConnectedAt: this.lastConnectedAt,
      activeRooms: Array.from(this.activeRooms),
      queuedMessages: this.messageQueue.length,
      presenceCount: this.presenceMap.size,
    };
  }

  // Subscribe to events
  on(event: string, handler: (...args: any[]) => void): this {
    if (this.socket) {
      this.socket.on(event, handler);
    }
    super.on(event, handler);
    return this;
  }

  off(event: string, handler?: (...args: any[]) => void): this {
    if (this.socket) {
      this.socket.off(event, handler);
    }
    super.off(event, handler);
    return this;
  }

  once(event: string, handler: (...args: any[]) => void): this {
    if (this.socket) {
      this.socket.once(event, handler);
    }
    super.once(event, handler);
    return this;
  }
}

// Create singleton instance
export const realtimeService = new RealtimeService();

// React hook for realtime connection
import { useEffect, useState } from 'react';

export const useRealtimeConnection = () => {
  const [connectionState, setConnectionState] = useState(realtimeService.getConnectionState());
  const [connectionInfo, setConnectionInfo] = useState(realtimeService.getConnectionInfo());

  useEffect(() => {
    // Subscribe to connection state changes
    const unsubscribe = realtimeService.onConnectionStateChange((state) => {
      setConnectionState(state);
      setConnectionInfo(realtimeService.getConnectionInfo());
    });

    // Update connection info periodically
    const interval = setInterval(() => {
      setConnectionInfo(realtimeService.getConnectionInfo());
    }, 1000);

    return () => {
      unsubscribe();
      clearInterval(interval);
    };
  }, []);

  return {
    connectionState,
    connectionInfo,
    isConnected: connectionState === ConnectionState.CONNECTED,
    connect: (auth?: { token: string }) => realtimeService.connect(auth),
    disconnect: () => realtimeService.disconnect(),
  };
};

// React hook for realtime events
export const useRealtimeEvent = <T = any>(
  event: string,
  handler: (data: T) => void,
  deps: React.DependencyList = []
) => {
  useEffect(() => {
    const eventHandler = (data: T) => handler(data);
    realtimeService.on(event, eventHandler);

    return () => {
      realtimeService.off(event, eventHandler);
    };
  }, deps);
};

// React hook for presence
export const useRealtimePresence = (userIds?: string[]) => {
  const [presence, setPresence] = useState<Map<string, PresenceData>>(new Map());

  useEffect(() => {
    const updatePresence = () => {
      if (userIds) {
        const filtered = new Map<string, PresenceData>();
        userIds.forEach(userId => {
          const data = realtimeService.getPresence(userId);
          if (data) {
            filtered.set(userId, data);
          }
        });
        setPresence(filtered);
      } else {
        const all = realtimeService.getAllPresence();
        const map = new Map<string, PresenceData>();
        all.forEach(data => map.set(data.userId, data));
        setPresence(map);
      }
    };

    updatePresence();

    const handlePresenceUpdate = () => {
      updatePresence();
    };

    realtimeService.on('presenceUpdate', handlePresenceUpdate);

    return () => {
      realtimeService.off('presenceUpdate', handlePresenceUpdate);
    };
  }, [userIds?.join(',')]);

  return presence;
};