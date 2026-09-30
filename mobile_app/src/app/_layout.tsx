import { Stack } from 'expo-router';
import { useColorScheme, View, StyleSheet, Text } from 'react-native';
import { DarkTheme, DefaultTheme, ThemeProvider } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { useEffect, useState } from 'react';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withTiming,
  withSpring,
  withDelay,
  runOnJS,
  Easing,
} from 'react-native-reanimated';
import { FilterProvider } from '../context/FilterContext';
import { AppProvider, useApp } from '../context/AppContext';

SplashScreen.preventAutoHideAsync();

// Animovaný custom splash screen (Task 16)
function AnimatedSplashScreen({ onFinish }: { onFinish: () => void }) {
  const opacity = useSharedValue(1);
  const scale = useSharedValue(0.8);

  useEffect(() => {
    SplashScreen.hideAsync().catch(() => {});
    
    // Scale-in animace loga
    scale.value = withSpring(1, { damping: 15, stiffness: 100 });
    
    // Fade out po 1 sekundě
    opacity.value = withDelay(1200, withTiming(0, { duration: 400, easing: Easing.inOut(Easing.ease) }, (finished) => {
      if (finished) runOnJS(onFinish)();
    }));
  }, []);

  const animatedStyle = useAnimatedStyle(() => ({
    opacity: opacity.value,
  }));
  
  const logoStyle = useAnimatedStyle(() => ({
    transform: [{ scale: scale.value }],
  }));

  return (
    <Animated.View style={[styles.splashContainer, animatedStyle]}>
      <Animated.View style={[styles.logoBox, logoStyle]}>
        <Text style={styles.logoText}>SCROLLIENTEERING</Text>
      </Animated.View>
    </Animated.View>
  );
}

// Wrapper pro dynamické přepínání dark/light podle uživatelského nastavení
function ThemeWrapper({ children }: { children: React.ReactNode }) {
  const systemColorScheme = useColorScheme();
  const { userSettings, isLoaded } = useApp();

  if (!isLoaded) return null; // Zůstává nativní splash screen, dokud se nenačte nastavení

  const isDark =
    userSettings.theme === 'dark' ||
    (userSettings.theme === 'system' && systemColorScheme === 'dark');

  return (
    <ThemeProvider value={isDark ? DarkTheme : DefaultTheme}>
      {children}
    </ThemeProvider>
  );
}

// Wrapper pro skrytí splash screenu a spuštění custom animace
function RootLayoutInner() {
  const [animationFinished, setAnimationFinished] = useState(false);

  return (
    <View style={{ flex: 1, backgroundColor: '#ffffff' }}>
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="(tabs)" />
        {/* Detail postupu */}
        <Stack.Screen name="postup/[id]" />
      </Stack>
      
      {!animationFinished && (
        <AnimatedSplashScreen onFinish={() => setAnimationFinished(true)} />
      )}
    </View>
  );
}

export default function RootLayout() {
  return (
    <AppProvider>
      <ThemeWrapper>
        <FilterProvider>
          <RootLayoutInner />
        </FilterProvider>
      </ThemeWrapper>
    </AppProvider>
  );
}

const styles = StyleSheet.create({
  splashContainer: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: '#ffffff',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 9999,
  },
  logoBox: {
    padding: 20,
    backgroundColor: '#000000',
    borderRadius: 16,
  },
  logoText: {
    color: '#ffffff',
    fontSize: 22,
    fontWeight: '900',
    letterSpacing: 2,
  },
});
