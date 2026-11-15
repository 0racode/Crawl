import React, { useState } from 'react';
import { ActivityIndicator, Alert, ScrollView, Switch, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { api } from '../api';
import { colors, s } from '../theme';

const num = (v, d) => { const n = parseInt(v, 10); return Number.isFinite(n) ? n : d; };
const lines = (t) => t.split('\n').map((x) => x.trim()).filter(Boolean);

function Toggle({ label, value, onChange, hint }) {
  return (
    <View style={[s.row, { justifyContent: 'space-between', marginTop: 12 }]}>
      <View style={{ flex: 1, paddingRight: 12 }}>
        <Text style={s.title}>{label}</Text>
        {hint ? <Text style={s.muted}>{hint}</Text> : null}
      </View>
      <Switch value={value} onValueChange={onChange} trackColor={{ true: colors.accent }} />
    </View>
  );
}

function Field({ label, value, onChange, kb = 'number-pad', multiline, ph }) {
  return (
  <>
    <Text style={s.label}>{label}</Text>
    <TextInput style={[s.input, multiline && { minHeight: 70, textAlignVertical: 'top' }]} value={value}
      onChangeText={onChange} keyboardType={kb} multiline={multiline} placeholder={ph}
      placeholderTextColor={colors.muted} autoCapitalize="none" autoCorrect={false} />
  </>
);
}

export default function CrawlConfigScreen({ route, navigation }) {
  const [url, setUrl] = useState(route.params?.url || '');
  const [maxPages, setMaxPages] = useState('100');
  const [maxDepth, setMaxDepth] = useState('3');
  const [concurrency, setConcurrency] = useState('4');
  const [delay, setDelay] = useState('300');
  const [subs, setSubs] = useState(false);
  const [robots, setRobots] = useState(true);
  const [sitemap, setSitemap] = useState(true);
  const [text, setText] = useState(true);
  const [links, setLinks] = useState(true);
  const [images, setImages] = useState(true);
  const [include, setInclude] = useState('');
  const [exclude, setExclude] = useState('');
  const [selectors, setSelectors] = useState('');
  const [render, setRender] = useState('auto');
  const [busy, setBusy] = useState(false);

  const start = async () => {
    const sel = {};
    for (const l of lines(selectors)) {
      const i = l.indexOf('=');
      if (i < 1) return Alert.alert('Selector format', 'Use one per line: name=css selector  (add @attr to read an attribute, e.g. img=img.hero@src)');
      sel[l.slice(0, i).trim()] = l.slice(i + 1).trim();
    }
    setBusy(true);
    try {
      const job = await api.createJob({
        start_url: url.trim(),
        max_pages: num(maxPages, 100), max_depth: num(maxDepth, 3),
        concurrency: num(concurrency, 4), delay_ms: num(delay, 300),
        include_subdomains: subs, respect_robots: robots, use_sitemap: sitemap,
        render_js: render, include_text: text, include_links: links, include_images: images,
        include_patterns: lines(include), exclude_patterns: lines(exclude), selectors: sel,
      });
      navigation.replace('JobDetail', { id: job.id });
    } catch (e) { Alert.alert('Could not start crawl', e.message); }
    finally { setBusy(false); }
  };

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.pad} keyboardShouldPersistTaps="handled">
      <Field label="Start URL" value={url} onChange={setUrl} kb="url" />
      <View style={[s.row, { gap: 10 }]}>
        <View style={{ flex: 1 }}><Field label="Max pages" value={maxPages} onChange={setMaxPages} /></View>
        <View style={{ flex: 1 }}><Field label="Max depth" value={maxDepth} onChange={setMaxDepth} /></View>
      </View>
      <View style={[s.row, { gap: 10 }]}>
        <View style={{ flex: 1 }}><Field label="Parallel requests" value={concurrency} onChange={setConcurrency} /></View>
        <View style={{ flex: 1 }}><Field label="Delay (ms)" value={delay} onChange={setDelay} /></View>
      </View>

      <Text style={s.label}>JavaScript pages</Text>
      <View style={[s.row, { gap: 8 }]}>
        {['off', 'auto', 'always'].map((m) => (
          <TouchableOpacity key={m} onPress={() => setRender(m)}
            style={[render === m ? s.btn : s.btnGhost, { flex: 1, paddingVertical: 9 }]}>
            <Text style={render === m ? s.btnText : s.btnGhostText}>{m}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <Text style={s.muted}>auto = render in a real browser only when a page looks empty (slower, needs server support)</Text>

      <Toggle label="Use sitemap" value={sitemap} onChange={setSitemap} hint="Finds pages not linked from the start page" />
      <Toggle label="Respect robots.txt" value={robots} onChange={setRobots} hint="Recommended" />
      <Toggle label="Include subdomains" value={subs} onChange={setSubs} />
      <Toggle label="Save page text" value={text} onChange={setText} />
      <Toggle label="Save links" value={links} onChange={setLinks} />
      <Toggle label="Save images" value={images} onChange={setImages} />

      <Field label="Only crawl URLs matching (regex, one per line)" value={include} onChange={setInclude} kb="default" multiline ph="/blog/" />
      <Field label="Skip URLs matching (regex, one per line)" value={exclude} onChange={setExclude} kb="default" multiline ph="/login|/cart" />
      <Field label="Custom fields (name=css selector, one per line)" value={selectors} onChange={setSelectors} kb="default" multiline ph={'price=.price\nhero=img.hero@src'} />

      <TouchableOpacity style={[s.btn, { marginTop: 22 }]} onPress={start} disabled={busy}>
        {busy ? <ActivityIndicator color="#06231b" /> : <Text style={s.btnText}>Start crawl</Text>}
      </TouchableOpacity>
      <Text style={[s.muted, { marginTop: 10, textAlign: 'center' }]}>Only crawl sites you have the right to. Public pages only.</Text>
    </ScrollView>
  );
}
