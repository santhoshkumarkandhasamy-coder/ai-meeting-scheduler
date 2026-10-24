import { useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useAuth } from '@/lib/auth';
import { colors } from '@/lib/theme';

export default function SignInScreen() {
  const { signIn } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onPress = async () => {
    setBusy(true);
    setError(null);
    try {
      await signIn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.hero}>
        <Text style={styles.title}>Meeting Assistant</Text>
        <Text style={styles.subtitle}>
          Your voice assistant for Google Calendar. Get reminders, schedule meetings and find free time, in Tamil or
          English.
        </Text>
        <Text style={styles.subtitle}>உங்க மீட்டிங்குகளை குரல் மூலமா நிர்வகிக்கலாம்.</Text>
      </View>
      <Pressable style={styles.button} onPress={onPress} disabled={busy}>
        {busy ? <ActivityIndicator color={colors.primaryText} /> : <Text style={styles.buttonText}>Sign in with Google</Text>}
      </Pressable>
      {error && <Text style={styles.error}>{error}</Text>}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg, padding: 24, justifyContent: 'center' },
  hero: { gap: 12, marginBottom: 40 },
  title: { fontSize: 32, fontWeight: '700', color: colors.text },
  subtitle: { fontSize: 16, color: colors.muted, lineHeight: 22 },
  button: { backgroundColor: colors.primary, borderRadius: 12, paddingVertical: 16, alignItems: 'center' },
  buttonText: { color: colors.primaryText, fontSize: 17, fontWeight: '600' },
  error: { color: colors.danger, marginTop: 16, textAlign: 'center' },
});
