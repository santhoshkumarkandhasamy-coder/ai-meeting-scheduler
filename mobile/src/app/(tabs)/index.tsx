import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { colors } from '@/lib/theme';
import { speak, useVoiceInput, type VoiceLang } from '@/lib/voice';

type Message = { id: string; role: 'user' | 'assistant'; text: string; error?: boolean };

const EXAMPLES = [
  'நாளைக்கு என்ன மீட்டிங் இருக்கு?',
  'Schedule a meeting with ravi@company.com tomorrow at 3 PM',
  'அடுத்த வாரம் எந்த நாள் ஃப்ரீ?',
];

export default function AssistantScreen() {
  const { user } = useAuth();
  const [lang, setLang] = useState<VoiceLang>(user?.language === 'en-IN' ? 'en-IN' : 'ta-IN');
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [thinking, setThinking] = useState(false);
  const listRef = useRef<FlatList<Message>>(null);

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || thinking) return;
      setDraft('');
      setMessages((m) => [...m, { id: `u${Date.now()}`, role: 'user', text: trimmed }]);
      setThinking(true);
      try {
        const res = await api.chat(trimmed, conversationId);
        setConversationId(res.conversation_id);
        setMessages((m) => [...m, { id: `a${Date.now()}`, role: 'assistant', text: res.reply }]);
        speak(res.reply);
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        setMessages((m) => [...m, { id: `e${Date.now()}`, role: 'assistant', text: msg, error: true }]);
      } finally {
        setThinking(false);
      }
    },
    [conversationId, thinking],
  );

  const voice = useVoiceInput(send);

  useEffect(() => {
    if (messages.length) listRef.current?.scrollToEnd({ animated: true });
  }, [messages.length, thinking]);

  const newChat = () => {
    setMessages([]);
    setConversationId(null);
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={90}>
      <View style={styles.toolbar}>
        <View style={styles.langToggle}>
          {(['ta-IN', 'en-IN'] as const).map((l) => (
            <Pressable key={l} onPress={() => setLang(l)} style={[styles.langBtn, lang === l && styles.langBtnActive]}>
              <Text style={[styles.langText, lang === l && styles.langTextActive]}>{l === 'ta-IN' ? 'தமிழ்' : 'English'}</Text>
            </Pressable>
          ))}
        </View>
        <Pressable onPress={newChat}>
          <Text style={styles.link}>New chat</Text>
        </Pressable>
      </View>

      <FlatList
        ref={listRef}
        data={messages}
        keyExtractor={(m) => m.id}
        contentContainerStyle={styles.list}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyTitle}>Hi{user?.name ? ` ${user.name.split(' ')[0]}` : ''}! Tap the mic and ask:</Text>
            {EXAMPLES.map((ex) => (
              <Pressable key={ex} onPress={() => send(ex)} style={styles.example}>
                <Text style={styles.exampleText}>{ex}</Text>
              </Pressable>
            ))}
          </View>
        }
        renderItem={({ item }) => (
          <View style={[styles.bubble, item.role === 'user' ? styles.userBubble : styles.botBubble]}>
            <Text style={[styles.bubbleText, item.role === 'user' && styles.userText, item.error && styles.errorText]}>
              {item.text}
            </Text>
          </View>
        )}
        ListFooterComponent={thinking ? <ActivityIndicator style={{ marginTop: 8 }} color={colors.primary} /> : undefined}
      />

      {(voice.listening || voice.partial) && (
        <Text style={styles.partial}>{voice.listening ? `🎙 ${voice.partial || 'Listening…'}` : ''}</Text>
      )}
      {voice.error && <Text style={styles.voiceError}>{voice.error}</Text>}

      <View style={styles.inputRow}>
        <TextInput
          style={styles.input}
          value={draft}
          onChangeText={setDraft}
          placeholder="Type or tap the mic…"
          placeholderTextColor={colors.muted}
          onSubmitEditing={() => send(draft)}
          returnKeyType="send"
        />
        <Pressable
          accessibilityLabel={voice.listening ? 'Stop listening' : 'Start speaking'}
          onPress={() => (voice.listening ? voice.stop() : voice.start(lang))}
          style={[styles.mic, voice.listening && styles.micActive]}>
          <Text style={styles.micIcon}>{voice.listening ? '■' : '🎤'}</Text>
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  toolbar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 12 },
  langToggle: { flexDirection: 'row', backgroundColor: colors.border, borderRadius: 20, padding: 3 },
  langBtn: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 17 },
  langBtnActive: { backgroundColor: colors.card },
  langText: { color: colors.muted, fontWeight: '600' },
  langTextActive: { color: colors.primary },
  link: { color: colors.primary, fontWeight: '600' },
  list: { padding: 12, gap: 8, flexGrow: 1 },
  empty: { flex: 1, justifyContent: 'center', gap: 10 },
  emptyTitle: { fontSize: 17, color: colors.text, fontWeight: '600', marginBottom: 6 },
  example: { backgroundColor: colors.card, borderColor: colors.border, borderWidth: 1, borderRadius: 12, padding: 12 },
  exampleText: { color: colors.text },
  bubble: { maxWidth: '85%', borderRadius: 16, paddingHorizontal: 14, paddingVertical: 10 },
  userBubble: { alignSelf: 'flex-end', backgroundColor: colors.userBubble },
  botBubble: { alignSelf: 'flex-start', backgroundColor: colors.botBubble },
  bubbleText: { fontSize: 16, color: colors.text, lineHeight: 22 },
  userText: { color: colors.primaryText },
  errorText: { color: colors.danger },
  partial: { paddingHorizontal: 16, color: colors.muted, fontStyle: 'italic' },
  voiceError: { paddingHorizontal: 16, color: colors.danger },
  inputRow: { flexDirection: 'row', alignItems: 'center', padding: 12, gap: 10 },
  input: {
    flex: 1,
    backgroundColor: colors.card,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: 24,
    paddingHorizontal: 16,
    paddingVertical: 12,
    fontSize: 16,
    color: colors.text,
  },
  mic: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  micActive: { backgroundColor: colors.danger },
  micIcon: { fontSize: 26, color: colors.primaryText },
});
