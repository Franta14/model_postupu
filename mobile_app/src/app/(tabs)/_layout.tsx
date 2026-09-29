import { Tabs } from 'expo-router';
import { StyleSheet, View, Text } from 'react-native';
import Feather from '@expo/vector-icons/Feather';
import Svg, { Path, Line, Circle, Polygon } from 'react-native-svg';
import { useFilter } from '../../context/FilterContext';

// Custom Orienťácká Map Ikonka z webu
const CustomMapIcon = ({ color, size, strokeWidth }: { color: any; size: number; strokeWidth: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
    <Path d="M9 4L15 7L21 4V18L15 21L9 18L3 21V7Z" />
    <Line x1="9" y1="4" x2="9" y2="18" />
    <Line x1="15" y1="7" x2="15" y2="21" />
    {/* Circle in left fold */}
    <Circle cx="6" cy="10" r="1.5" />
    {/* Triangle in right fold */}
    <Polygon points="18 13 16.5 16 19.5 16" />
    {/* Dash line from left to right */}
    <Path d="M7 14c1.5 2 4.5 2 6-1 1.5-3 4-1 4 0" strokeDasharray="2 3" />
  </Svg>
);

export default function TabLayout() {
  const { activeFilterCount } = useFilter();

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarShowLabel: false,
        tabBarStyle: styles.tabBar,
        tabBarActiveTintColor: '#000000', // Instagram style
        tabBarInactiveTintColor: 'rgba(0, 0, 0, 0.4)',
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Explore',
          tabBarIcon: ({ color, focused }) => <Feather name="compass" size={28} color={color} strokeWidth={focused ? 2 : 1.5} />,
        }}
      />
      <Tabs.Screen
        name="reels"
        options={{
          title: 'Reels',
          tabBarIcon: ({ color, focused }) => (
            <View style={styles.mapIconWrapper}>
              <CustomMapIcon color={color} size={28} strokeWidth={focused ? 2 : 1.5} />
              {activeFilterCount > 0 && (
                <View style={styles.navBadge}>
                  <Text style={styles.navBadgeText}>{activeFilterCount}</Text>
                </View>
              )}
            </View>
          ),
        }}
      />
      <Tabs.Screen
        name="chat"
        options={{
          title: 'Chat',
          tabBarIcon: ({ color, focused }) => <Feather name="send" size={28} color={color} strokeWidth={focused ? 2 : 1.5} />,
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: 'Settings',
          tabBarIcon: ({ color, focused }) => <Feather name="settings" size={28} color={color} strokeWidth={focused ? 2 : 1.5} />,
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: 'Profile',
          tabBarIcon: ({ color, focused }) => <Feather name="user" size={28} color={color} strokeWidth={focused ? 2 : 1.5} />,
        }}
      />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  tabBar: {
    backgroundColor: '#ffffff',
    borderTopWidth: 0.5,
    borderTopColor: '#dbdbdb',
    height: 85,
    paddingTop: 10,
    paddingBottom: 25,
  },
  mapIconWrapper: {
    width: 32,
    height: 32,
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative',
  },
  navBadge: {
    position: 'absolute',
    top: -4,
    right: -8,
    backgroundColor: '#ff3040',
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    borderWidth: 2,
    borderColor: '#ffffff',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 2,
    zIndex: 10,
  },
  navBadgeText: {
    color: '#ffffff',
    fontSize: 9.5,
    fontWeight: '700',
    textAlign: 'center',
    includeFontPadding: false,
  },
});
