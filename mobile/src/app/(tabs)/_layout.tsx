import { Tabs } from 'expo-router/tabs';

import { colors } from '@/lib/theme';

export default function TabsLayout() {
  return (
    <Tabs screenOptions={{ tabBarActiveTintColor: colors.primary, headerTitleAlign: 'center' }}>
      <Tabs.Screen name="index" options={{ title: 'Assistant' }} />
      <Tabs.Screen name="upcoming" options={{ title: 'Upcoming' }} />
      <Tabs.Screen name="settings" options={{ title: 'Settings' }} />
    </Tabs>
  );
}
