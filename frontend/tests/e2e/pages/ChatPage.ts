import { Page, Locator } from '@playwright/test';

export class ChatPage {
  readonly page: Page;
  readonly conversationList: Locator;
  readonly messageInput: Locator;
  readonly sendButton: Locator;
  readonly messageThread: Locator;
  readonly searchInput: Locator;
  readonly attachmentButton: Locator;
  readonly emojiButton: Locator;
  readonly conversationInfo: Locator;
  
  // Conversation elements
  readonly newConversationButton: Locator;
  readonly conversationItems: Locator;
  readonly unreadBadge: Locator;
  readonly onlineStatus: Locator;
  
  // Message elements
  readonly messages: Locator;
  readonly typingIndicator: Locator;
  readonly messageStatus: Locator;
  readonly messageActions: Locator;

  constructor(page: Page) {
    this.page = page;
    
    // Main elements
    this.conversationList = page.getByTestId('conversation-list');
    this.messageInput = page.getByPlaceholder(/type a message/i);
    this.sendButton = page.getByRole('button', { name: /send/i });
    this.messageThread = page.getByTestId('message-thread');
    this.searchInput = page.getByPlaceholder(/search conversations/i);
    this.attachmentButton = page.getByRole('button', { name: /attach/i });
    this.emojiButton = page.getByRole('button', { name: /emoji/i });
    this.conversationInfo = page.getByTestId('conversation-info');
    
    // Conversation elements
    this.newConversationButton = page.getByRole('button', { name: /new conversation/i });
    this.conversationItems = page.getByTestId('conversation-item');
    this.unreadBadge = page.getByTestId('unread-count');
    this.onlineStatus = page.getByTestId('online-status');
    
    // Message elements
    this.messages = page.getByTestId('message');
    this.typingIndicator = page.getByTestId('typing-indicator');
    this.messageStatus = page.getByTestId('message-status');
    this.messageActions = page.getByTestId('message-actions');
  }

  async goto() {
    await this.page.goto('/chat');
  }

  async selectConversation(userName: string) {
    const conversation = this.conversationItems.filter({ hasText: userName });
    await conversation.click();
    await this.messageThread.waitFor({ state: 'visible' });
  }

  async sendMessage(message: string) {
    await this.messageInput.fill(message);
    await this.sendButton.click();
    
    // Wait for message to appear in thread
    await this.page.waitForTimeout(500);
  }

  async sendMessageWithAttachment(message: string, filePath: string) {
    await this.attachmentButton.click();
    
    const fileInput = this.page.locator('input[type="file"]');
    await fileInput.setInputFiles(filePath);
    
    // Wait for upload
    await this.page.waitForTimeout(1000);
    
    if (message) {
      await this.messageInput.fill(message);
    }
    
    await this.sendButton.click();
  }

  async searchConversations(query: string) {
    await this.searchInput.fill(query);
    await this.page.waitForTimeout(500); // Debounce
  }

  async startNewConversation(userName: string) {
    await this.newConversationButton.click();
    
    // Search for user
    const userSearch = this.page.getByPlaceholder(/search users/i);
    await userSearch.fill(userName);
    await this.page.waitForTimeout(500);
    
    // Select user
    const userItem = this.page.getByTestId('user-item').filter({ hasText: userName });
    await userItem.click();
    
    // Start conversation
    await this.page.getByRole('button', { name: /start conversation/i }).click();
  }

  async getMessageCount() {
    return await this.messages.count();
  }

  async getLastMessage() {
    const lastMessage = this.messages.last();
    return {
      text: await lastMessage.getByTestId('message-text').textContent(),
      time: await lastMessage.getByTestId('message-time').textContent(),
      status: await lastMessage.getByTestId('message-status').getAttribute('data-status'),
    };
  }

  async isTypingIndicatorVisible() {
    return await this.typingIndicator.isVisible();
  }

  async getUnreadCount(userName: string) {
    const conversation = this.conversationItems.filter({ hasText: userName });
    const badge = conversation.locator(this.unreadBadge);
    
    if (await badge.isVisible()) {
      return parseInt(await badge.textContent() || '0');
    }
    return 0;
  }

  async markAsRead(userName: string) {
    const conversation = this.conversationItems.filter({ hasText: userName });
    await conversation.click({ button: 'right' });
    await this.page.getByRole('menuitem', { name: /mark as read/i }).click();
  }

  async deleteMessage(messageIndex: number) {
    const message = this.messages.nth(messageIndex);
    await message.hover();
    await message.getByRole('button', { name: /more/i }).click();
    await this.page.getByRole('menuitem', { name: /delete/i }).click();
    await this.page.getByRole('button', { name: /confirm/i }).click();
  }

  async editMessage(messageIndex: number, newText: string) {
    const message = this.messages.nth(messageIndex);
    await message.hover();
    await message.getByRole('button', { name: /more/i }).click();
    await this.page.getByRole('menuitem', { name: /edit/i }).click();
    
    const editInput = message.getByRole('textbox');
    await editInput.clear();
    await editInput.fill(newText);
    await editInput.press('Enter');
  }

  async addReaction(messageIndex: number, emoji: string) {
    const message = this.messages.nth(messageIndex);
    await message.hover();
    await message.getByRole('button', { name: /react/i }).click();
    await this.page.getByText(emoji).click();
  }
}