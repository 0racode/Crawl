import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { NavigationContainer, DarkTheme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Text } from 'react-native';

import BrowseScreen from './src/screens/BrowseScreen';
import CrawlConfigScreen from './src/screens/CrawlConfigScreen';
import JobsScreen from './src/screens/JobsScreen';
import JobDetailScreen from './src/screens/JobDetailScreen';
import JsonViewScreen from './src/screens/JsonViewScreen';
import SettingsScreen from './src/screens/SettingsScreen';
import { colors } from './src/theme';

const Tab = createBottomTabNavigator();
const Stack = createNativeStackNavigator();

const theme = {
  ...DarkTheme,
  colors: { ...DarkTheme.colors, background: colors.bg, card: colors.card, text: colors.text,
            primary: colors.accent, border: colors.border },
};

const icon = (g) => ({ color }) => <Text style={{ color, fontSize: 18 }}>{g}</Text>;

function Tabs() {
  return (
    <Tab.Navigator screenOptions={{ tabBarActiveTintColor: colors.accent, headerShown: false }}>
      <Tab.Screen name="Browse" component={BrowseScreen} options={{ tabBarIcon: icon('🌐') }} />
      <Tab.Screen name="Jobs" component={JobsScreen} options={{ tabBarIcon: icon('📦') }} />
      <Tab.Screen name="Settings" component={SettingsScreen} options={{ tabBarIcon: icon('⚙️') }} />
    </Tab.Navigator>
  );
}

export default function App() {
  return (
    <NavigationContainer theme={theme}>
      <StatusBar style="light" />
      <Stack.Navigator>
        <Stack.Screen name="Tabs" component={Tabs} options={{ headerShown: false }} />
        <Stack.Screen name="CrawlConfig" component={CrawlConfigScreen} options={{ title: 'Crawl settings' }} />
        <Stack.Screen name="JobDetail" component={JobDetailScreen} options={{ title: 'Crawl job' }} />
        <Stack.Screen name="JsonView" component={JsonViewScreen} options={{ title: 'Extracted JSON' }} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
