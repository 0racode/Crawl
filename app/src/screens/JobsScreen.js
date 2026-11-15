import React, { useCallback, useState } from 'react';
import { FlatList, RefreshControl, Text, TouchableOpacity, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useFocusEffect } from '@react-navigation/native';
import { api } from '../api';
import { colors, s } from '../theme';

export const statusColor = (st) =>
  ({ done: colors.accent, running: colors.warn, queued: colors.warn, failed: colors.danger,
     cancelled: colors.muted, interrupted: colors.muted }[st] || colors.muted);

export default function JobsScreen({ navigation }) {
  const [jobs, setJobs] = useState([]);
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try { setJobs(await api.listJobs()); setErr(''); }
    catch (e) { setErr(e.message); }
    finally { setLoading(false); }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  return (
    <SafeAreaView style={s.screen} edges={['top']}>
      <Text style={[s.title, { fontSize: 20, padding: 16, paddingBottom: 4 }]}>Crawl jobs</Text>
      {err ? <Text style={{ color: colors.danger, paddingHorizontal: 16 }}>{err}</Text> : null}
      <FlatList
        data={jobs} keyExtractor={(j) => j.id} contentContainerStyle={s.pad}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor={colors.accent} />}
        ListEmptyComponent={!loading && !err ? <Text style={s.muted}>No jobs yet. Browse to a page and tap “Crawl site”.</Text> : null}
        renderItem={({ item }) => (
          <TouchableOpacity style={s.card} onPress={() => navigation.navigate('JobDetail', { id: item.id })}>
            <View style={[s.row, { justifyContent: 'space-between' }]}>
              <Text style={[s.title, { flex: 1 }]} numberOfLines={1}>{item.start_url}</Text>
              <Text style={{ color: statusColor(item.status), fontSize: 12, fontWeight: '700' }}>{item.status}</Text>
            </View>
            <Text style={[s.muted, { marginTop: 4 }]}>
              {item.stats.crawled || 0} pages · {item.stats.failed || 0} failed · {new Date(item.created * 1000).toLocaleString()}
            </Text>
          </TouchableOpacity>
        )}
      />
    </SafeAreaView>
  );
}
