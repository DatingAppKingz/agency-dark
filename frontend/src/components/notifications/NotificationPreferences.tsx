import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useToast } from '@/components/ui/use-toast';
import { notificationApi } from '@/api/notifications';
import { Bell, Mail, MessageSquare, Smartphone, Globe, Clock } from 'lucide-react';

interface NotificationPreferences {
  email_enabled: boolean;
  sms_enabled: boolean;
  push_enabled: boolean;
  in_app_enabled: boolean;
  categories: {
    marketing: boolean;
    transactions: boolean;
    messages: boolean;
    system: boolean;
    security: boolean;
  };
  digest_enabled: boolean;
  digest_frequency: 'daily' | 'weekly' | 'monthly';
  quiet_hours_enabled: boolean;
  quiet_hours_start?: string;
  quiet_hours_end?: string;
  timezone: string;
  preferred_email?: string;
  preferred_phone?: string;
}

export function NotificationPreferences() {
  const { toast } = useToast();
  const [preferences, setPreferences] = useState<NotificationPreferences | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  // Load preferences
  const loadPreferences = async () => {
    try {
      const response = await notificationApi.getPreferences();
      setPreferences(response.data);
    } catch (error) {
      console.error('Failed to load preferences:', error);
      toast({
        title: 'Failed to load preferences',
        description: 'Please try again later.',
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  };

  // Save preferences
  const savePreferences = async () => {
    if (!preferences) return;

    setIsSaving(true);
    try {
      await notificationApi.updatePreferences(preferences);
      toast({
        title: 'Preferences saved',
        description: 'Your notification preferences have been updated.',
      });
    } catch (error) {
      console.error('Failed to save preferences:', error);
      toast({
        title: 'Failed to save preferences',
        description: 'Please try again later.',
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  // Update preference
  const updatePreference = (key: string, value: any) => {
    if (!preferences) return;
    
    if (key.includes('.')) {
      // Handle nested properties
      const [parent, child] = key.split('.');
      setPreferences({
        ...preferences,
        [parent]: {
          ...(preferences as any)[parent],
          [child]: value,
        },
      });
    } else {
      setPreferences({
        ...preferences,
        [key]: value,
      });
    }
  };

  useEffect(() => {
    loadPreferences();
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-muted-foreground">Loading preferences...</div>
      </div>
    );
  }

  if (!preferences) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-muted-foreground">Failed to load preferences</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Tabs defaultValue="channels" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="channels">Channels</TabsTrigger>
          <TabsTrigger value="categories">Categories</TabsTrigger>
          <TabsTrigger value="schedule">Schedule</TabsTrigger>
          <TabsTrigger value="contact">Contact</TabsTrigger>
        </TabsList>

        <TabsContent value="channels" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Notification Channels</CardTitle>
              <CardDescription>
                Choose how you want to receive notifications
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <Mail className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <Label htmlFor="email">Email Notifications</Label>
                    <p className="text-sm text-muted-foreground">
                      Receive notifications via email
                    </p>
                  </div>
                </div>
                <Switch
                  id="email"
                  checked={preferences.email_enabled}
                  onCheckedChange={(checked) => updatePreference('email_enabled', checked)}
                />
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <MessageSquare className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <Label htmlFor="sms">SMS Notifications</Label>
                    <p className="text-sm text-muted-foreground">
                      Receive notifications via text message
                    </p>
                  </div>
                </div>
                <Switch
                  id="sms"
                  checked={preferences.sms_enabled}
                  onCheckedChange={(checked) => updatePreference('sms_enabled', checked)}
                />
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <Smartphone className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <Label htmlFor="push">Push Notifications</Label>
                    <p className="text-sm text-muted-foreground">
                      Receive push notifications on your devices
                    </p>
                  </div>
                </div>
                <Switch
                  id="push"
                  checked={preferences.push_enabled}
                  onCheckedChange={(checked) => updatePreference('push_enabled', checked)}
                />
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <Bell className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <Label htmlFor="in_app">In-App Notifications</Label>
                    <p className="text-sm text-muted-foreground">
                      See notifications within the app
                    </p>
                  </div>
                </div>
                <Switch
                  id="in_app"
                  checked={preferences.in_app_enabled}
                  onCheckedChange={(checked) => updatePreference('in_app_enabled', checked)}
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="categories" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Notification Categories</CardTitle>
              <CardDescription>
                Choose which types of notifications you want to receive
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {Object.entries(preferences.categories).map(([category, enabled]) => (
                <div key={category} className="flex items-center justify-between">
                  <div>
                    <Label htmlFor={category}>
                      {category.charAt(0).toUpperCase() + category.slice(1)}
                    </Label>
                    <p className="text-sm text-muted-foreground">
                      {getCategoryDescription(category)}
                    </p>
                  </div>
                  <Switch
                    id={category}
                    checked={enabled}
                    onCheckedChange={(checked) =>
                      updatePreference(`categories.${category}`, checked)
                    }
                  />
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="schedule" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Delivery Schedule</CardTitle>
              <CardDescription>
                Control when you receive notifications
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label htmlFor="digest">Email Digest</Label>
                    <p className="text-sm text-muted-foreground">
                      Receive a summary instead of individual emails
                    </p>
                  </div>
                  <Switch
                    id="digest"
                    checked={preferences.digest_enabled}
                    onCheckedChange={(checked) => updatePreference('digest_enabled', checked)}
                  />
                </div>

                {preferences.digest_enabled && (
                  <div className="ml-6">
                    <Label htmlFor="frequency">Digest Frequency</Label>
                    <Select
                      value={preferences.digest_frequency}
                      onValueChange={(value) => updatePreference('digest_frequency', value)}
                    >
                      <SelectTrigger id="frequency" className="mt-2">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="daily">Daily</SelectItem>
                        <SelectItem value="weekly">Weekly</SelectItem>
                        <SelectItem value="monthly">Monthly</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                )}
              </div>

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label htmlFor="quiet_hours">Quiet Hours</Label>
                    <p className="text-sm text-muted-foreground">
                      Pause notifications during specific hours
                    </p>
                  </div>
                  <Switch
                    id="quiet_hours"
                    checked={preferences.quiet_hours_enabled}
                    onCheckedChange={(checked) =>
                      updatePreference('quiet_hours_enabled', checked)
                    }
                  />
                </div>

                {preferences.quiet_hours_enabled && (
                  <div className="ml-6 grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="start_time">Start Time</Label>
                      <Input
                        id="start_time"
                        type="time"
                        value={preferences.quiet_hours_start || '22:00'}
                        onChange={(e) =>
                          updatePreference('quiet_hours_start', e.target.value)
                        }
                        className="mt-2"
                      />
                    </div>
                    <div>
                      <Label htmlFor="end_time">End Time</Label>
                      <Input
                        id="end_time"
                        type="time"
                        value={preferences.quiet_hours_end || '08:00'}
                        onChange={(e) => updatePreference('quiet_hours_end', e.target.value)}
                        className="mt-2"
                      />
                    </div>
                  </div>
                )}
              </div>

              <div>
                <Label htmlFor="timezone">Timezone</Label>
                <Select
                  value={preferences.timezone}
                  onValueChange={(value) => updatePreference('timezone', value)}
                >
                  <SelectTrigger id="timezone" className="mt-2">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="UTC">UTC</SelectItem>
                    <SelectItem value="America/New_York">Eastern Time</SelectItem>
                    <SelectItem value="America/Chicago">Central Time</SelectItem>
                    <SelectItem value="America/Denver">Mountain Time</SelectItem>
                    <SelectItem value="America/Los_Angeles">Pacific Time</SelectItem>
                    <SelectItem value="Europe/London">London</SelectItem>
                    <SelectItem value="Europe/Paris">Paris</SelectItem>
                    <SelectItem value="Asia/Tokyo">Tokyo</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="contact" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Contact Information</CardTitle>
              <CardDescription>
                Update your preferred contact methods
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="preferred_email">Preferred Email</Label>
                <Input
                  id="preferred_email"
                  type="email"
                  value={preferences.preferred_email || ''}
                  onChange={(e) => updatePreference('preferred_email', e.target.value)}
                  placeholder="Leave empty to use account email"
                  className="mt-2"
                />
              </div>

              <div>
                <Label htmlFor="preferred_phone">Preferred Phone Number</Label>
                <Input
                  id="preferred_phone"
                  type="tel"
                  value={preferences.preferred_phone || ''}
                  onChange={(e) => updatePreference('preferred_phone', e.target.value)}
                  placeholder="+1234567890"
                  className="mt-2"
                />
                <p className="text-sm text-muted-foreground mt-1">
                  Required for SMS notifications
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <div className="flex justify-end">
        <Button onClick={savePreferences} disabled={isSaving}>
          {isSaving ? 'Saving...' : 'Save Preferences'}
        </Button>
      </div>
    </div>
  );
}

function getCategoryDescription(category: string): string {
  const descriptions: { [key: string]: string } = {
    marketing: 'Promotional emails and announcements',
    transactions: 'Payment confirmations and financial updates',
    messages: 'New messages and chat notifications',
    system: 'System updates and maintenance notices',
    security: 'Security alerts and login notifications',
  };
  return descriptions[category] || '';
}