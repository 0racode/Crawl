import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, FlatList, Linking, Text, TouchableOpacity, View } from 'react-native';
import { api } from '../api';
import { colors, s } from '../theme';
import { statusColor } from './JobsScreen';

export default function JobDetailScreen({ route, navigation }) {
  const { id } = route.params;
  const [job, setJob] = useState(null);
  const [items, setItems] = useState([]);
  const [err, setErr] = useState('');
  const cursor = useRef(0);
  const jobRef = useRef(null);

  const fetchMore = useCallback(async () => {
    // drain all new results since the cursor
    for (let i = 0; i < 20; i++) {
      const r = await api.results(id, cursor.current, 50);
      if (!r.items.length) break;
      cursor.current = r.next;
      setItems((prev) => [...prev, ...r.items]);
      if (r.items.length < 50) break;
    }
  }, [id]);

  const refresh = useCallback(async () => {
    try {
      const j = await api.getJob(id);
      jobRef.current = j; setJob(j); setErr('');
      await fetchMore();
    } catch (e) { setErr(e.message); }
  }, [id, fetchMore]);

  useEffect(() => {
    refresh();
    const t = setInterval(() => {
      const st = jobRef.current?.status;
      if (!st || st === 'running' || st === 'queued') refresh();
    }, 2000);
    return () => clearInterval(t);
  }, [refresh]);

  const active = job && (job.status === 'running' || job.status === 'queued');

  const doExport = async (format) => {
    try { await Linking.openURL(await api.exportUrl(id, format)); }
    catch (e) { Alert.alert('Export failed', e.message); }
  };

  const cancel = async () => { try { await api.cancel(id); refresh(); } catch (e) { Alert.alert('Cancel failed', e.message); } };
  const remove = () => Alert.alert('Delete job?', 'This removes the job and all its extracted data.', [
    { text: 'Cancel', style: 'cancel' },
    { text: 'Delete', style: 'destructive', onPress: async () => { try { await api.remove(id); navigation.goBack(); } catch (e) { Alert.alert('Delete failed', e.message); } } },
  ]);

  const stats = job?.stats || {};
  const cap = job?.config?.max_pages || 1;
  const pct = Math.min(100, Math.round(((stats.crawled || 0) / cap) * 100));

  const Header = (
    <View style={{ marginBottom: 12 }}>
      <Text style={s.title} numberOfLines={2}>{job?.start_url}</Text>
      <View style={[s.row, { marginTop: 6, justifyContent: 'space-between' }]}>
        <Text style={{ color: statusColor(job?.status), fontWeight: '700' }}>{job?.status || '…'}</Text>
        <Text style={s.muted}>{stats.crawled || 0} / {cap} pages · {stats.failed || 0} failed · {stats.queued || 0} found</Text>
      </View>
      <View style={{ height: 6, backgroundColor: colors.border, borderRadius: 3, marginTop: 8, overflow: 'hidden' }}>
        <View style={{ width: `${pct}%`, height: 6, backgroundColor: colors.accent }} />
      </View>
      {job?.error ? <Text style={{ color: colors.danger, marginTop: 8 }}>{job.error}</Text> : null}
      {err ? <Text style={{ color: colors.danger, marginTop: 8 }}>{err}</Text> : null}
      <View style={[s.row, { gap: 8, marginTop: 12 }]}>
        {active ? (
          <TouchableOpacity style={[s.btnGhost, { flex: 1 }]} onPress={cancel}><Text style={s.btnGhostText}>Stop</Text></TouchableOpacity>
        ) : (
          <>
            <TouchableOpacity style={[s.btn, { flex: 1 }]} onPress={() => doExport('json')}><Text style={s.btnText}>Export JSON</Text></TouchableOpacity>
            <TouchableOpacity style={[s.btnGhost, { flex: 1 }]} onPress={() => doExport('ndjson')}><Text style={s.btnGhostText}>NDJSON</Text></TouchableOpacity>
            <TouchableOpacity style={s.btnGhost} onPress={remove}><Text style={{ color: colors.danger }}>Delete</Text></TouchableOpacity>
          </>
        )}
      </View>
    </View>
  );

  return (
    <FlatList
      style={s.screen} contentContainerStyle={s.pad} data={items} keyExtractor={(i) => String(i._id)}
      ListHeaderComponent={Header}
      onEndReached={() => fetchMore().catch(() => {})} onEndReachedThreshold={0.5}
      renderItem={({ item }) => (
        <TouchableOpacity style={s.card}
          onPress={async () => {
            try {
              const data = await api.page(id, item._id);
              navigation.navigate('JsonView', { data, title: data.title || data.url });
            } catch (e) { Alert.alert('Could not load page', e.message); }
          }}>
          <Text style={s.title} numberOfLines={1}>{item.title || item.url}</Text>
          <Text style={s.muted} numberOfLines={1}>{item.url}</Text>
          <Text style={{ color: item.status === 'ok' ? colors.muted : colors.danger, fontSize: 12, marginTop: 2 }}>
            {item.status === 'ok' ? `depth ${item.depth} · ${item.word_count} words` : item.error || item.status}
          </Text>
        </TouchableOpacity>
      )}
    />
  );
}
