import { useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from 'react-native';

import { api, type UserProfile } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { colors } from '@/lib/theme';

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const LANGS: { value: UserProfile['language']; label: string }[] = [
  { value: 'auto', label: 'Auto' },
  { value: 'ta-IN', label: 'தமிழ்' },
  { value: 'en-IN', label: 'English' },
];
const TIME = /^\d{2}:\d{2}$/;

export default function SettingsScreen() {
  const { user, setUser, signOut } = useAuth();
  const [reminders, setReminders] = useState((user?.reminder_minutes ?? [30, 10]).join(', '));
  const [workStart, setWorkStart] = useState(user?.work_start ?? '09:00');
  const [workEnd, setWorkEnd] = useState(user?.work_end ?? '18:00');
  const [workDays, setWorkDays] = useState<number[]>(user?.work_days ?? [0, 1, 2, 3, 4]);
  const [briefingOn, setBriefingOn] = useState(user?.morning_briefing_time != null);
  const [briefing, setBriefing] = useState(user?.morning_briefing_time ?? '08:00');
  const [language, setLanguage] = useState<UserProfile['language']>(user?.language ?? 'auto');
  const [saving, setSaving] = useState(false);

  if (!user) return null;

  const toggleDay = (d: number) =>
    setWorkDays((days) => (days.includes(d) ? days.filter((x) => x !== d) : [...days, d].sort()));

  const save = async () => {
    const minutes = reminders
      .split(',')
      .map((s) => parseInt(s.trim(), 10))
      .filter((n) => n > 0);
    if (!minutes.length) return Alert.alert('Reminders', 'Enter at least one reminder time in minutes, e.g. 30, 10');
    if (![workStart, workEnd, briefing].every((t) => TIME.test(t)))
      return Alert.alert('Time format', 'Use HH:MM, for example 09:00');

    setSaving(true);
    try {
      const updated = await api.updateSettings({
        reminder_minutes: minutes,
        work_start: workStart,
        work_end: workEnd,
        work_days: workDays,
        language,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        ...(briefingOn ? { morning_briefing_time: briefing } : { disable_morning_briefing: true }),
      });
      setUser(updated);
      Alert.alert('Saved', 'Your settings were updated.');
    } catch (e) {
      Alert.alert('Could not save', e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.account}>{user.email}</Text>

      <Text style={styles.label}>Remind me before meetings (minutes)</Text>
      <TextInput style={styles.input} value={reminders} onChangeText={setReminders} keyboardType="numbers-and-punctuation" />

      <Text style={styles.label}>Working hours (used for free-time answers)</Text>
      <View style={styles.row}>
        <TextInput style={[styles.input, styles.half]} value={workStart} onChangeText={setWorkStart} placeholder="09:00" />
        <TextInput style={[styles.input, styles.half]} value={workEnd} onChangeText={setWorkEnd} placeholder="18:00" />
      </View>
      <View style={styles.row}>
        {DAYS.map((d, i) => (
          <Pressable key={d} onPress={() => toggleDay(i)} style={[styles.chip, workDays.includes(i) && styles.chipOn]}>
            <Text style={[styles.chipText, workDays.includes(i) && styles.chipTextOn]}>{d}</Text>
          </Pressable>
        ))}
      </View>

      <View style={[styles.row, styles.between]}>
        <Text style={styles.label}>Morning briefing</Text>
        <Switch value={briefingOn} onValueChange={setBriefingOn} />
      </View>
      {briefingOn && <TextInput style={styles.input} value={briefing} onChangeText={setBriefing} placeholder="08:00" />}

      <Text style={styles.label}>Reply language</Text>
      <View style={styles.row}>
        {LANGS.map((l) => (
          <Pressable key={l.value} onPress={() => setLanguage(l.value)} style={[styles.chip, language === l.value && styles.chipOn]}>
            <Text style={[styles.chipText, language === l.value && styles.chipTextOn]}>{l.label}</Text>
          </Pressable>
        ))}
      </View>

      <Pressable style={styles.save} onPress={save} disabled={saving}>
        <Text style={styles.saveText}>{saving ? 'Saving…' : 'Save'}</Text>
      </Pressable>
      <Pressable style={styles.signOut} onPress={signOut}>
        <Text style={styles.signOutText}>Sign out</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 16, gap: 10 },
  account: { color: colors.muted, marginBottom: 6 },
  label: { fontSize: 15, fontWeight: '600', color: colors.text, marginTop: 10 },
  input: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    padding: 12,
    fontSize: 16,
    color: colors.text,
  },
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, alignItems: 'center' },
  between: { justifyContent: 'space-between' },
  half: { flex: 1 },
  chip: { borderWidth: 1, borderColor: colors.border, borderRadius: 16, paddingHorizontal: 12, paddingVertical: 6 },
  chipOn: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { color: colors.text },
  chipTextOn: { color: colors.primaryText },
  save: { backgroundColor: colors.primary, borderRadius: 12, padding: 14, alignItems: 'center', marginTop: 20 },
  saveText: { color: colors.primaryText, fontWeight: '600', fontSize: 16 },
  signOut: { padding: 14, alignItems: 'center' },
  signOutText: { color: colors.danger, fontWeight: '600' },
});
