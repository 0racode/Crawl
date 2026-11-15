import React, { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, Text, TextInput, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { api, getSettings, saveSettings } from '../api';
import { colors, s } from '../theme';

export default function SettingsScreen() {
  const [baseUrl, setBaseUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [msg, setMsg] = useState({ text: '', ok: true });
  const [busy, setBusy] = useState(false);

  useEffect(() => { getSettings().then((c) => { setBaseUrl(c.baseUrl); setApiKey(c.apiKey); }); }, []);

  const save = async () => {
    setBusy(true);
    try {
      await saveSettings({ baseUrl: baseUrl.trim(), apiKey: apiKey.trim() });
      const h = await api.health();
      setMsg({ text: `Connected ✓  (${h.active_jobs} active jobs)`, ok: true });
    } catch (e) { setMsg({ text: e.message, ok: false }); }
    finally { setBusy(false); }
  };

  return (
    <SafeAreaView style={s.screen} edges={['top']}>
      <ScrollView contentContainerStyle={s.pad} keyboardShouldPersistTaps="handled">
        <Text style={[s.title, { fontSize: 20 }]}>Backend</Text>
        <Text style={s.label}>Server URL</Text>
        <TextInput style={s.input} value={baseUrl} onChangeText={setBaseUrl} autoCapitalize="none" autoCorrect={false}
          keyboardType="url" placeholder="https://crawler.example.com" placeholderTextColor={colors.muted} />
        <Text style={s.label}>API key (optional)</Text>
        <TextInput style={s.input} value={apiKey} onChangeText={setApiKey} autoCapitalize="none" autoCorrect={false}
          secureTextEntry placeholder="Matches API_KEY on the server" placeholderTextColor={colors.muted} />
        <TouchableOpacity style={[s.btn, { marginTop: 20 }]} onPress={save} disabled={busy}>
          {busy ? <ActivityIndicator color="#06231b" /> : <Text style={s.btnText}>Save & test connection</Text>}
        </TouchableOpacity>
        {msg.text ? <Text style={{ marginTop: 12, color: msg.ok ? colors.accent : colors.danger }}>{msg.text}</Text> : null}
        <Text style={[s.muted, { marginTop: 24, lineHeight: 18 }]}>
          Emulator: http://10.0.2.2:8000 reaches a backend on your computer.{'\n'}
          Real phone: use your computer's LAN IP (http://192.168.x.x:8000) or a deployed HTTPS URL.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}
