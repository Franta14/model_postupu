import { Tabs, usePathname } from 'expo-router';
import { StyleSheet, View, Text, Pressable } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Feather from '@expo/vector-icons/Feather';
import Svg, { Path, Line } from 'react-native-svg';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withTiming,
  interpolateColor,
  Easing,
} from 'react-native-reanimated';
import React, { useEffect } from 'react';
import { useFilter } from '../../context/FilterContext';
import { useThemeColors } from '../../context/AppContext';

// Mapa ikonka (identická s webem — čisté SVG)
const CleanMapIcon = ({
  color,
  size,
  strokeWidth,
}: {
  color: string;
  size: number;
  strokeWidth: number;
}) => (
  <Svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke={color}
    strokeWidth={strokeWidth}
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <Path d="M9 4L15 7L21 4V18L15 21L9 18L3 21V7Z" />
    <Line x1="9" y1="4" x2="9" y2="18" />
    <Line x1="15" y1="7" x2="15" y2="21" />
  </Svg>
);

// Animovaný background tab baru — interpoluje mezi bílou a černou
function AnimatedTabBackground({ isReels, colors }: { isReels: boolean; colors: any }) {
  const progress = useSharedValue(0);

  useEffect(() => {
    progress.value = withTiming(isReels ? 1 : 0, {
      duration: 280,
      easing: Easing.out(Easing.ease),
    });
  }, [isReels]);

  const animatedStyle = useAnimatedStyle(() => ({
    backgroundColor: interpolateColor(progress.value, [0, 1], [colors.background, '#000000']),
    borderTopColor: interpolateColor(
      progress.value,
      [0, 1],
      [colors.border, 'rgba(255,255,255,0.15)']
    ),
    flex: 1,
    borderTopWidth: 0.5,
  }));

  return <Animated.View style={animatedStyle} />;
}

export default function TabLayout() {
  const { activeFilterCount } = useFilter();
  const pathname = usePathname();
  const insets = useSafeAreaInsets();
  const colors = useThemeColors();
  const isDarkReels = pathname === '/reels';
  const bottomInset = insets.bottom > 0 ? insets.bottom : 4;
  const tabHeight = 46 + bottomInset;
  
  const styles = React.useMemo(() => getStyles(colors), [colors]);

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarShowLabel: false,
        tabBarStyle: [
          styles.tabBar,
          { height: tabHeight, paddingBottom: bottomInset, paddingTop: 4 },
        ],
        tabBarActiveTintColor: isDarkReels ? '#ffffff' : colors.text,
        tabBarInactiveTintColor: isDarkReels
          ? 'rgba(255, 255, 255, 0.45)'
          : colors.secondaryText,
        // Animovaný background
        tabBarBackground: () => <AnimatedTabBackground isReels={isDarkReels} colors={colors} />,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Explore',
          tabBarIcon: ({ color, focused }) => (
            <Feather name="compass" size={23} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="reels"
        options={{
          title: 'Reels',
          tabBarIcon: ({ color, focused }) => (
            <View style={styles.mapIconWrapper}>
              <CleanMapIcon color={color as string} size={23} strokeWidth={focused ? 2.1 : 1.7} />
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
          tabBarIcon: ({ color, focused }) => (
            <Feather name="send" size={22} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: 'Settings',
          tabBarIcon: ({ color, focused }) => (
            <Feather name="settings" size={22} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: 'Profile',
          tabBarIcon: ({ color, focused }) => (
            <Feather name="user" size={23} color={color} />
          ),
        }}
      />
    </Tabs>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  tabBar: {
    // backgroundColor je animovány přes tabBarBackground
    backgroundColor: 'transparent',
    borderTopWidth: 0, // border je v AnimatedTabBackground
  },
  mapIconWrapper: {
    width: 26,
    height: 26,
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative',
  },
  navBadge: {
    position: 'absolute',
    top: -3,
    right: -7,
    backgroundColor: '#ff3040',
    minWidth: 15,
    height: 15,
    borderRadius: 7.5,
    borderWidth: 1.5,
    borderColor: colors.background,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 2,
    zIndex: 10,
  },
  navBadgeText: {
    color: '#ffffff',
    fontSize: 8.5,
    fontWeight: '700',
    textAlign: 'center',
    includeFontPadding: false,
  },
});
