#!/usr/bin/env bash
# Creates a fresh Expo project with SDK-matched dependency versions, then drops this source into it.
# Usage:  ./setup.sh   (run from the app/ folder; creates ../sitecrawler-app)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/../sitecrawler-app"

npx create-expo-app@latest "$OUT" --template blank --no-install
cp "$HERE/App.js" "$OUT/App.js"
mkdir -p "$OUT/src" && cp -r "$HERE/src/." "$OUT/src/"

cd "$OUT"
npm install
# `expo install` picks versions compatible with the project's Expo SDK
npx expo install @react-navigation/native @react-navigation/native-stack @react-navigation/bottom-tabs \
  react-native-screens react-native-safe-area-context react-native-webview \
  @react-native-async-storage/async-storage expo-clipboard expo-status-bar expo-build-properties

# Allow plain-http backends (LAN / emulator) in release builds. Prefer HTTPS in production.
node -e '
const fs=require("fs");const p=JSON.parse(fs.readFileSync("app.json"));
p.expo.name="SiteCrawler";p.expo.userInterfaceStyle="dark";
p.expo.android={...(p.expo.android||{}),package:"com.sitecrawler.app"};
p.expo.plugins=[...(p.expo.plugins||[]),["expo-build-properties",{android:{usesCleartextTraffic:true}}]];
fs.writeFileSync("app.json",JSON.stringify(p,null,2));'

echo
echo "Done. Next:  cd $OUT && npx expo start   (scan the QR with Expo Go)"
echo "Build an APK: npx eas-cli build -p android --profile preview"
