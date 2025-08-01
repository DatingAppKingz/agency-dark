# Socket.IO Client Example for Chat System

This document provides examples of how to connect to and use the Socket.IO real-time chat features.

## Installation

First, install the Socket.IO client library:

```bash
npm install socket.io-client
# or
yarn add socket.io-client
```

## Basic Connection

```javascript
import { io } from 'socket.io-client';

// Connect to the Socket.IO server
const socket = io('http://localhost:8000', {
  auth: {
    token: 'your-jwt-token-here' // Get this from your login response
  },
  transports: ['websocket', 'polling'], // Use WebSocket first, fallback to polling
  reconnection: true,
  reconnectionAttempts: 5,
  reconnectionDelay: 1000,
});

// Connect to the chat namespace
const chatSocket = io('http://localhost:8000/chat/v2', {
  auth: {
    token: 'your-jwt-token-here'
  }
});
```

## Event Listeners

### Connection Events

```javascript
// When connected
chatSocket.on('connected', (data) => {
  console.log('Connected to chat:', data);
  // data = { status: 'connected', user: {...}, timestamp: '...' }
});

// Connection error
chatSocket.on('connect_error', (error) => {
  console.error('Connection error:', error.message);
});

// Disconnected
chatSocket.on('disconnect', (reason) => {
  console.log('Disconnected:', reason);
});
```

### Joining a Conversation

```javascript
// Join a conversation room
chatSocket.emit('join_conversation', {
  conversation_id: 123
});

// Listen for join confirmation
chatSocket.on('joined_conversation', (data) => {
  console.log('Joined conversation:', data.conversation_id);
});

// Leave a conversation room
chatSocket.emit('leave_conversation', {
  conversation_id: 123
});
```

### Sending Messages

```javascript
// Send a text message
chatSocket.emit('send_message', {
  conversation_id: 123,
  content: 'Hello, how are you?',
  type: 'text'
});

// Send a message with media
chatSocket.emit('send_message', {
  conversation_id: 123,
  content: 'Check out this photo!',
  type: 'image',
  media_url: 'https://example.com/image.jpg'
});

// Send a tip message
chatSocket.emit('send_message', {
  conversation_id: 123,
  content: 'Thanks for the great content!',
  type: 'tip',
  amount: 50.00
});

// Send PPV (Pay-Per-View) content
chatSocket.emit('send_message', {
  conversation_id: 123,
  content: 'Exclusive content available!',
  type: 'ppv',
  media_url: 'https://example.com/locked-content.jpg',
  amount: 25.00
});
```

### Receiving Messages

```javascript
// Listen for new messages
chatSocket.on('new_message', (message) => {
  console.log('New message received:', message);
  // message = {
  //   id: 456,
  //   conversation_id: 123,
  //   sender_id: 789,
  //   sender_type: 'model',
  //   sender_name: 'Model Name',
  //   type: 'text',
  //   content: 'Hello!',
  //   media_url: null,
  //   amount: null,
  //   status: 'sent',
  //   created_at: '2024-01-31T12:34:56Z'
  // }
  
  // Add message to UI
  addMessageToChat(message);
});
```

### Typing Indicators

```javascript
// Start typing
chatSocket.emit('typing_start', {
  conversation_id: 123
});

// Stop typing
chatSocket.emit('typing_stop', {
  conversation_id: 123
});

// Listen for typing events
chatSocket.on('user_typing', (data) => {
  console.log(`${data.user_name} is ${data.is_typing ? 'typing' : 'not typing'}`);
  // data = {
  //   conversation_id: 123,
  //   user_id: '789',
  //   user_name: 'John Doe',
  //   is_typing: true
  // }
});
```

### Mark Messages as Read

```javascript
// Mark specific messages as read
chatSocket.emit('mark_read', {
  conversation_id: 123,
  message_ids: [456, 457, 458]
});

// Mark all messages in conversation as read
chatSocket.emit('mark_read', {
  conversation_id: 123
});

// Listen for read receipts
chatSocket.on('messages_read', (data) => {
  console.log(`Messages read by user ${data.reader_id}`);
  // Update UI to show read status
});
```

### Conversation Updates

```javascript
// Update conversation status (admin/model only)
chatSocket.emit('update_conversation_status', {
  conversation_id: 123,
  status: 'archived' // 'active', 'archived', 'blocked'
});

// Listen for conversation updates
chatSocket.on('conversation_updated', (data) => {
  console.log(`Conversation ${data.conversation_id} status changed to ${data.status}`);
});
```

### Error Handling

```javascript
// Listen for errors
chatSocket.on('error', (error) => {
  console.error('Socket error:', error.message);
  // Show error to user
  showErrorNotification(error.message);
});
```

## Complete Example: Chat Component

```javascript
class ChatManager {
  constructor(token) {
    this.token = token;
    this.socket = null;
    this.currentConversation = null;
    this.messages = [];
    this.typingUsers = new Map();
  }

  connect() {
    this.socket = io('http://localhost:8000/chat/v2', {
      auth: { token: this.token }
    });

    this.setupEventListeners();
  }

  setupEventListeners() {
    // Connection events
    this.socket.on('connected', (data) => {
      console.log('Connected:', data);
      this.onConnected(data.user);
    });

    // Message events
    this.socket.on('new_message', (message) => {
      this.handleNewMessage(message);
    });

    // Typing events
    this.socket.on('user_typing', (data) => {
      this.handleTypingIndicator(data);
    });

    // Error handling
    this.socket.on('error', (error) => {
      this.handleError(error);
    });
  }

  joinConversation(conversationId) {
    this.currentConversation = conversationId;
    this.socket.emit('join_conversation', {
      conversation_id: conversationId
    });
  }

  sendMessage(content, type = 'text', extras = {}) {
    if (!this.currentConversation) return;

    this.socket.emit('send_message', {
      conversation_id: this.currentConversation,
      content,
      type,
      ...extras
    });
  }

  startTyping() {
    if (!this.currentConversation) return;

    this.socket.emit('typing_start', {
      conversation_id: this.currentConversation
    });
  }

  stopTyping() {
    if (!this.currentConversation) return;

    this.socket.emit('typing_stop', {
      conversation_id: this.currentConversation
    });
  }

  markMessagesRead(messageIds = []) {
    if (!this.currentConversation) return;

    this.socket.emit('mark_read', {
      conversation_id: this.currentConversation,
      message_ids: messageIds
    });
  }

  handleNewMessage(message) {
    if (message.conversation_id === this.currentConversation) {
      this.messages.push(message);
      this.onMessageReceived(message);
    }
  }

  handleTypingIndicator(data) {
    if (data.conversation_id !== this.currentConversation) return;

    if (data.is_typing) {
      this.typingUsers.set(data.user_id, data.user_name);
    } else {
      this.typingUsers.delete(data.user_id);
    }

    this.onTypingUsersChanged(Array.from(this.typingUsers.values()));
  }

  handleError(error) {
    console.error('Chat error:', error);
    this.onError(error);
  }

  // Override these methods in your implementation
  onConnected(user) {}
  onMessageReceived(message) {}
  onTypingUsersChanged(typingUsers) {}
  onError(error) {}

  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
    }
  }
}

// Usage
const chatManager = new ChatManager(authToken);

chatManager.onConnected = (user) => {
  console.log('User connected:', user);
};

chatManager.onMessageReceived = (message) => {
  // Add message to UI
  appendMessageToChat(message);
};

chatManager.onTypingUsersChanged = (users) => {
  // Update typing indicator
  updateTypingIndicator(users);
};

chatManager.onError = (error) => {
  // Show error notification
  showError(error.message);
};

// Connect and join a conversation
chatManager.connect();
chatManager.joinConversation(123);

// Send a message
chatManager.sendMessage('Hello!', 'text');

// Handle typing
const messageInput = document.getElementById('message-input');
let typingTimer;

messageInput.addEventListener('input', () => {
  chatManager.startTyping();
  clearTimeout(typingTimer);
  typingTimer = setTimeout(() => {
    chatManager.stopTyping();
  }, 1000);
});
```

## React Hook Example

```javascript
import { useEffect, useState, useCallback } from 'react';
import { io } from 'socket.io-client';

function useChatSocket(token, conversationId) {
  const [socket, setSocket] = useState(null);
  const [connected, setConnected] = useState(false);
  const [messages, setMessages] = useState([]);
  const [typingUsers, setTypingUsers] = useState([]);

  useEffect(() => {
    if (!token) return;

    const newSocket = io('http://localhost:8000/chat/v2', {
      auth: { token }
    });

    newSocket.on('connected', () => {
      setConnected(true);
      if (conversationId) {
        newSocket.emit('join_conversation', { conversation_id: conversationId });
      }
    });

    newSocket.on('new_message', (message) => {
      setMessages(prev => [...prev, message]);
    });

    newSocket.on('user_typing', (data) => {
      setTypingUsers(prev => {
        const updated = [...prev.filter(u => u.user_id !== data.user_id)];
        if (data.is_typing) {
          updated.push(data);
        }
        return updated;
      });
    });

    setSocket(newSocket);

    return () => {
      newSocket.disconnect();
    };
  }, [token, conversationId]);

  const sendMessage = useCallback((content, type = 'text', extras = {}) => {
    if (!socket || !conversationId) return;

    socket.emit('send_message', {
      conversation_id: conversationId,
      content,
      type,
      ...extras
    });
  }, [socket, conversationId]);

  const startTyping = useCallback(() => {
    if (!socket || !conversationId) return;
    socket.emit('typing_start', { conversation_id: conversationId });
  }, [socket, conversationId]);

  const stopTyping = useCallback(() => {
    if (!socket || !conversationId) return;
    socket.emit('typing_stop', { conversation_id: conversationId });
  }, [socket, conversationId]);

  return {
    connected,
    messages,
    typingUsers,
    sendMessage,
    startTyping,
    stopTyping
  };
}

// Usage in component
function ChatComponent({ token, conversationId }) {
  const { connected, messages, typingUsers, sendMessage, startTyping, stopTyping } = useChatSocket(token, conversationId);

  return (
    <div>
      {!connected && <div>Connecting...</div>}
      
      <div className="messages">
        {messages.map(msg => (
          <div key={msg.id}>
            <strong>{msg.sender_name}:</strong> {msg.content}
          </div>
        ))}
      </div>

      {typingUsers.length > 0 && (
        <div className="typing">
          {typingUsers.map(u => u.user_name).join(', ')} {typingUsers.length === 1 ? 'is' : 'are'} typing...
        </div>
      )}

      <input
        onFocus={startTyping}
        onBlur={stopTyping}
        onKeyPress={(e) => {
          if (e.key === 'Enter') {
            sendMessage(e.target.value);
            e.target.value = '';
          }
        }}
      />
    </div>
  );
}
```

## Testing with Python Client

```python
import socketio
import asyncio

# Create a Socket.IO client
sio = socketio.AsyncClient()

@sio.on('connected', namespace='/chat/v2')
async def on_connected(data):
    print(f"Connected: {data}")
    # Join a conversation
    await sio.emit('join_conversation', {'conversation_id': 123}, namespace='/chat/v2')

@sio.on('new_message', namespace='/chat/v2')
async def on_new_message(data):
    print(f"New message: {data}")

@sio.on('error', namespace='/chat/v2')
async def on_error(data):
    print(f"Error: {data}")

async def main():
    # Connect with authentication
    await sio.connect(
        'http://localhost:8000',
        auth={'token': 'your-jwt-token'},
        namespaces=['/chat/v2']
    )
    
    # Send a message
    await sio.emit('send_message', {
        'conversation_id': 123,
        'content': 'Hello from Python!',
        'type': 'text'
    }, namespace='/chat/v2')
    
    # Keep the connection alive
    await asyncio.sleep(60)
    
    # Disconnect
    await sio.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
```

## Security Considerations

1. **Always use JWT tokens** for authentication
2. **Use HTTPS/WSS** in production
3. **Implement rate limiting** on the server
4. **Validate all input** on both client and server
5. **Handle disconnections gracefully** with reconnection logic
6. **Don't expose sensitive data** in events

## Troubleshooting

### Connection Issues

1. Check that the server is running and accessible
2. Verify the JWT token is valid and not expired
3. Ensure CORS is configured correctly on the server
4. Check firewall/proxy settings

### Message Not Received

1. Verify you've joined the conversation room
2. Check that the conversation_id is correct
3. Look for error events
4. Check server logs for errors

### Performance Issues

1. Use WebSocket transport instead of polling
2. Implement message pagination
3. Limit the number of concurrent connections
4. Use room-based broadcasting efficiently