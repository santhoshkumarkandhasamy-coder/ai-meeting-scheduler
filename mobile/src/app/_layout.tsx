import * as Notifications from 'expo-notifications';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { ActivityIndicator, View } from 'react-native';

import { AuthProvider, useAuth } from '@/lib/auth';
import { registerForReminders } from '@/lib/notifications';
import { colors } from '@/lib/theme';
import { speak } from '@/lib/voice';

function RootNavigator() {
  const { user, loading } = useAuth();

  useEffect(() => {
    if (!user) return;
    registerForReminders().catch((e) => console.warn('Push registration failed', e));
  }, [user]);

  // Tapping a reminder or briefing notification reads it aloud.
  const lastResponse = Notifications.useLastNotificationResponse();
  useEffect(() => {
    const text = lastResponse?.notification.request.content.data?.speak;
    if (typeof text === 'string') speak(text);
  }, [lastResponse]);

  if (loading) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg }}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }

  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Protected guard={!!user}>
        <Stack.Screen name="(tabs)" />
      </Stack.Protected>
      <Stack.Protected guard={!user}>
        <Stack.Screen name="sign-in" />
      </Stack.Protected>
    </Stack>
  );
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <StatusBar style="dark" />
      <RootNavigator />
    </AuthProvider>
  );
}
