import React, { useRef, useState } from 'react';
import { ActivityIndicator, Alert, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { WebView } from 'react-native-webview';
import { api } from '../api';
import { colors, s } from '../theme';

const normalize = (t) => {
  const v = t.trim();
  if (!v) return '';
  if (/^https?:\/\//i.test(v)) return v;
  return 'https://' + v;
};

export default function BrowseScreen({ navigation }) {
  const web = useRef(null);
  const [input, setInput] = useState('');
  const [uri, setUri] = useState(null);
  const [current, setCurrent] = useState('');
  const [canBack, setCanBack] = useState(false);
  const [busy, setBusy] = useState(false);

  const go = () => {
    const u = normalize(input);
    if (u) { setUri(u); setCurrent(u); }
  };

  const target = () => current || normalize(input);

  const extractThis = async () => {
    const url = target();
    if (!url) return Alert.alert('Enter a URL first');
    setBusy(true);
    try {
      const data = await api.extract({ url });
      navigation.navigate('JsonView', { data, title: data.title || url });
    } catch (e) { Alert.alert('Extraction failed', e.message); }
    finally { setBusy(false); }
  };

  const crawlSite = () => {
    const url = target();
    if (!url) return Alert.alert('Enter a URL first');
    navigation.navigate('CrawlConfig', { url });
  };

  return (
    <SafeAreaView style={s.screen} edges={['top']}>
      <View style={[s.row, { padding: 10, gap: 8 }]}>
        <TouchableOpacity disabled={!canBack} onPress={() => web.current?.goBack()}>
          <Text style={{ color: canBack ? colors.text : colors.muted, fontSize: 22, paddingHorizontal: 6 }}>‹</Text>
        </TouchableOpacity>
        <TextInput
          style={[s.input, { flex: 1 }]} value={input} onChangeText={setInput}
          placeholder="Enter a public page URL" placeholderTextColor={colors.muted}
          autoCapitalize="none" autoCorrect={false} keyboardType="url"
          returnKeyType="go" onSubmitEditing={go}
        />
        <TouchableOpacity onPress={go}><Text style={{ color: colors.accent, fontWeight: '700' }}>Go</Text></TouchableOpacity>
      </View>

      <View style={{ flex: 1, backgroundColor: '#fff' }}>
        {uri ? (
          <WebView
            ref={web} source={{ uri }} startInLoadingState
            onNavigationStateChange={(st) => { setCurrent(st.url); setCanBack(st.canGoBack); setInput(st.url); }}
            renderLoading={() => <ActivityIndicator style={{ position: 'absolute', top: 24, alignSelf: 'center' }} color={colors.accent} />}
          />
        ) : (
          <View style={{ flex: 1, backgroundColor: colors.bg, justifyContent: 'center', padding: 28 }}>
            <Text style={[s.title, { textAlign: 'center', fontSize: 18 }]}>Start from any public page</Text>
            <Text style={[s.muted, { textAlign: 'center', marginTop: 8, lineHeight: 18 }]}>
              Browse to a page, then extract just that page, or crawl the whole site, including pages you haven't opened.
            </Text>
          </View>
        )}
      </View>

      <View style={[s.row, { padding: 10, gap: 10 }]}>
        <TouchableOpacity style={[s.btnGhost, { flex: 1 }]} onPress={extractThis} disabled={busy}>
          {busy ? <ActivityIndicator color={colors.accent} /> : <Text style={s.btnGhostText}>Extract page</Text>}
        </TouchableOpacity>
        <TouchableOpacity style={[s.btn, { flex: 1 }]} onPress={crawlSite}>
          <Text style={s.btnText}>Crawl site</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}
