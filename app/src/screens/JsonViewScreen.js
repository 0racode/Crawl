import React, { useLayoutEffect, useMemo } from 'react';
import { Alert, ScrollView, Share, Text, TouchableOpacity } from 'react-native';
import * as Clipboard from 'expo-clipboard';
import { colors, s } from '../theme';

export default function JsonViewScreen({ route, navigation }) {
  const { data, title } = route.params;
  // Cap rendering size so a huge page doesn't freeze the UI; copy/share still use the full JSON.
  const full = useMemo(() => JSON.stringify(data, null, 2), [data]);
  const shown = full.length > 60000 ? full.slice(0, 60000) + '\n… (truncated in view, copy for full JSON)' : full;

  useLayoutEffect(() => {
    navigation.setOptions({
      title: (title || 'Extracted JSON').slice(0, 28),
      headerRight: () => (
        <TouchableOpacity onPress={async () => { await Clipboard.setStringAsync(full); Alert.alert('Copied', 'JSON copied to clipboard'); }}>
          <Text style={{ color: colors.accent, fontWeight: '700' }}>Copy</Text>
        </TouchableOpacity>
      ),
    });
  }, [navigation, title, full]);

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.pad}>
      <ScrollView horizontal>
        <Text selectable style={s.mono}>{shown}</Text>
      </ScrollView>
      <TouchableOpacity style={[s.btnGhost, { marginTop: 16 }]} onPress={() => Share.share({ message: full })}>
        <Text style={s.btnGhostText}>Share JSON</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}
