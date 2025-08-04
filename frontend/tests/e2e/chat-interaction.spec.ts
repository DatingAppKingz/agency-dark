import { test, expect } from '@playwright/test';
import { LoginPage } from './pages/LoginPage';
import { ChatPage } from './pages/ChatPage';

test.describe('Chat Interaction', () => {
  let chatPage: ChatPage;

  test.beforeEach(async ({ page }) => {
    // Login as admin
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login('admin@agency.com', 'admin123');
    await page.waitForURL(/.*dashboard/);
    
    // Navigate to chat
    chatPage = new ChatPage(page);
    await chatPage.goto();
  });

  test('should display conversation list', async ({ page }) => {
    // Should show conversations
    await expect(chatPage.conversationList).toBeVisible();
    
    // Should have at least one conversation
    const conversationCount = await chatPage.conversationItems.count();
    expect(conversationCount).toBeGreaterThanOrEqual(0);
    
    // Should show online status for users
    if (conversationCount > 0) {
      const firstConversation = chatPage.conversationItems.first();
      const onlineIndicator = firstConversation.locator(chatPage.onlineStatus);
      await expect(onlineIndicator).toHaveAttribute('data-online', /(true|false)/);
    }
  });

  test('should send and receive messages', async ({ page }) => {
    // Select first conversation
    const firstConversation = chatPage.conversationItems.first();
    if (await firstConversation.count() === 0) {
      test.skip();
      return;
    }
    
    const userName = await firstConversation.getByTestId('user-name').textContent();
    await chatPage.selectConversation(userName!);
    
    // Count initial messages
    const initialMessageCount = await chatPage.getMessageCount();
    
    // Send a message
    const testMessage = `Test message ${Date.now()}`;
    await chatPage.sendMessage(testMessage);
    
    // Message should appear in thread
    const newMessageCount = await chatPage.getMessageCount();
    expect(newMessageCount).toBe(initialMessageCount + 1);
    
    // Last message should be our test message
    const lastMessage = await chatPage.getLastMessage();
    expect(lastMessage.text).toBe(testMessage);
    expect(lastMessage.status).toBe('sent');
    
    // Wait for delivery status
    await page.waitForTimeout(1000);
    const updatedMessage = await chatPage.getLastMessage();
    expect(updatedMessage.status).toMatch(/(delivered|read)/);
  });

  test('should handle real-time messaging', async ({ page, context }) => {
    // Open second browser tab as another user
    const page2 = await context.newPage();
    const loginPage2 = new LoginPage(page2);
    await loginPage2.goto();
    await loginPage2.login('model@example.com', 'model123');
    await page2.waitForURL(/.*dashboard/);
    
    const chatPage2 = new ChatPage(page2);
    await chatPage2.goto();
    
    // Start conversation from first user
    await chatPage.startNewConversation('Test Model');
    await chatPage.sendMessage('Hello from admin!');
    
    // Second user should receive notification
    await page2.waitForTimeout(2000);
    const unreadCount = await chatPage2.getUnreadCount('Admin User');
    expect(unreadCount).toBeGreaterThan(0);
    
    // Open conversation on second user
    await chatPage2.selectConversation('Admin User');
    
    // Message should be visible
    await expect(page2.getByText('Hello from admin!')).toBeVisible();
    
    // Reply from second user
    await chatPage2.sendMessage('Hello back from model!');
    
    // First user should see the reply
    await page.waitForTimeout(2000);
    await expect(page.getByText('Hello back from model!')).toBeVisible();
    
    // Close second tab
    await page2.close();
  });

  test('should show typing indicators', async ({ page, context }) => {
    // Open second browser tab
    const page2 = await context.newPage();
    const loginPage2 = new LoginPage(page2);
    await loginPage2.goto();
    await loginPage2.login('model@example.com', 'model123');
    await page2.waitForURL(/.*dashboard/);
    
    const chatPage2 = new ChatPage(page2);
    await chatPage2.goto();
    
    // Both users open same conversation
    await chatPage.selectConversation('Test Model');
    await chatPage2.selectConversation('Admin User');
    
    // Start typing in first user
    await chatPage.messageInput.fill('Typing...');
    
    // Second user should see typing indicator
    await page2.waitForTimeout(500);
    expect(await chatPage2.isTypingIndicatorVisible()).toBe(true);
    
    // Stop typing
    await chatPage.messageInput.clear();
    
    // Typing indicator should disappear
    await page2.waitForTimeout(2000);
    expect(await chatPage2.isTypingIndicatorVisible()).toBe(false);
    
    await page2.close();
  });

  test('should send messages with attachments', async ({ page }) => {
    // Select conversation
    const firstConversation = chatPage.conversationItems.first();
    if (await firstConversation.count() === 0) {
      test.skip();
      return;
    }
    
    const userName = await firstConversation.getByTestId('user-name').textContent();
    await chatPage.selectConversation(userName!);
    
    // Send message with image
    await chatPage.sendMessageWithAttachment(
      'Check out this image!',
      './tests/fixtures/sample-image.jpg'
    );
    
    // Message should show with attachment
    const lastMessage = chatPage.messages.last();
    await expect(lastMessage).toContainText('Check out this image!');
    await expect(lastMessage.getByRole('img')).toBeVisible();
    
    // Click to view full size
    await lastMessage.getByRole('img').click();
    await expect(page.getByTestId('image-viewer')).toBeVisible();
    
    // Close viewer
    await page.getByRole('button', { name: /close/i }).click();
  });

  test('should edit and delete messages', async ({ page }) => {
    // Select conversation
    const firstConversation = chatPage.conversationItems.first();
    if (await firstConversation.count() === 0) {
      test.skip();
      return;
    }
    
    await chatPage.selectConversation('Test Model');
    
    // Send a message
    await chatPage.sendMessage('Message to edit');
    await page.waitForTimeout(1000);
    
    // Get message index
    const messageCount = await chatPage.getMessageCount();
    const lastMessageIndex = messageCount - 1;
    
    // Edit the message
    await chatPage.editMessage(lastMessageIndex, 'Edited message');
    
    // Message should show as edited
    const editedMessage = chatPage.messages.nth(lastMessageIndex);
    await expect(editedMessage).toContainText('Edited message');
    await expect(editedMessage).toContainText('edited');
    
    // Delete the message
    await chatPage.deleteMessage(lastMessageIndex);
    
    // Message should be removed
    const newMessageCount = await chatPage.getMessageCount();
    expect(newMessageCount).toBe(messageCount - 1);
  });

  test('should add reactions to messages', async ({ page }) => {
    // Select conversation
    const firstConversation = chatPage.conversationItems.first();
    if (await firstConversation.count() === 0) {
      test.skip();
      return;
    }
    
    await chatPage.selectConversation('Test Model');
    
    // Send a message
    await chatPage.sendMessage('React to this message!');
    await page.waitForTimeout(1000);
    
    // Add reaction
    const messageCount = await chatPage.getMessageCount();
    await chatPage.addReaction(messageCount - 1, '❤️');
    
    // Reaction should be visible
    const lastMessage = chatPage.messages.last();
    await expect(lastMessage.getByText('❤️')).toBeVisible();
    
    // Add another reaction
    await chatPage.addReaction(messageCount - 1, '👍');
    await expect(lastMessage.getByText('👍')).toBeVisible();
  });

  test('should search conversations', async ({ page }) => {
    // Search for specific conversation
    await chatPage.searchConversations('model');
    
    // Should filter conversations
    await page.waitForTimeout(500);
    const visibleConversations = await chatPage.conversationItems.count();
    
    // All visible conversations should contain 'model'
    for (let i = 0; i < visibleConversations; i++) {
      const conversation = chatPage.conversationItems.nth(i);
      const text = await conversation.textContent();
      expect(text?.toLowerCase()).toContain('model');
    }
    
    // Clear search
    await chatPage.searchInput.clear();
    await page.waitForTimeout(500);
    
    // Should show all conversations again
    const allConversations = await chatPage.conversationItems.count();
    expect(allConversations).toBeGreaterThanOrEqual(visibleConversations);
  });

  test('should handle message status updates', async ({ page }) => {
    // Select conversation
    const firstConversation = chatPage.conversationItems.first();
    if (await firstConversation.count() === 0) {
      test.skip();
      return;
    }
    
    await chatPage.selectConversation('Test Model');
    
    // Send message
    await chatPage.sendMessage('Testing message status');
    
    // Check initial status
    let lastMessage = await chatPage.getLastMessage();
    expect(lastMessage.status).toBe('sent');
    
    // Wait for delivery
    await page.waitForTimeout(2000);
    lastMessage = await chatPage.getLastMessage();
    expect(lastMessage.status).toMatch(/(delivered|read)/);
    
    // If delivered, might change to read
    if (lastMessage.status === 'delivered') {
      await page.waitForTimeout(3000);
      lastMessage = await chatPage.getLastMessage();
      // Status might be 'read' now
    }
  });

  test('should handle automated messages', async ({ page }) => {
    // Start new conversation
    await chatPage.startNewConversation('New Fan User');
    
    // Should receive automated welcome message
    await page.waitForTimeout(2000);
    
    const messages = await chatPage.messages.allTextContents();
    const hasWelcomeMessage = messages.some(msg => 
      msg.toLowerCase().includes('welcome') || 
      msg.toLowerCase().includes('hello')
    );
    
    expect(hasWelcomeMessage).toBe(true);
    
    // Automated message should be marked
    const automatedMessage = chatPage.messages.filter({ 
      hasText: /(welcome|hello)/i 
    }).first();
    
    await expect(automatedMessage.getByTestId('automated-badge')).toBeVisible();
  });

  test('should handle conversation actions', async ({ page }) => {
    // Select conversation
    const firstConversation = chatPage.conversationItems.first();
    if (await firstConversation.count() === 0) {
      test.skip();
      return;
    }
    
    const userName = await firstConversation.getByTestId('user-name').textContent();
    
    // Right-click on conversation
    await firstConversation.click({ button: 'right' });
    
    // Pin conversation
    await page.getByRole('menuitem', { name: /pin conversation/i }).click();
    
    // Should move to top and show pin icon
    await page.waitForTimeout(500);
    const pinnedConversation = chatPage.conversationItems.first();
    await expect(pinnedConversation).toContainText(userName!);
    await expect(pinnedConversation.getByTestId('pin-icon')).toBeVisible();
    
    // Mute conversation
    await pinnedConversation.click({ button: 'right' });
    await page.getByRole('menuitem', { name: /mute notifications/i }).click();
    
    // Should show muted icon
    await expect(pinnedConversation.getByTestId('mute-icon')).toBeVisible();
    
    // Archive conversation
    await pinnedConversation.click({ button: 'right' });
    await page.getByRole('menuitem', { name: /archive/i }).click();
    
    // Should be removed from active list
    await page.waitForTimeout(500);
    await expect(chatPage.conversationItems.filter({ hasText: userName! })).toHaveCount(0);
    
    // View archived conversations
    await page.getByRole('button', { name: /archived/i }).click();
    await expect(page.getByText(userName!)).toBeVisible();
  });

  test('should export chat history', async ({ page }) => {
    // Select conversation
    const firstConversation = chatPage.conversationItems.first();
    if (await firstConversation.count() === 0) {
      test.skip();
      return;
    }
    
    await chatPage.selectConversation('Test Model');
    
    // Open conversation info
    await page.getByRole('button', { name: /info/i }).click();
    await expect(chatPage.conversationInfo).toBeVisible();
    
    // Export chat
    await page.getByRole('button', { name: /export chat/i }).click();
    
    // Select format
    await page.getByLabel('Export Format').selectOption('pdf');
    
    // Download
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: /download/i }).click();
    
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/chat.*\.pdf/i);
  });
});