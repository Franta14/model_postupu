import React, { useMemo, useEffect } from 'react';
import {
  StyleSheet,
  Text,
  View,
  FlatList,
  Dimensions,
  TouchableOpacity,
  ScrollView,
  Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withRepeat,
  withTiming,
  withSequence,
  Easing,
} from 'react-native-reanimated';
import { LinearGradient } from 'expo-linear-gradient';
import { useFilter } from '../../context/FilterContext';
import { useApp, useThemeColors } from '../../context/AppContext';

// Načteme skutečná data o postupech
import postupyIndex from '../../../assets/postupy/postupy_index.json';

const { width } = Dimensions.get('window');
const COLUMN_COUNT = 3;
const SPACING = 2;
const TILE_WIDTH = (width - (COLUMN_COUNT - 1) * SPACING) / COLUMN_COUNT;
const TILE_HEIGHT = TILE_WIDTH * (5 / 4); // 4:5 aspect ratio

// Lokální náhledy map
const MAP_THUMBS: Record<string, any> = {
  holna: require('../../../assets/thumbs/map_holna.jpg'),
  bilaskala: require('../../../assets/thumbs/map_bilaskala.jpg'),
  homolka: require('../../../assets/thumbs/map_homolka.jpg'),
};

const STORIES = [
  {
    id: '1',
    terrain: 'cesko',
    title: 'Česko',
    img: require('../../../assets/thumbs/map_holna.jpg'),
    isLocal: true,
  },
  {
    id: '2',
    terrain: 'skandinavie',
    title: 'Skandinávie',
    img: 'https://upload.wikimedia.org/wikipedia/commons/thumb/3/3d/Forest_in_Sweden.jpg/800px-Forest_in_Sweden.jpg',
    isLocal: false,
  },
  {
    id: '3',
    terrain: 'madarsko',
    title: 'Maďarsko',
    img: 'https://upload.wikimedia.org/wikipedia/commons/thumb/d/d4/B%C3%BCkk_National_Park.jpg/800px-B%C3%BCkk_National_Park.jpg',
    isLocal: false,
  },
  {
    id: '4',
    terrain: 'piskovce',
    title: 'Pískovce',
    img: 'https://upload.wikimedia.org/wikipedia/commons/thumb/4/4b/Pravcicka_brana.jpg/800px-Pravcicka_brana.jpg',
    isLocal: false,
  },
  {
    id: '5',
    terrain: 'alpy',
    title: 'Alpy',
    img: 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/60/Matterhorn_from_Domh%C3%BCtte_-_2.jpg/800px-Matterhorn_from_Domh%C3%BCtte_-_2.jpg',
    isLocal: false,
  },
  {
    id: '6',
    terrain: 'mesto',
    title: 'Město',
    img: 'https://upload.wikimedia.org/wikipedia/commons/thumb/d/da/Prague_Old_Town_Square.jpg/800px-Prague_Old_Town_Square.jpg',
    isLocal: false,
  },
];

const getRoutesCountText = (count: number) => {
  if (count === 1) return '1 postup';
  if (count >= 2 && count <= 4) return `${count} postupy`;
  return `${count} postupů`;
};

// Komponenta pro dlaždici s 4-bodovou Ken Burns animací (70s cyklus, identicky s webem)
function DriftingTile({ item, index, onPress }: { item: any; index: number; onPress: () => void }) {
  const thumb = MAP_THUMBS[item.map_id];
  const colors = useThemeColors();
  const styles = React.useMemo(() => getStyles(colors), [colors]);

  const translateX = useSharedValue(0);
  const translateY = useSharedValue(0);

  useEffect(() => {
    // 4 body pohybu s různým časováním pro každou dłaždici (identicky s web @keyframes mapDrift)
    // Faze posun závisí na indexu — dłaždice se nehybou synchronně
    const phase = (index * 0.37) % 1.0; // 0–1
    const cycleDur = 70000; // 70s identicky s webem
    const segDur = cycleDur / 4; // každý segment ~17.5s

    // X osa: 4-bodový pohyb s proměnným směrem
    const xPoints = [0, -14, -6, -18, 0];
    // Y osa: 4-bodový pohyb ortogonálně k X
    const yPoints = [0, -8, -16, -4, 0];

    // Posuneme startovní bod podle phase
    const pIdx = Math.floor(phase * 4);
    const xShifted = [...xPoints.slice(pIdx), ...xPoints.slice(1, pIdx + 1)];
    const yShifted = [...yPoints.slice(pIdx), ...yPoints.slice(1, pIdx + 1)];

    const ease = Easing.inOut(Easing.ease);

    translateX.value = withRepeat(
      withSequence(
        withTiming(xShifted[1], { duration: segDur, easing: ease }),
        withTiming(xShifted[2], { duration: segDur, easing: ease }),
        withTiming(xShifted[3], { duration: segDur, easing: ease }),
        withTiming(xShifted[0], { duration: segDur, easing: ease }),
      ),
      -1,
      false
    );
    translateY.value = withRepeat(
      withSequence(
        withTiming(yShifted[1], { duration: segDur + 2000, easing: ease }),
        withTiming(yShifted[2], { duration: segDur + 1000, easing: ease }),
        withTiming(yShifted[3], { duration: segDur + 3000, easing: ease }),
        withTiming(yShifted[0], { duration: segDur, easing: ease }),
      ),
      -1,
      false
    );
  }, [index]);

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [
      { scale: 1.32 }, // Trochu větší scale aby kraj pohybu nebyl vidět
      { translateX: translateX.value },
      { translateY: translateY.value },
    ],
  }));

  return (
    <TouchableOpacity
      activeOpacity={0.85}
      style={styles.tile}
      onPress={onPress}
    >
      <View style={styles.tileImageContainer}>
        {thumb ? (
          <Animated.Image
            source={thumb}
            style={[styles.tileImage, animatedStyle]}
            resizeMode="cover"
          />
        ) : (
          <View style={styles.imagePlaceholder}>
            <Text style={styles.tilePlaceholderText}>{item.map_name}</Text>
          </View>
        )}
      </View>

      {/* Gradient overlay dole s textem */}
      <LinearGradient
        colors={['transparent', 'rgba(0,0,0,0.2)', 'rgba(0,0,0,0.85)']}
        locations={[0, 0.45, 1]}
        style={styles.tileOverlay}
      >
        <Text style={styles.tileMapName}>{item.map_name}</Text>
        <Text style={styles.tileCountText}>{getRoutesCountText(item.routes.length)}</Text>
      </LinearGradient>
    </TouchableOpacity>
  );
}

export default function ExploreScreen() {
  const router = useRouter();
  const { selectedTerrains, toggleTerrain, isTerrainSelected } = useFilter();
  const colors = useThemeColors();
  const styles = React.useMemo(() => getStyles(colors), [colors]);

  // Zoskupení dat podle map_id s podporou vícenásobného výběru filtrů
  const groupedData = useMemo(() => {
    let filtered = postupyIndex;
    if (selectedTerrains.length > 0) {
      filtered = filtered.filter((p: any) => selectedTerrains.includes(p.terrain));
    }

    const mapGroups = new Map();
    filtered.forEach((route: any) => {
      if (!mapGroups.has(route.map_id)) {
        mapGroups.set(route.map_id, {
          map_id: route.map_id,
          map_name: route.map_name,
          terrain: route.terrain,
          routes: [],
        });
      }
      mapGroups.get(route.map_id).routes.push(route);
    });
    return Array.from(mapGroups.values());
  }, [selectedTerrains]);

  const renderStory = (story: typeof STORIES[0]) => {
    const isSelected = isTerrainSelected(story.terrain);

    // Pokud je vybráno, použijeme LinearGradient (Instagram gradient), jinak šedý View
    const RingWrapper = isSelected ? LinearGradient : View;
    const ringProps = isSelected
      ? {
          colors: ['#f09433', '#e6683c', '#dc2743', '#cc2366', '#bc1888'],
          start: { x: 0, y: 1 },
          end: { x: 1, y: 0 },
          style: styles.storyRing,
        }
      : {
          style: [styles.storyRing, { backgroundColor: colors.border }],
        };

    const imageSource = story.isLocal ? story.img : { uri: story.img as string };

    return (
      <TouchableOpacity
        key={story.id}
        style={styles.storyItem}
        onPress={() => toggleTerrain(story.terrain)}
        activeOpacity={0.7}
      >
        <RingWrapper {...(ringProps as any)}>
          <Image source={imageSource} style={styles.storyImg} />
        </RingWrapper>
        <Text
          style={[
            styles.storyText,
            isSelected && { fontWeight: '700', color: colors.text },
          ]}
          numberOfLines={1}
        >
          {story.title}
        </Text>
      </TouchableOpacity>
    );
  };

  const ListHeader = () => (
    <View>
      <View style={styles.exploreHeader}>
        <Text style={styles.exploreTitle}>Terény</Text>
      </View>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.storiesContainer}
      >
        {STORIES.map(renderStory)}
      </ScrollView>
    </View>
  );

  const renderItem = ({ item, index }: { item: any; index: number }) => (
    <DriftingTile
      item={item}
      index={index}
      onPress={() => router.push(`/reels?map=${item.map_id}`)}
    />
  );

  return (
    <SafeAreaView style={styles.safeArea}>
      <FlatList
        data={groupedData}
        keyExtractor={(item) => item.map_id}
        numColumns={COLUMN_COUNT}
        renderItem={renderItem}
        ListHeaderComponent={ListHeader}
        contentContainerStyle={styles.gridContainer}
        columnWrapperStyle={groupedData.length > 0 ? styles.columnWrapper : undefined}
        showsVerticalScrollIndicator={false}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyTitle}>Žádné mapy pro vybrané terény</Text>
            <Text style={styles.emptySubtitle}>Zkuste kliknout na jiný filtr pro zobrazení tras.</Text>
          </View>
        }
      />
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.background,
  },
  exploreHeader: {
    paddingHorizontal: 15,
    paddingTop: 15,
    paddingBottom: 6,
    alignItems: 'center', // Centrování nápisu Terény 1:1 jako web
    justifyContent: 'center',
  },
  exploreTitle: {
    fontSize: 22,
    fontWeight: '800',
    color: colors.text,
    letterSpacing: -0.5,
  },
  storiesContainer: {
    paddingHorizontal: 15,
    paddingVertical: 10,
    gap: 14,
  },
  storyItem: {
    alignItems: 'center',
    width: 68,
  },
  storyRing: {
    width: 64,
    height: 64,
    borderRadius: 32,
    padding: 2.5,
    justifyContent: 'center',
    alignItems: 'center',
  },
  storyImg: {
    width: '100%',
    height: '100%',
    borderRadius: 29.5,
    borderWidth: 2.5,
    borderColor: colors.background,
  },
  storyText: {
    fontSize: 11,
    marginTop: 5,
    color: colors.text,
    fontWeight: '400',
    textAlign: 'center',
  },
  gridContainer: {
    paddingBottom: 100,
  },
  columnWrapper: {
    gap: SPACING,
    marginBottom: SPACING,
  },
  tile: {
    width: TILE_WIDTH,
    height: TILE_HEIGHT,
    position: 'relative',
    overflow: 'hidden',
    backgroundColor: colors.pillBg,
  },
  tileImageContainer: {
    width: '100%',
    height: '100%',
    overflow: 'hidden',
  },
  tileImage: {
    width: '100%',
    height: '100%',
  },
  imagePlaceholder: {
    flex: 1,
    backgroundColor: colors.pillBg,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 10,
  },
  tilePlaceholderText: {
    color: colors.secondaryText,
    fontSize: 12,
    fontWeight: '600',
    textAlign: 'center',
  },
  tileOverlay: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    paddingTop: 24,
    paddingBottom: 8,
    paddingHorizontal: 8,
  },
  tileMapName: {
    color: '#ffffff',
    fontSize: 12,
    fontWeight: '700',
    textShadowColor: 'rgba(0,0,0,0.9)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 3,
    marginBottom: 1,
  },
  tileCountText: {
    color: 'rgba(255,255,255,0.85)',
    fontSize: 11,
    fontWeight: '600',
    textShadowColor: 'rgba(0,0,0,0.85)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 2,
  },
  emptyContainer: {
    paddingTop: 60,
    alignItems: 'center',
    paddingHorizontal: 30,
  },
  emptyTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 6,
    textAlign: 'center',
  },
  emptySubtitle: {
    fontSize: 13,
    color: colors.secondaryText,
    textAlign: 'center',
  },
});
