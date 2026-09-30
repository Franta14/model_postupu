import React, { useState, useRef, useMemo, useEffect, useCallback } from 'react';
import {
  StyleSheet,
  Text,
  View,
  Dimensions,
  FlatList,
  TouchableOpacity,
  Pressable,
  ViewToken,
  Modal,
  TextInput,
  ScrollView,
  Share,
  PanResponder,
  Platform,
  Animated as RNAnimated,
} from 'react-native';
import { Image } from 'expo-image';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useLocalSearchParams } from 'expo-router';
import Svg, {
  Path,
  Line,
  Circle,
  Text as SvgText,
  G,
} from 'react-native-svg';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  withTiming,
  withSequence,
  withDelay,
  Easing,
  useFrameCallback,
  runOnJS,
} from 'react-native-reanimated';
import Feather from '@expo/vector-icons/Feather';

import postupyIndex from '../../../assets/postupy/postupy_index.json';
import { geojsons } from '../../../assets/postupy/geojsons';
import thumbsMetaRaw from '../../../assets/thumbs/thumbs_meta.json';
import { useFilter } from '../../context/FilterContext';
import { useApp, useThemeColors } from '../../context/AppContext';
import { collection, query, where, orderBy, onSnapshot, addDoc, serverTimestamp } from 'firebase/firestore';
import { db } from '../../config/firebase';

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');

// Kompletní podkladové mapy ve vysokém rozlišení
const MAP_CONFIG: Record<
  string,
  {
    image: any;
    width: number;
    height: number;
  }
> = {
  holna: {
    image: require('../../../assets/thumbs/map_holna_full.jpg'),
    width: 2480,
    height: 3508,
  },
  bilaskala: {
    image: require('../../../assets/thumbs/map_bilaskala_full.jpg'),
    width: 3508,
    height: 4961,
  },
  homolka: {
    image: require('../../../assets/thumbs/map_homolka_full.jpg'),
    width: 7016,
    height: 9933,
  },
};

const thumbsMeta = thumbsMetaRaw as any;
const IOF_PURPLE = '#b300ff';

// Přesná SVG grafika srdíčka (Instagram / Feather tvar 1:1)
const InstagramHeart = ({
  size = 24,
  filled = false,
  color = '#ffffff',
  fillColor = '#ff3040',
  strokeWidth = 1.75,
}: {
  size?: number;
  filled?: boolean;
  color?: string;
  fillColor?: string;
  strokeWidth?: number;
}) => (
  <Svg width={size} height={size} viewBox="0 0 24 24">
    <Path
      d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"
      fill={filled ? fillColor : 'none'}
      stroke={filled ? fillColor : color}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

// Ikonka komentáře z webu
const CommentIcon = ({ size = 24, color = '#ffffff', strokeWidth = 1.75 }: { size?: number; color?: string; strokeWidth?: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24">
    <Path
      d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"
      fill="none"
      stroke={color}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

// Ikonka sdílení (letadlo) z webu
const ShareIcon = ({ size = 24, color = '#ffffff', strokeWidth = 1.75 }: { size?: number; color?: string; strokeWidth?: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24">
    <Path
      d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"
      fill="none"
      stroke={color}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

// Ikonka záložky z webu
const BookmarkIcon = ({ size = 24, filled = false, color = '#ffffff', strokeWidth = 1.75 }: { size?: number; filled?: boolean; color?: string; strokeWidth?: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24">
    <Path
      d="M19 21l-7-5-7 5V5a2 2 0 012-2h10a2 2 0 012 2z"
      fill={filled ? color : 'none'}
      stroke={color}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </Svg>
);

interface Variant {
  id: number;
  color: string;
  vzdal_m: number;
  prevyseni_m: number;
  cas_s: number;
  tempo_str?: string;
}

interface RouteItem {
  id: number;
  map_id: string;
  map_name: string;
  terrain: string;
  file: string;
  dist_m: number;
  variants_count: number;
  variants: Variant[];
}

// ==========================================
// ==========================================
// KOMPONENTA JEDNOHO REELU
// ==========================================
function ReelItemComponent({
  item,
  isActive,
  isNear,
  onOpenComments,
  onOpenShare,
}: {
  item: RouteItem;
  isActive: boolean;
  isNear: boolean;
  onOpenComments: (route: RouteItem) => void;
  onOpenShare: (route: RouteItem) => void;
}) {
  const insets = useSafeAreaInsets();
  const { isBookmarked, toggleBookmark, isLiked, toggleLike, t, getAdjustedTime, formatTime } =
    useApp();
  const colors = useThemeColors();
  const styles = React.useMemo(() => getStyles(colors), [colors]);

  const [isOptionsOpen, setIsOptionsOpen] = useState(false);
  const [isOptionsCollapsed, setIsOptionsCollapsed] = useState(false);

  // Reanimated shared values pro animaci běžců (UI vlákno, žádný re-render)
  const animCycleMs = useSharedValue(0);
  const animStartTs = useSharedValue(-1);
  // Zrcadla JS stavů jako shared values (worklet nemůže číst JS state přímo)
  const isOptionsOpenSV = useSharedValue(false);
  const isActiveSV = useSharedValue(false);

  const basename = item.file.replace('.geojson', '').replace('.json', '');
  const routeMeta = thumbsMeta?.routes?.[basename];
  const geojsonData = (geojsons as Record<string, any>)[basename];
  const mapCfg = MAP_CONFIG[item.map_id] || MAP_CONFIG.homolka;

  // Spodní odsazení nad kompaktní 46px tab bar lištou
  const bottomNavOffset = insets.bottom > 0 ? insets.bottom + 46 + 10 : 46 + 12;

  // Reaktivní Instagram Heart animace
  const likeScale = useSharedValue(0);
  const likeOpacity = useSharedValue(0);

  const triggerLikePop = useCallback(() => {
    // Svižná Instagram animace: výbuch z 0.3 do 1.25 s elasticitou, usazení na 1.0, podržení a fade-out
    likeScale.value = 0.3;
    likeOpacity.value = 1;
    likeScale.value = withSequence(
      withTiming(1.24, { duration: 160, easing: Easing.out(Easing.back(1.6)) }),
      withTiming(1.0, { duration: 110, easing: Easing.inOut(Easing.ease) }),
      withDelay(260, withTiming(0.4, { duration: 170, easing: Easing.in(Easing.ease) }))
    );
    likeOpacity.value = withSequence(
      withTiming(1.0, { duration: 120 }),
      withDelay(410, withTiming(0, { duration: 170 }))
    );
  }, [likeScale, likeOpacity]);

  const handleLikePress = () => {
    const nextState = toggleLike(basename);
    if (nextState) {
      triggerLikePop();
    }
  };

  const animatedLikeStyle = useAnimatedStyle(() => ({
    transform: [{ scale: likeScale.value }],
    opacity: likeOpacity.value,
  }));

  // Double tap detekce pro přiblížení mapy (1.6x) nebo lajk
  const lastTapRef = useRef<number>(0);
  const [isZoomed, setIsZoomed] = useState(false);
  const zoomScale = useSharedValue(1.0);

  const handleMapDoubleTap = () => {
    const now = Date.now();
    if (now - lastTapRef.current < 320) {
      if (!isZoomed) {
        setIsZoomed(true);
        zoomScale.value = withTiming(1.6, { duration: 220, easing: Easing.out(Easing.ease) });
      } else {
        setIsZoomed(false);
        zoomScale.value = withTiming(1.0, { duration: 220, easing: Easing.out(Easing.ease) });
      }
      if (!isLiked(basename)) {
        toggleLike(basename);
        triggerLikePop();
      }
      lastTapRef.current = 0;
    } else {
      lastTapRef.current = now;
    }
  };

  // Reset zoomu při odscrollování + synchronizace isActive do shared value
  useEffect(() => {
    isActiveSV.value = isActive;
    if (!isActive) {
      setIsZoomed(false);
      zoomScale.value = 1.0;
      setIsOptionsOpen(false);
    }
  }, [isActive, zoomScale, isActiveSV]);

  // Přesný matematický výpočet geometrie, rotace a zoomu z webového rozhraní
  const routeGeometry = useMemo(() => {
    let p1_x = 0;
    let p1_y = 0;
    let p2_x = 0;
    let p2_y = 0;

    if (geojsonData && geojsonData.features) {
      geojsonData.features.forEach((f: any) => {
        if (f.properties?.type === 'start' && f.geometry?.coordinates) {
          p1_x = f.geometry.coordinates[0] * 32;
          p1_y = -f.geometry.coordinates[1] * 32;
        }
        if (f.properties?.type === 'end' && f.geometry?.coordinates) {
          p2_x = f.geometry.coordinates[0] * 32;
          p2_y = -f.geometry.coordinates[1] * 32;
        }
      });
    } else if (routeMeta) {
      p1_x = (routeMeta.start[0] / 100.0) * mapCfg.width;
      p1_y = (routeMeta.start[1] / 100.0) * mapCfg.height;
      p2_x = (routeMeta.end[0] / 100.0) * mapCfg.width;
      p2_y = (routeMeta.end[1] / 100.0) * mapCfg.height;
    }

    const dx = p2_x - p1_x;
    const dy = p2_y - p1_y;
    const dist = Math.hypot(dx, dy);

    // Výpočet rotace: směr běhu míří kolmo nahoru (Start dole, Cíl nahoře)
    const bearingRad = Math.atan2(-dx, -dy);
    const bearingDeg = (bearingRad * 180) / Math.PI;

    const midX = (p1_x + p2_x) / 2;
    const midY = (p1_y + p2_y) / 2;

    const effHeight = SCREEN_HEIGHT - insets.top - bottomNavOffset;
    const targetHeight = Math.min(SCREEN_HEIGHT * 0.62, effHeight * 0.78);
    const scale = dist > 0 ? targetHeight / dist : 0.5;

    const screenMidX = SCREEN_WIDTH / 2;
    const screenMidY = insets.top + effHeight / 2;

    const mapResRatio = mapCfg.width / 3200;
    const R = Math.max(24 * mapResRatio, Math.min(55 * mapResRatio, 32 * mapResRatio));
    const strokeW = Math.max(3.2 * mapResRatio, R / 8);
    const gap = strokeW * 1.5;

    let sx = p1_x;
    let sy = p1_y;
    let ex = p2_x;
    let ey = p2_y;

    if (dist > (R + gap) * 2) {
      const ux = dx / dist;
      const uy = dy / dist;
      sx = p1_x + ux * (R + gap);
      sy = p1_y + uy * (R + gap);
      ex = p2_x - ux * (R + gap);
      ey = p2_y - uy * (R + gap);
    }

    // Umístění čísel 1 a 2 NALEVO od kruhů (kolmo ke směru běhu)
    const ux = dist > 0 ? dx / dist : 0;
    const uy = dist > 0 ? dy / dist : -1;
    const nx = uy;
    const ny = -ux;
    const textDist = R + 18 * mapResRatio;

    const c1_x = p1_x + nx * textDist;
    const c1_y = p1_y + ny * textDist;
    const c2_x = p2_x + nx * textDist;
    const c2_y = p2_y + ny * textDist;
    const fontSize = Math.round(28 * mapResRatio);

    // Inteligetní pozicování panelu variant (identické s webem)
    let panelCorner: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right' = 'top-right';
    if (geojsonData && geojsonData.features && dist > 0) {
      const ux2 = dx / dist;
      const uy2 = dy / dist;
      const vx2 = -uy2;
      const vy2 = ux2;
      let maxBulgeTopLeft = 0, maxBulgeTopRight = 0, maxBulgeBottomLeft = 0;
      geojsonData.features.forEach((f: any) => {
        if (f.properties?.type === 'variant' && f.geometry?.type === 'LineString') {
          f.geometry.coordinates.forEach((c: number[]) => {
            const px2 = c[0] * 32 - midX;
            const py2 = -c[1] * 32 - midY;
            const localY = px2 * ux2 + py2 * uy2;
            const localX = px2 * vx2 + py2 * vy2;
            if (localY > dist * 0.6) {
              if (localX > maxBulgeTopLeft) maxBulgeTopLeft = localX;
              if (-localX > maxBulgeTopRight) maxBulgeTopRight = -localX;
            } else if (localY < dist * 0.4) {
              if (localX > maxBulgeBottomLeft) maxBulgeBottomLeft = localX;
            }
          });
        }
      });
      const corners = [
        { corner: 'top-left' as const, val: maxBulgeTopLeft },
        { corner: 'top-right' as const, val: maxBulgeTopRight },
        { corner: 'bottom-left' as const, val: maxBulgeBottomLeft },
      ];
      corners.sort((a, b) => a.val - b.val);
      panelCorner = corners[0].corner;
    }

    return {
      p1_x,
      p1_y,
      p2_x,
      p2_y,
      dist,
      bearingDeg,
      midX,
      midY,
      scale,
      screenMidX,
      screenMidY,
      R,
      strokeW,
      sx,
      sy,
      ex,
      ey,
      c1_x,
      c1_y,
      c2_x,
      c2_y,
      fontSize,
      mapCfg,
      panelCorner,
    };
  }, [geojsonData, routeMeta, mapCfg, insets, bottomNavOffset]);

  // Převod linií variant na souřadnice mapy
  const variantData = useMemo(() => {
    if (!geojsonData || !geojsonData.features) return [];
    const list: Array<{
      id: number;
      color: string;
      coords: number[][];
      cumDists: number[];
      totalDist: number;
      vDuration: number;
      pathString: string;
    }> = [];

    const sc_x = routeGeometry.p1_x;
    const sc_y = routeGeometry.p1_y;

    const BASE_DURATION = 1600;
    const minTime = Math.min(...(item.variants?.map((v) => v.cas_s) || [100]));

    geojsonData.features.forEach((f: any) => {
      if (f.properties?.type === 'variant' && f.geometry?.type === 'LineString') {
        const vInfo = item.variants?.find((v) => v.id === f.properties.id);
        const color = vInfo?.color || f.properties.color || '#ff4444';
        const raw = f.geometry.coordinates;
        if (!raw || raw.length < 2) return;

        const pts = raw.map((c: number[]) => [c[0] * 32, -c[1] * 32]);

        const d0 = Math.hypot(pts[0][0] - sc_x, pts[0][1] - sc_y);
        const dEnd = Math.hypot(pts[pts.length - 1][0] - sc_x, pts[pts.length - 1][1] - sc_y);
        const ordered = dEnd < d0 ? pts.slice().reverse() : pts.slice();

        const cumDists = [0];
        let total = 0;
        for (let j = 0; j < ordered.length - 1; j++) {
          const segDist = Math.hypot(
            ordered[j + 1][0] - ordered[j][0],
            ordered[j + 1][1] - ordered[j][1]
          );
          total += segDist;
          cumDists.push(total);
        }

        let pathString = `M ${ordered[0][0]} ${ordered[0][1]}`;
        for (let j = 1; j < ordered.length; j++) {
          pathString += ` L ${ordered[j][0]} ${ordered[j][1]}`;
        }

        const vTime = vInfo?.cas_s || minTime || 100;
        const ratio = minTime > 0 ? vTime / minTime : 1.0;
        const vDuration = Math.min(2600, Math.max(1200, Math.round(BASE_DURATION * ratio)));

        list.push({
          id: f.properties.id,
          color,
          coords: ordered,
          cumDists,
          totalDist: total,
          vDuration,
          pathString,
        });
      }
    });

    return list;
  }, [geojsonData, item.variants, routeGeometry]);

  // Synchronizace isOptionsOpen do shared value
  useEffect(() => {
    isOptionsOpenSV.value = isOptionsOpen;
  }, [isOptionsOpen, isOptionsOpenSV]);

  // Animace běžců — useFrameCallback běží pouze když jsou Volby otevřené a reel je aktivní
  const isRunning = isOptionsOpen && isActive;
  const frameCallback = useFrameCallback((frameInfo) => {
    if (animStartTs.value < 0) {
      animStartTs.value = frameInfo.timestamp;
    }
    const elapsed = frameInfo.timestamp - animStartTs.value;
    animCycleMs.value = elapsed % 3400;
  }, false);

  useEffect(() => {
    frameCallback.setActive(isRunning);
    if (!isRunning) {
      animCycleMs.value = 0;
      animStartTs.value = -1;
    }
  }, [isRunning, frameCallback]);

  // JS-side helper pro výpočet pozice běžce (používáme jen při renderu)
  const getRunnerPosition = (v: (typeof variantData)[0], elapsedMs: number) => {
    if (v.totalDist <= 0 || v.coords.length < 2) return v.coords[0];
    const progress = Math.min(1.0, elapsedMs / v.vDuration);
    const targetDist = progress * v.totalDist;

    for (let j = 0; j < v.cumDists.length - 1; j++) {
      if (targetDist <= v.cumDists[j + 1]) {
        const segStartDist = v.cumDists[j];
        const segEndDist = v.cumDists[j + 1];
        const segSpan = segEndDist - segStartDist || 1;
        const frac = (targetDist - segStartDist) / segSpan;
        const rx = v.coords[j][0] + (v.coords[j + 1][0] - v.coords[j][0]) * frac;
        const ry = v.coords[j][1] + (v.coords[j + 1][1] - v.coords[j][1]) * frac;
        return [rx, ry];
      }
    }
    return v.coords[v.coords.length - 1];
  };

  const animatedMapStyle = useAnimatedStyle(() => ({
    transform: [
      { translateX: routeGeometry.screenMidX - routeGeometry.mapCfg.width / 2 },
      { translateY: routeGeometry.screenMidY - routeGeometry.mapCfg.height / 2 },
      { scale: routeGeometry.scale * zoomScale.value },
      { rotate: `${routeGeometry.bearingDeg}deg` },
      { translateX: routeGeometry.mapCfg.width / 2 - routeGeometry.midX },
      { translateY: routeGeometry.mapCfg.height / 2 - routeGeometry.midY },
    ],
  }));

  const bookmarked = isBookmarked(basename);
  const liked = isLiked(basename);

  // KRITICKÁ OPTIMALIZACE PAMĚTI:
  // Pokud položka není v bezprostřední blízkosti aktivní obrazovky (isNear === false),
  // vůbec nemontujeme bitmapu mapy ani SVG do nativního stromu.
  if (!isNear) {
    return <View style={styles.reelContainer} />;
  }

  return (
    <View style={styles.reelContainer}>
      {/* ── MAPOVÉ PLÁTNO A VEKTORY ── */}
      <Pressable onPress={handleMapDoubleTap} style={styles.mapTouchArea}>
        <View style={styles.mapViewport}>
          <Animated.View
            style={[
              {
                width: routeGeometry.mapCfg.width,
                height: routeGeometry.mapCfg.height,
                position: 'absolute',
                top: 0,
                left: 0,
              },
              animatedMapStyle,
            ]}
          >
            {/* 1. Podkladová orienťácká mapa (expo-image s hardware poolingem a okamžitým uvolňováním paměti) */}
            <Image
              source={routeGeometry.mapCfg.image}
              style={{
                width: routeGeometry.mapCfg.width,
                height: routeGeometry.mapCfg.height,
                position: 'absolute',
              }}
              contentFit="cover"
              cachePolicy="memory-disk"
              recyclingKey={`map-${item.map_id}`}
            />

            {/* 2. Vektorový SVG overlay */}
            <Svg
              width={routeGeometry.mapCfg.width}
              height={routeGeometry.mapCfg.height}
              viewBox={`0 0 ${routeGeometry.mapCfg.width} ${routeGeometry.mapCfg.height}`}
              style={styles.svgAbsolute}
            >
              {/* Spojnice kontrol */}
              {routeGeometry.dist > (routeGeometry.R + routeGeometry.strokeW) * 2 && (
                <Line
                  x1={routeGeometry.sx}
                  y1={routeGeometry.sy}
                  x2={routeGeometry.ex}
                  y2={routeGeometry.ey}
                  stroke={IOF_PURPLE}
                  strokeWidth={routeGeometry.strokeW}
                  strokeOpacity={0.88}
                  strokeLinecap="round"
                />
              )}

              {/* Startovní kolečko (1) */}
              <Circle
                cx={routeGeometry.p1_x}
                cy={routeGeometry.p1_y}
                r={routeGeometry.R}
                stroke={IOF_PURPLE}
                strokeWidth={routeGeometry.strokeW}
                fill="none"
              />

              {/* Cílové kolečko (2) */}
              <Circle
                cx={routeGeometry.p2_x}
                cy={routeGeometry.p2_y}
                r={routeGeometry.R}
                stroke={IOF_PURPLE}
                strokeWidth={routeGeometry.strokeW}
                fill="none"
              />

              {/* Číslo kontroly 1 (nalevo od kruhu, nerotuje se spolu s mapou) */}
              <G
                transform={`rotate(${-routeGeometry.bearingDeg}, ${routeGeometry.c1_x}, ${routeGeometry.c1_y})`}
              >
                <SvgText
                  x={routeGeometry.c1_x}
                  y={routeGeometry.c1_y + routeGeometry.fontSize * 0.35}
                  fill={IOF_PURPLE}
                  fontSize={routeGeometry.fontSize}
                  fontWeight="bold"
                  fontFamily="Arial, sans-serif"
                  textAnchor="middle"
                >
                  1
                </SvgText>
              </G>

              {/* Číslo kontroly 2 (nalevo od kruhu, nerotuje se spolu s mapou) */}
              <G
                transform={`rotate(${-routeGeometry.bearingDeg}, ${routeGeometry.c2_x}, ${routeGeometry.c2_y})`}
              >
                <SvgText
                  x={routeGeometry.c2_x}
                  y={routeGeometry.c2_y + routeGeometry.fontSize * 0.35}
                  fill={IOF_PURPLE}
                  fontSize={routeGeometry.fontSize}
                  fontWeight="bold"
                  fontFamily="Arial, sans-serif"
                  textAnchor="middle"
                >
                  2
                </SvgText>
              </G>

              {/* Statické trajektorie variant (zobrazeny okamžitě po otevření Voleb) */}
              {isOptionsOpen &&
                variantData.map((v) => (
                  <Path
                    key={`path-${v.id}`}
                    d={v.pathString}
                    stroke={v.color}
                    strokeWidth={routeGeometry.strokeW * 1.15}
                    strokeOpacity={0.88}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    fill="none"
                  />
                ))}

              {/* Animované body běžců — pozice čtena ze shared value, rendrováno přes JS bridge */}
              {isOptionsOpen &&
                variantData.map((v) => {
                  const pos = getRunnerPosition(v, animCycleMs.value);
                  if (!pos) return null;
                  return (
                    <Circle
                      key={`runner-${v.id}`}
                      cx={pos[0]}
                      cy={pos[1]}
                      r={routeGeometry.R * 0.28}
                      fill={v.color}
                      stroke="#ffffff"
                      strokeWidth={routeGeometry.strokeW * 0.45}
                    />
                  );
                })}
            </Svg>
          </Animated.View>
        </View>
      </Pressable>

      {/* ── VELKÉ ČERVENÉ LIKE SRDCE UPROSTŘED (Instagram styl) ── */}
      <Animated.View
        pointerEvents="none"
        style={[styles.bigHeartContainer, animatedLikeStyle]}
      >
        <InstagramHeart size={105} filled={true} fillColor="#ff3040" color="#ffffff" strokeWidth={1} />
      </Animated.View>

      {/* ── PLOVOUCÍ AKČNÍ LIŠTA NA PRAVÉ STRANĚ (Čisté bílé SVG ikonky, okamžitá odezva) ── */}
      <View style={[styles.actionBar, { bottom: bottomNavOffset + 48 }]}>
        {/* Like */}
        <TouchableOpacity
          activeOpacity={0.5}
          style={styles.actionBtn}
          onPress={handleLikePress}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          <View style={styles.actionIconWrapper}>
            <InstagramHeart
              size={28}
              filled={liked}
              color="#ffffff"
              fillColor="#ff3040"
              strokeWidth={1.8}
            />
          </View>
        </TouchableOpacity>

        {/* Komentáře */}
        <TouchableOpacity
          activeOpacity={0.5}
          style={styles.actionBtn}
          onPress={() => onOpenComments(item)}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          <View style={styles.actionIconWrapper}>
            <CommentIcon size={26} color="#ffffff" strokeWidth={1.75} />
          </View>
        </TouchableOpacity>

        {/* Sdílet */}
        <TouchableOpacity
          activeOpacity={0.5}
          style={styles.actionBtn}
          onPress={() => onOpenShare(item)}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          <View style={styles.actionIconWrapper}>
            <ShareIcon size={25} color="#ffffff" strokeWidth={1.75} />
          </View>
        </TouchableOpacity>

        {/* Záložka / Uložit */}
        <TouchableOpacity
          activeOpacity={0.5}
          style={styles.actionBtn}
          onPress={() => toggleBookmark(basename)}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          <View style={styles.actionIconWrapper}>
            <BookmarkIcon size={27} filled={bookmarked} color="#ffffff" strokeWidth={1.75} />
          </View>
        </TouchableOpacity>
      </View>

      {/* ── SPODNÍ LIŠTA: VZDUŠNÁ VZDÁLENOST A TLAČÍTKO "VOLBY" ── */}
      <View style={[styles.bottomInfoBar, { bottom: bottomNavOffset }]}>
        {/* Čistý text přímo na mapě (1:1 s webem) */}
        <Text style={styles.aerialText}>
          {item.dist_m ? Math.round(item.dist_m) : ''} {t('aerial')}
        </Text>

        {/* Tlačítko "Volby" - čisté bílé */}
        <TouchableOpacity
          activeOpacity={0.65}
          style={styles.optionsBtn}
          onPress={() => setIsOptionsOpen((prev) => !prev)}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          <Feather name="menu" size={15} color="#000000" style={{ marginRight: 6 }} />
          <Text style={styles.optionsBtnText}>{t('options')}</Text>
        </TouchableOpacity>
      </View>

      {/* ── PLOVOUCÍ PANEL VARIANT — Inteligentní pozicování (port z webu) ── */}
      {isOptionsOpen && (() => {
        const corner = routeGeometry.panelCorner || 'top-right';
        const isTop = !corner.includes('bottom');
        const isRight = !corner.includes('left');
        const panelDynStyle = [
          styles.variantsPanel,
          isTop
            ? { top: insets.top + 8 }
            : { bottom: bottomNavOffset + 56, top: undefined },
          isRight
            ? { right: 12 }
            : { left: 12, right: undefined },
        ];
        return (
          <View style={panelDynStyle}>
            <TouchableOpacity
              onPress={() => setIsOptionsCollapsed((prev) => !prev)}
              style={styles.collapseBtn}
              activeOpacity={0.6}
              hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
            >
              <Feather
                name={isOptionsCollapsed ? 'chevron-down' : 'chevron-up'}
                size={22}
                color="#ffffff"
                style={styles.collapseIconShadow}
              />
            </TouchableOpacity>

            {!isOptionsCollapsed && (
              <View style={styles.variantsList}>
                {item.variants?.map((v) => {
                  const adjTimeS = getAdjustedTime(v.cas_s);
                  const adjTimeStr = formatTime(adjTimeS);
                  const adjPaceS = (adjTimeS / (v.vzdal_m || 1000)) * 1000;
                  const adjPaceStr = `${formatTime(adjPaceS)} min/km`;

                  return (
                    <View key={`var-row-${v.id}`} style={styles.variantItem}>
                      <View style={[styles.variantDot, { backgroundColor: v.color }]} />
                      <View style={styles.variantStats}>
                        <Text style={styles.variantMain}>
                          V{v.id} • {adjTimeStr}
                        </Text>
                        <Text style={styles.variantSub}>
                          {Math.round(v.vzdal_m)}m • {Math.round(v.prevyseni_m)}m↑
                        </Text>
                        <Text style={styles.variantSub}>{adjPaceStr}</Text>
                      </View>
                    </View>
                  );
                })}
              </View>
            )}
          </View>
        );
      })()}

    </View>
  );
}

const ReelItem = React.memo(ReelItemComponent, (prev, next) => {
  return (
    prev.item.id === next.item.id &&
    prev.isActive === next.isActive &&
    prev.isNear === next.isNear
  );
});

// ==========================================
// BOTTOM SHEET (Komentáře, Instagram styl)
// Plně UI-thread animace přes Reanimated + GestureDetector
// ==========================================
import { GestureDetector, Gesture } from 'react-native-gesture-handler';

const SHEET_HEIGHT = SCREEN_HEIGHT * 0.65;

const CommentsBottomSheet = ({
  visible,
  onClose,
  commentsList,
  commentText,
  setCommentText,
  handleAddComment,
}: {
  visible: boolean;
  onClose: () => void;
  commentsList: Array<{ id: string; author: string; text: string; time: string }>;
  commentText: string;
  setCommentText: (t: string) => void;
  handleAddComment: () => void;
}) => {
  const colors = useThemeColors();
  const styles = React.useMemo(() => getStyles(colors), [colors]);
  const translateY = useSharedValue(SHEET_HEIGHT);
  const backdropOpacity = useSharedValue(0);
  const [mounted, setMounted] = useState(false);
  const insets = useSafeAreaInsets();

  // Otevři / zavři animaci
  useEffect(() => {
    if (visible) {
      setMounted(true);
      translateY.value = withSpring(0, {
        damping: 28,
        stiffness: 300,
        mass: 0.8,
      });
      backdropOpacity.value = withTiming(1, { duration: 220 });
    } else if (mounted) {
      translateY.value = withTiming(SHEET_HEIGHT, {
        duration: 240,
        easing: Easing.out(Easing.ease),
      });
      backdropOpacity.value = withTiming(0, { duration: 220 });
      const timer = setTimeout(() => setMounted(false), 260);
      return () => clearTimeout(timer);
    }
  }, [visible]);

  // Pan gesture — UI vlákno (60fps, bez JS bridge)
  const startY = useSharedValue(0);
  const panGesture = Gesture.Pan()
    .onBegin(() => {
      startY.value = translateY.value;
    })
    .onUpdate((e) => {
      const newY = startY.value + e.translationY;
      // Povolíme jen posun dolů, odolnost při tahu nahoru
      translateY.value = newY > 0 ? newY : newY * 0.12;
      backdropOpacity.value = Math.max(0, 1 - newY / SHEET_HEIGHT);
    })
    .onEnd((e) => {
      // Dismiss: velké posunutí nebo rychlý swipe dolů
      if (e.translationY > 100 || e.velocityY > 600) {
        translateY.value = withTiming(SHEET_HEIGHT, {
          duration: 240,
          easing: Easing.out(Easing.ease),
        });
        backdropOpacity.value = withTiming(0, { duration: 220 });
        runOnJS(onClose)();
      } else {
        // Snap zpět
        translateY.value = withSpring(0, { damping: 28, stiffness: 300, mass: 0.8 });
        backdropOpacity.value = withTiming(1, { duration: 150 });
      }
    });

  const sheetStyle = useAnimatedStyle(() => ({
    transform: [{ translateY: translateY.value }],
  }));
  const backdropStyle = useAnimatedStyle(() => ({
    opacity: backdropOpacity.value,
  }));

  if (!mounted) return null;

  return (
    <Modal visible={mounted} transparent animationType="none" onRequestClose={onClose}>
      {/* Tmavý backdrop — opacity navázána na pozici sheetu */}
      <Animated.View style={[styles.modalOverlay, backdropStyle]} pointerEvents="box-none">
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} />
      </Animated.View>

      {/* Sheet */}
      <GestureDetector gesture={panGesture}>
        <Animated.View
          style={[
            styles.sheetContainer,
            { paddingBottom: insets.bottom },
            sheetStyle,
          ]}
        >
          {/* Handle + hlavička — draggable */}
          <View style={styles.sheetHeaderArea}>
            <View style={styles.sheetHandle} />
            <Text style={styles.sheetTitle}>Komentáře</Text>
          </View>

          <ScrollView
            style={styles.sheetCommentsList}
            keyboardShouldPersistTaps="handled"
            // Zabráníme konfliktu scrollu a pan gestu
            scrollEventThrottle={16}
          >
            {commentsList.map((c) => (
              <View key={c.id} style={styles.commentItem}>
                <View style={styles.commentAvatar}>
                  <Feather name="user" size={16} color="#ffffff" />
                </View>
                <View style={styles.commentContent}>
                  <Text style={styles.commentAuthor}>
                    {c.author} <Text style={styles.commentTime}>{c.time}</Text>
                  </Text>
                  <Text style={styles.commentText}>{c.text}</Text>
                </View>
              </View>
            ))}
          </ScrollView>

          <View style={styles.sheetInputRow}>
            <TextInput
              style={styles.commentInput}
              placeholder="Přidat komentář..."
              placeholderTextColor="#888888"
              value={commentText}
              onChangeText={setCommentText}
            />
            <TouchableOpacity style={styles.sendCommentBtn} onPress={handleAddComment}>
              <Feather name="send" size={16} color="#ffffff" />
            </TouchableOpacity>
          </View>
        </Animated.View>
      </GestureDetector>
    </Modal>
  );
};


// ==========================================
// HLAVNÍ REELS SCREEN
// ==========================================
export default function ReelsScreen() {
  const { map } = useLocalSearchParams<{ map?: string }>();
  const { selectedTerrains } = useFilter();
  const { markViewed, userName } = useApp();
  const colors = useThemeColors();
  const styles = React.useMemo(() => getStyles(colors), [colors]);

  const [activeIndex, setActiveIndex] = useState(0);
  const [commentsRoute, setCommentsRoute] = useState<RouteItem | null>(null);
  const [commentText, setCommentText] = useState('');
  const [commentsList, setCommentsList] = useState<
    Array<{ id: string; author: string; text: string; time: string }>
  >([]);

  // Real-time načítání komentářů pro otevřený postup
  useEffect(() => {
    if (!commentsRoute) {
      setCommentsList([]);
      return;
    }
    
    const basename = commentsRoute.file.replace('.geojson', '').replace('.json', '');
    const q = query(
      collection(db, 'comments'),
      where('routeId', '==', basename),
      orderBy('timestamp', 'asc')
    );

    const unsubscribe = onSnapshot(q, (snapshot) => {
      const newComments: any[] = [];
      snapshot.forEach((doc) => {
        const data = doc.data();
        let timeStr = 'Teď';
        if (data.timestamp) {
          const seconds = data.timestamp.seconds || data.timestamp._seconds;
          if (seconds) {
             const diff = Math.floor(Date.now() / 1000) - seconds;
             if (diff < 60) timeStr = 'Teď';
             else if (diff < 3600) timeStr = `${Math.floor(diff / 60)}m`;
             else if (diff < 86400) timeStr = `${Math.floor(diff / 3600)}h`;
             else timeStr = `${Math.floor(diff / 86400)}d`;
          }
        }
        newComments.push({
          id: doc.id,
          author: data.author || 'Neznámý',
          text: data.text || '',
          time: timeStr,
        });
      });
      setCommentsList(newComments);
    }, (error) => {
      console.warn("Chyba při načítání komentářů:", error);
    });

    return () => unsubscribe();
  }, [commentsRoute]);

  // Filtrování postupů podle vybrané mapy nebo filtrů terénu
  const displayRoutes = useMemo(() => {
    let routes = postupyIndex as RouteItem[];
    if (map) {
      routes = routes.filter((r) => r.map_id === map);
    } else if (selectedTerrains.length > 0) {
      routes = routes.filter((r) => selectedTerrains.includes(r.terrain));
    }
    return routes;
  }, [map, selectedTerrains]);

  const displayRoutesRef = useRef(displayRoutes);
  useEffect(() => {
    displayRoutesRef.current = displayRoutes;
  }, [displayRoutes]);

  const onViewableItemsChanged = useRef(
    ({ viewableItems }: { viewableItems: ViewToken[] }) => {
      if (viewableItems.length > 0 && viewableItems[0].index !== null && viewableItems[0].index !== undefined) {
        const idx = viewableItems[0].index;
        setActiveIndex(idx);
        const currentRoute = displayRoutesRef.current[idx];
        if (currentRoute) {
          markViewed(currentRoute.id);
        }
      }
    }
  ).current;

  const viewabilityConfig = useRef({
    itemVisiblePercentThreshold: 60,
  }).current;

  const handleOpenComments = useCallback((route: RouteItem) => {
    setCommentsRoute(route);
  }, []);

  const handleOpenShare = useCallback(async (route: RouteItem) => {
    try {
      await Share.share({
        message: `Koukni na tento orienťácký postup: ${route.map_name} (${Math.round(
          route.dist_m
        )}m vzdušně)!`,
      });
    } catch (e) {
      // Ignorovat
    }
  }, []);

  const handleAddComment = async () => {
    if (!commentText.trim() || !commentsRoute) return;
    const basename = commentsRoute.file.replace('.geojson', '').replace('.json', '');
    const currentText = commentText;
    setCommentText(''); // Optimistické vymazání vstupu
    
    try {
      await addDoc(collection(db, 'comments'), {
        routeId: basename,
        author: userName || 'Anonym',
        text: currentText.trim(),
        timestamp: serverTimestamp(),
      });
    } catch (e) {
      console.warn('Error adding comment:', e);
      setCommentText(currentText); // Vrácení textu při chybě
    }
  };

  const getItemLayout = useCallback(
    (_: any, index: number) => ({
      length: SCREEN_HEIGHT,
      offset: SCREEN_HEIGHT * index,
      index,
    }),
    []
  );

  const renderItem = useCallback(
    ({ item, index }: { item: RouteItem; index: number }) => {
      const isNear = Math.abs(index - activeIndex) <= 1;
      return (
        <ReelItem
          item={item}
          isActive={index === activeIndex}
          isNear={isNear}
          onOpenComments={handleOpenComments}
          onOpenShare={handleOpenShare}
        />
      );
    },
    [activeIndex, handleOpenComments, handleOpenShare]
  );

  return (
    <View style={styles.container}>
      <FlatList
        data={displayRoutes}
        keyExtractor={(item) => item.file}
        renderItem={renderItem}
        getItemLayout={getItemLayout}
        pagingEnabled
        snapToInterval={SCREEN_HEIGHT}
        snapToAlignment="start"
        decelerationRate="fast"
        showsVerticalScrollIndicator={false}
        onViewableItemsChanged={onViewableItemsChanged}
        viewabilityConfig={viewabilityConfig}
        initialNumToRender={1}
        maxToRenderPerBatch={2}
        windowSize={3}
        removeClippedSubviews={Platform.OS === 'android'}
      />

      {/* SPODNÍ SHEET PRO KOMENTÁŘE */}
      <CommentsBottomSheet
        visible={!!commentsRoute}
        onClose={() => setCommentsRoute(null)}
        commentsList={commentsList}
        commentText={commentText}
        setCommentText={setCommentText}
        handleAddComment={handleAddComment}
      />
    </View>
  );
}

// ==========================================
// STYLY
// ==========================================
const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000000', // Reels background always black
  },
  reelContainer: {
    width: SCREEN_WIDTH,
    height: SCREEN_HEIGHT,
    position: 'relative',
    backgroundColor: '#000000',
    overflow: 'hidden',
  },
  mapTouchArea: {
    width: '100%',
    height: '100%',
  },
  mapViewport: {
    width: '100%',
    height: '100%',
    overflow: 'hidden',
    backgroundColor: '#ffffff',
  },
  svgAbsolute: {
    position: 'absolute',
    top: 0,
    left: 0,
  },
  bigHeartContainer: {
    position: 'absolute',
    top: '42%',
    left: '50%',
    marginLeft: -52,
    marginTop: -52,
    zIndex: 999,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.5,
    shadowRadius: 10,
    elevation: 10,
  },
  actionBar: {
    position: 'absolute',
    right: 12,
    alignItems: 'center',
    gap: 16,
    zIndex: 100,
  },
  actionBtn: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  actionIconWrapper: {
    width: 32,
    height: 32,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1.5 },
    shadowOpacity: 0.85,
    shadowRadius: 3.5,
    elevation: 6,
  },
  bottomInfoBar: {
    position: 'absolute',
    left: 14,
    right: 14,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    zIndex: 100,
  },
  aerialText: {
    color: '#000000',
    fontSize: 13,
    fontWeight: '500',
    textShadowColor: 'rgba(255, 255, 255, 0.95)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 3,
  },
  optionsBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#ffffff',
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#d0d0d0',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.15,
    shadowRadius: 2.5,
    elevation: 2,
  },
  optionsBtnText: {
    color: '#000000',
    fontSize: 13,
    fontWeight: '600',
  },
  variantsPanel: {
    position: 'absolute',
    right: 14,
    alignItems: 'flex-end',
    zIndex: 200,
  },
  collapseBtn: {
    padding: 4,
    alignSelf: 'flex-end',
    marginBottom: 4,
  },
  collapseIconShadow: {
    textShadowColor: 'rgba(0, 0, 0, 0.85)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 3,
  },
  variantsList: {
    flexDirection: 'column',
    alignItems: 'flex-start',
    gap: 8,
  },
  variantItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  variantDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 7,
    marginTop: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.8,
    shadowRadius: 2,
    elevation: 2,
  },
  variantStats: {
    flexDirection: 'column',
  },
  variantMain: {
    color: '#ffffff',
    fontSize: 13,
    fontWeight: '700',
    textShadowColor: 'rgba(0, 0, 0, 0.95)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 3,
  },
  variantSub: {
    color: 'rgba(255, 255, 255, 0.95)',
    fontSize: 11,
    fontWeight: '600',
    lineHeight: 14,
    textShadowColor: 'rgba(0, 0, 0, 0.95)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 3,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  sheetContainer: {
    height: SCREEN_HEIGHT * 0.65,
    backgroundColor: colors.modalBg,
    borderTopLeftRadius: 18,
    borderTopRightRadius: 18,
    paddingHorizontal: 16,
    paddingBottom: 24,
  },
  sheetHeaderArea: {
    backgroundColor: 'transparent',
    paddingTop: 12,
    paddingBottom: 8,
  },
  sheetHandle: {
    width: 40,
    height: 4,
    backgroundColor: 'rgba(255,255,255,0.3)',
    borderRadius: 2,
    alignSelf: 'center',
    marginBottom: 12,
  },
  sheetTitle: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: 16,
  },
  sheetCommentsList: {
    flex: 1,
  },
  commentItem: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 16,
  },
  commentAvatar: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.secondaryBg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  commentContent: {
    flex: 1,
  },
  commentAuthor: {
    color: colors.text,
    fontSize: 13,
    fontWeight: '700',
    marginBottom: 2,
  },
  commentTime: {
    color: colors.secondaryText,
    fontSize: 11,
    fontWeight: '400',
  },
  commentText: {
    color: colors.text,
    fontSize: 13,
    lineHeight: 18,
  },
  sheetInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    borderTopWidth: 0.5,
    borderTopColor: colors.border,
    paddingTop: 12,
  },
  commentInput: {
    flex: 1,
    backgroundColor: colors.secondaryBg,
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    color: colors.text,
    fontSize: 14,
  },
  sendCommentBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: '#0095f6',
    alignItems: 'center',
    justifyContent: 'center',
  },
});
