import { StyleSheet } from 'react-native';

export const colors = {
  bg: '#0e1116', card: '#161b22', border: '#2a313c', text: '#e6edf3', muted: '#8b949e',
  accent: '#4cc2a0', danger: '#f0616d', warn: '#e3b341',
};

export const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  pad: { padding: 16 },
  card: { backgroundColor: colors.card, borderColor: colors.border, borderWidth: 1, borderRadius: 12, padding: 12, marginBottom: 10 },
  title: { color: colors.text, fontSize: 15, fontWeight: '600' },
  muted: { color: colors.muted, fontSize: 12 },
  label: { color: colors.muted, fontSize: 12, marginTop: 14, marginBottom: 6 },
  input: { backgroundColor: colors.card, color: colors.text, borderColor: colors.border, borderWidth: 1, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14 },
  btn: { backgroundColor: colors.accent, borderRadius: 10, paddingVertical: 12, paddingHorizontal: 16, alignItems: 'center' },
  btnText: { color: '#06231b', fontWeight: '700', fontSize: 14 },
  btnGhost: { borderColor: colors.border, borderWidth: 1, borderRadius: 10, paddingVertical: 12, paddingHorizontal: 16, alignItems: 'center' },
  btnGhostText: { color: colors.text, fontWeight: '600', fontSize: 14 },
  row: { flexDirection: 'row', alignItems: 'center' },
  mono: { color: colors.text, fontFamily: 'monospace', fontSize: 11 },
});
