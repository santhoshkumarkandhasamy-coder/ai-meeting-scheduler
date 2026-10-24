import * as Speech from 'expo-speech';
import { ExpoSpeechRecognitionModule, useSpeechRecognitionEvent } from 'expo-speech-recognition';
import { useCallback, useEffect, useRef, useState } from 'react';

export type VoiceLang = 'ta-IN' | 'en-IN';

const TAMIL_SCRIPT = /[஀-௿]/;

/** Speak a reply aloud, picking the Tamil or English voice from the text itself. */
export function speak(text: string) {
  Speech.stop();
  Speech.speak(text, { language: TAMIL_SCRIPT.test(text) ? 'ta-IN' : 'en-IN', rate: 1.0 });
}

export function stopSpeaking() {
  Speech.stop();
}

/** Push-to-talk speech recognition. `onFinal` receives the final transcript. */
export function useVoiceInput(onFinal: (text: string) => void) {
  const [listening, setListening] = useState(false);
  const [partial, setPartial] = useState('');
  const [error, setError] = useState<string | null>(null);
  const finalText = useRef('');
  const onFinalRef = useRef(onFinal);
  useEffect(() => {
    onFinalRef.current = onFinal;
  }, [onFinal]);

  useSpeechRecognitionEvent('start', () => {
    finalText.current = '';
    setPartial('');
    setError(null);
    setListening(true);
  });
  useSpeechRecognitionEvent('result', (event) => {
    const text = event.results[0]?.transcript ?? '';
    setPartial(text);
    if (event.isFinal) finalText.current = text;
  });
  useSpeechRecognitionEvent('error', (event) => {
    if (event.error !== 'aborted' && event.error !== 'no-speech') setError(event.message || event.error);
  });
  useSpeechRecognitionEvent('end', () => {
    setListening(false);
    const text = (finalText.current || '').trim();
    if (text) onFinalRef.current(text);
  });

  const start = useCallback(async (lang: VoiceLang) => {
    stopSpeaking();
    const permission = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
    if (!permission.granted) {
      setError('Microphone permission is needed to talk to the assistant.');
      return;
    }
    ExpoSpeechRecognitionModule.start({
      lang,
      interimResults: true,
      continuous: false,
      addsPunctuation: true,
    });
  }, []);

  const stop = useCallback(() => ExpoSpeechRecognitionModule.stop(), []);

  return { listening, partial, error, start, stop };
}
