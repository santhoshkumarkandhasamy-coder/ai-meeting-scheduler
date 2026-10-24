import Constants from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { AndroidImportance } from 'expo-notifications';
import { Platform } from 'react-native';

import { api } from './api';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

/** Ask for permission, get this device's Expo push token and register it with the backend. */
export async function registerForReminders(): Promise<string | null> {
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('reminders', {
      name: 'Meeting reminders',
      importance: AndroidImportance.HIGH,
      sound: 'default',
    });
  }
  if (!Device.isDevice) return null; // push tokens need a physical device

  let { status } = await Notifications.getPermissionsAsync();
  if (status !== 'granted') status = (await Notifications.requestPermissionsAsync()).status;
  if (status !== 'granted') return null;

  const projectId = Constants.expoConfig?.extra?.eas?.projectId ?? Constants.easConfig?.projectId;
  const { data: token } = await Notifications.getExpoPushTokenAsync(projectId ? { projectId } : undefined);
  await api.savePushToken(token);
  return token;
}
