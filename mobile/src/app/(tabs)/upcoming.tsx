import { useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Linking, Pressable, RefreshControl, SectionList, StyleSheet, Text, View } from 'react-native';

import { api, type CalendarEvent } from '@/lib/api';
import { formatDay, formatTime } from '@/lib/format';
import { colors } from '@/lib/theme';

type Section = { title: string; data: CalendarEvent[] };

function groupByDay(events: CalendarEvent[]): Section[] {
  const sections: Section[] = [];
  for (const event of events) {
    const title = formatDay(event.start);
    const last = sections[sections.length - 1];
    if (last?.title === title) last.data.push(event);
    else sections.push({ title, data: [event] });
  }
  return sections;
}

export default function UpcomingScreen() {
  const [sections, setSections] = useState<Section[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { events } = await api.upcoming(7);
      setSections(groupByDay(events));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  return (
    <SectionList
      style={styles.container}
      contentContainerStyle={styles.content}
      sections={sections}
      keyExtractor={(e) => e.id + e.start}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
      ListHeaderComponent={error ? <Text style={styles.error}>{error}</Text> : undefined}
      ListEmptyComponent={
        !loading && !error ? <Text style={styles.empty}>No meetings in the next 7 days. You are free!</Text> : undefined
      }
      renderSectionHeader={({ section }) => <Text style={styles.day}>{section.title}</Text>}
      renderItem={({ item }) => (
        <View style={[styles.card, item.my_response === 'declined' && styles.declined]}>
          <Text style={styles.time}>
            {item.all_day ? 'All day' : `${formatTime(item.start)} – ${formatTime(item.end)}`}
          </Text>
          <Text style={styles.title}>{item.title}</Text>
          {item.attendees.length > 0 && (
            <Text style={styles.meta} numberOfLines={1}>
              {item.attendees.map((a) => a.email).join(', ')}
            </Text>
          )}
          {item.meet_link && (
            <Pressable onPress={() => Linking.openURL(item.meet_link!)}>
              <Text style={styles.join}>Join Google Meet</Text>
            </Pressable>
          )}
        </View>
      )}
    />
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 16, gap: 8 },
  day: { fontSize: 15, fontWeight: '700', color: colors.muted, marginTop: 12, marginBottom: 4 },
  card: { backgroundColor: colors.card, borderRadius: 12, padding: 14, borderWidth: 1, borderColor: colors.border, gap: 4 },
  declined: { opacity: 0.5 },
  time: { color: colors.primary, fontWeight: '600' },
  title: { fontSize: 17, color: colors.text, fontWeight: '600' },
  meta: { color: colors.muted },
  join: { color: colors.primary, fontWeight: '600', marginTop: 4 },
  empty: { textAlign: 'center', color: colors.muted, marginTop: 40, fontSize: 16 },
  error: { color: colors.danger, marginBottom: 8 },
});
