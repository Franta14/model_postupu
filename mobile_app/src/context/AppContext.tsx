import React, { createContext, useContext, useState, useEffect, useRef, ReactNode } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useColorScheme } from 'react-native';

// ==========================================
// STORAGE KEYS
// ==========================================
const STORAGE_KEYS = {
  userSettings: 'user_settings',
  savedRoutes: 'saved_postupy',
  likedRoutes: 'liked_postupy',
  viewedRoutes: 'viewed_postupy',
  appTimeMs: 'app_time_ms',
  userName: 'profile_username',
  userBio: 'profile_bio',
  userAvatar: 'profile_avatar',
} as const;

// ==========================================
// TYPES
// ==========================================
export interface UserSettings {
  pace: number; // v sekundách, default 220 (3:40 min/km)
  language: 'cs' | 'en';
  theme: 'system' | 'light' | 'dark';
}

const DEFAULT_SETTINGS: UserSettings = {
  pace: 220,
  language: 'cs',
  theme: 'system',
};

// ==========================================
// i18n SLOVNÍK (identický s webem)
// ==========================================
const i18n = {
  cs: {
    settings: 'Nastavení',
    runner: 'BĚŽEC',
    paceOnRoad: 'Tempo na cestě',
    application: 'APLIKACE',
    language: 'Jazyk',
    theme: 'Vzhled',
    theme_system: 'Systémový',
    theme_light: 'Světlý',
    theme_dark: 'Tmavý',
    offlineMaps: 'Uložit mapy offline',
    download: 'Stáhnout',
    maps: 'MAPY',
    clearCache: 'Vymazat cache',
    saved: 'Uložené',
    all: 'Vše',
    analyzed: 'Analyz.',
    km: 'Km',
    hours: 'Hodin',
    noSaved: 'Žádné uložené postupy',
    noSavedDesc: 'Klikni ve feedu na ikonku záložky pro uložení.',
    options: 'Volby',
    aerial: 'm vzdušně',
    bioDesc: 'Zde najdeš všechny své oblíbené volby postupů z tréninků a závodů.',
    confirmClear: 'Opravdu chceš vymazat uložené offline mapy?',
    cacheCleared: 'Cache byla vymazána.',
    searchRoutes: 'Hledat postupy...',
    terrains: 'Terény',
    tutSwipe: 'Potáhni nahoru pro další',
    tutLike: 'Dvojklik pro To se mi líbí',
    tutOptions: 'Klikni na Volby pro srovnání',
    tutBtn: 'Rozumím!',
  },
  en: {
    settings: 'Settings',
    runner: 'RUNNER',
    paceOnRoad: 'Pace on road',
    application: 'APPLICATION',
    language: 'Language',
    theme: 'Appearance',
    theme_system: 'System',
    theme_light: 'Light',
    theme_dark: 'Dark',
    offlineMaps: 'Save maps offline',
    download: 'Download',
    maps: 'MAPS',
    clearCache: 'Clear cache',
    saved: 'Saved',
    all: 'All',
    analyzed: 'Analyz.',
    km: 'Km',
    hours: 'Hours',
    noSaved: 'No saved routes',
    noSavedDesc: 'Click the bookmark icon in the feed to save.',
    options: 'Options',
    aerial: 'm aerial',
    bioDesc: 'Here you can find all your favorite route choices from training and races.',
    confirmClear: 'Do you really want to clear offline maps?',
    cacheCleared: 'Cache cleared.',
    searchRoutes: 'Search routes...',
    terrains: 'Terrains',
    tutSwipe: 'Swipe up for next route',
    tutLike: 'Double tap to like',
    tutOptions: 'Click Options for comparisons',
    tutBtn: 'Got it!',
  },
};

// ==========================================
// CONTEXT INTERFACE
// ==========================================
interface AppContextType {
  isLoaded: boolean;
  userSettings: UserSettings;
  updateSetting: <K extends keyof UserSettings>(key: K, value: UserSettings[K]) => void;
  savedRoutes: string[];
  toggleBookmark: (fileOrId: string) => void;
  isBookmarked: (fileOrId: string) => boolean;
  likedRoutes: Record<string, boolean>;
  toggleLike: (fileOrId: string) => boolean;
  isLiked: (fileOrId: string) => boolean;
  viewedRoutes: number[];
  markViewed: (id: number) => void;
  appTimeMs: number;
  t: (key: string) => string;
  formatPace: (sec: number) => string;
  getAdjustedTime: (baseSeconds: number) => number;
  formatTime: (sec: number) => string;
  userName: string;
  setUserName: (name: string) => void;
  userBio: string;
  setUserBio: (bio: string) => void;
  userAvatar: string | null;
  setUserAvatar: (avatar: string | null) => void;
}

// ==========================================
// CONTEXT + PROVIDER
// ==========================================
const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [isLoaded, setIsLoaded] = useState(false);
  const [userSettings, setUserSettings] = useState<UserSettings>(DEFAULT_SETTINGS);
  const [savedRoutes, setSavedRoutes] = useState<string[]>([]);
  const [likedRoutes, setLikedRoutes] = useState<Record<string, boolean>>({});
  const [viewedRoutes, setViewedRoutes] = useState<number[]>([]);
  const [appTimeMs, setAppTimeMs] = useState<number>(0);
  const [userName, _setUserName] = useState<string>('franta14_');
  const [userBio, _setUserBio] = useState<string>(i18n.cs.bioDesc);
  const [userAvatar, _setUserAvatar] = useState<string | null>(null);

  // Ref pro okamžitý přístup ke stavu likedRoutes (řeší race condition v toggleLike)
  const likedRoutesRef = useRef<Record<string, boolean>>({});
  const savedRoutesRef = useRef<string[]>([]);

  // ============================================================
  // INICIALIZACE: Načti vše z AsyncStorage při startu
  // ============================================================
  useEffect(() => {
    const loadAllState = async () => {
      try {
        const [
          settingsRaw,
          savedRaw,
          likedRaw,
          viewedRaw,
          timeRaw,
          nameRaw,
          bioRaw,
          avatarRaw,
        ] = await Promise.all([
          AsyncStorage.getItem(STORAGE_KEYS.userSettings),
          AsyncStorage.getItem(STORAGE_KEYS.savedRoutes),
          AsyncStorage.getItem(STORAGE_KEYS.likedRoutes),
          AsyncStorage.getItem(STORAGE_KEYS.viewedRoutes),
          AsyncStorage.getItem(STORAGE_KEYS.appTimeMs),
          AsyncStorage.getItem(STORAGE_KEYS.userName),
          AsyncStorage.getItem(STORAGE_KEYS.userBio),
          AsyncStorage.getItem(STORAGE_KEYS.userAvatar),
        ]);

        if (settingsRaw) {
          const parsed = JSON.parse(settingsRaw) as Partial<UserSettings>;
          setUserSettings({ ...DEFAULT_SETTINGS, ...parsed });
        }

        if (savedRaw) {
          const parsed = JSON.parse(savedRaw) as string[];
          setSavedRoutes(parsed);
          savedRoutesRef.current = parsed;
        }

        if (likedRaw) {
          const parsed = JSON.parse(likedRaw) as Record<string, boolean>;
          setLikedRoutes(parsed);
          likedRoutesRef.current = parsed;
        }

        if (viewedRaw) {
          setViewedRoutes(JSON.parse(viewedRaw) as number[]);
        }

        if (timeRaw) {
          setAppTimeMs(parseInt(timeRaw, 10) || 0);
        }

        if (nameRaw) _setUserName(nameRaw);
        if (bioRaw) _setUserBio(bioRaw);
        if (avatarRaw) _setUserAvatar(avatarRaw);
      } catch (e) {
        console.warn('[AppContext] Chyba při načítání stavu z AsyncStorage:', e);
      } finally {
        setIsLoaded(true);
      }
    };

    loadAllState();
  }, []);

  // ============================================================
  // Měření času v aplikaci (každých 5 sekund, identicky s webem)
  // ============================================================
  useEffect(() => {
    if (!isLoaded) return;
    const timer = setInterval(() => {
      setAppTimeMs((prev) => {
        const next = prev + 5000;
        AsyncStorage.setItem(STORAGE_KEYS.appTimeMs, String(next)).catch(() => {});
        return next;
      });
    }, 5000);
    return () => clearInterval(timer);
  }, [isLoaded]);

  // ============================================================
  // HELPERS
  // ============================================================
  const normalizeFile = (fileOrId: string) => {
    if (!fileOrId) return '';
    return fileOrId.replace('.geojson', '').replace('.json', '');
  };

  // ============================================================
  // NASTAVENÍ
  // ============================================================
  const updateSetting = <K extends keyof UserSettings>(key: K, value: UserSettings[K]) => {
    setUserSettings((prev) => {
      const next = { ...prev, [key]: value };
      AsyncStorage.setItem(STORAGE_KEYS.userSettings, JSON.stringify(next)).catch(() => {});
      return next;
    });
  };

  // ============================================================
  // ZÁLOŽKY (Bookmark)
  // ============================================================
  const toggleBookmark = (fileOrId: string) => {
    const norm = normalizeFile(fileOrId);
    setSavedRoutes((prev) => {
      const next = prev.includes(norm) ? prev.filter((f) => f !== norm) : [...prev, norm];
      savedRoutesRef.current = next;
      AsyncStorage.setItem(STORAGE_KEYS.savedRoutes, JSON.stringify(next)).catch(() => {});
      return next;
    });
  };

  const isBookmarked = (fileOrId: string) => {
    const norm = normalizeFile(fileOrId);
    return savedRoutesRef.current.includes(norm);
  };

  // ============================================================
  // LIKE — opravená race condition přes useRef
  // ============================================================
  const toggleLike = (fileOrId: string): boolean => {
    const norm = normalizeFile(fileOrId);
    // Okamžitý přístup k aktuálnímu stavu přes ref (není stale)
    const currentLiked = likedRoutesRef.current[norm] ?? false;
    const nextState = !currentLiked;

    // Okamžitě aktualizujeme ref
    likedRoutesRef.current = { ...likedRoutesRef.current, [norm]: nextState };

    // Pak state (async, pro re-render)
    setLikedRoutes((prev) => {
      const next = { ...prev, [norm]: nextState };
      AsyncStorage.setItem(STORAGE_KEYS.likedRoutes, JSON.stringify(next)).catch(() => {});
      return next;
    });

    return nextState;
  };

  const isLiked = (fileOrId: string): boolean => {
    const norm = normalizeFile(fileOrId);
    return likedRoutesRef.current[norm] ?? false;
  };

  // ============================================================
  // VIEWED ROUTES
  // ============================================================
  const markViewed = (id: number) => {
    setViewedRoutes((prev) => {
      if (prev.includes(id)) return prev;
      const next = [...prev, id];
      AsyncStorage.setItem(STORAGE_KEYS.viewedRoutes, JSON.stringify(next)).catch(() => {});
      return next;
    });
  };

  // ============================================================
  // PROFIL SETTERY (s persistencí)
  // ============================================================
  const setUserName = (name: string) => {
    _setUserName(name);
    AsyncStorage.setItem(STORAGE_KEYS.userName, name).catch(() => {});
  };

  const setUserBio = (bio: string) => {
    _setUserBio(bio);
    AsyncStorage.setItem(STORAGE_KEYS.userBio, bio).catch(() => {});
  };

  const setUserAvatar = (avatar: string | null) => {
    _setUserAvatar(avatar);
    if (avatar) {
      AsyncStorage.setItem(STORAGE_KEYS.userAvatar, avatar).catch(() => {});
    } else {
      AsyncStorage.removeItem(STORAGE_KEYS.userAvatar).catch(() => {});
    }
  };

  // ============================================================
  // UTILITY FUNKCE
  // ============================================================
  const t = (key: string): string => {
    const lang = userSettings.language || 'cs';
    const dict = i18n[lang] || i18n.cs;
    return (dict as Record<string, string>)[key] || key;
  };

  const formatPace = (sec: number): string => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60).toString().padStart(2, '0');
    return `${m}:${s} min/km`;
  };

  // 1:1 přepočet s korekcí algoritmu z webu
  const getAdjustedTime = (baseSeconds: number): number => {
    const pythonErrorCorrection = 0.965 / 0.75;
    return baseSeconds * pythonErrorCorrection * (userSettings.pace / 220);
  };

  const formatTime = (sec: number): string => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  return (
    <AppContext.Provider
      value={{
        isLoaded,
        userSettings,
        updateSetting,
        savedRoutes,
        toggleBookmark,
        isBookmarked,
        likedRoutes,
        toggleLike,
        isLiked,
        viewedRoutes,
        markViewed,
        appTimeMs,
        t,
        formatPace,
        getAdjustedTime,
        formatTime,
        userName,
        setUserName,
        userBio,
        setUserBio,
        userAvatar,
        setUserAvatar,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};

export const useThemeColors = () => {
  const { userSettings } = useApp();
  const systemColorScheme = useColorScheme();
  
  const isDark =
    userSettings.theme === 'dark' ||
    (userSettings.theme === 'system' && systemColorScheme === 'dark');

  return {
    isDark,
    background: isDark ? '#000000' : '#ffffff',
    text: isDark ? '#ffffff' : '#000000',
    secondaryBg: isDark ? '#111111' : '#fafafa',
    border: isDark ? '#333333' : '#dbdbdb',
    secondaryText: isDark ? '#888888' : '#737373',
    icon: isDark ? '#ffffff' : '#000000',
    modalBg: isDark ? '#1a1a1a' : '#ffffff',
    pillBg: isDark ? '#222222' : '#efefef',
    overlay: isDark ? 'rgba(0,0,0,0.7)' : 'rgba(0,0,0,0.5)',
    blue: '#0095f6',
  };
};
