import React, { useState, useMemo } from 'react';
import {
  StyleSheet,
  Text,
  View,
  ScrollView,
  TouchableOpacity,
  Dimensions,
  Image,
  TextInput,
  Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import Svg, { Line, Circle } from 'react-native-svg';
import Feather from '@expo/vector-icons/Feather';
import Ionicons from '@expo/vector-icons/Ionicons';
import * as ImagePicker from 'expo-image-picker';
import { ref, uploadBytes, getDownloadURL } from 'firebase/storage';
import { storage } from '../../config/firebase';

import postupyIndex from '../../../assets/postupy/postupy_index.json';
import thumbsMetaRaw from '../../../assets/thumbs/thumbs_meta.json';
import { useApp, useThemeColors } from '../../context/AppContext';

const { width } = Dimensions.get('window');
const COLUMN_COUNT = 3;
const SPACING = 2;
const CARD_WIDTH = (width - (COLUMN_COUNT - 1) * SPACING) / COLUMN_COUNT;
const CARD_HEIGHT = CARD_WIDTH * (5 / 4); // 4:5 poměr stran

const MAP_IMAGES: Record<string, any> = {
  holna: require('../../../assets/thumbs/map_holna.jpg'),
  bilaskala: require('../../../assets/thumbs/map_bilaskala.jpg'),
  homolka: require('../../../assets/thumbs/map_homolka.jpg'),
};

const thumbsMeta = thumbsMetaRaw as any;
const IOF_PURPLE = '#b300ff';

const TERRAIN_NAMES: Record<string, string> = {
  cesko: 'Česko',
  'cesky-les': 'Česko',
  skandinavie: 'Skandinávie',
  madarsko: 'Maďarsko',
  piskovce: 'Pískovce',
  alpy: 'Alpy',
  mesto: 'Město',
};

export default function ProfileScreen() {
  const router = useRouter();
  const {
    userName,
    setUserName,
    userBio,
    setUserBio,
    savedRoutes,
    viewedRoutes,
    appTimeMs,
    t,
    userAvatar,
    setUserAvatar,
  } = useApp();
  const colors = useThemeColors();
  const styles = React.useMemo(() => getStyles(colors), [colors]);

  const [selectedTerrain, setSelectedTerrain] = useState<string>('Vše');
  const [isEditingName, setIsEditingName] = useState(false);
  const [isEditingBio, setIsEditingBio] = useState(false);
  const [tempName, setTempName] = useState(userName);
  const [tempBio, setTempBio] = useState(userBio);
  const [isUploading, setIsUploading] = useState(false);

  const pickImage = async () => {
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'],
        allowsEditing: true,
        aspect: [1, 1],
        quality: 0.5,
      });

      if (!result.canceled && result.assets[0].uri) {
        setIsUploading(true);
        const uri = result.assets[0].uri;
        
        // Nativní fetch pro převedení na blob (potřebné pro Firebase Storage)
        const response = await fetch(uri);
        const blob = await response.blob();
        
        // Vytvoř reference s unikátním názvem
        const filename = `avatars/avatar_${Date.now()}.jpg`;
        const storageRef = ref(storage, filename);
        
        // Upload
        await uploadBytes(storageRef, blob);
        const downloadUrl = await getDownloadURL(storageRef);
        
        setUserAvatar(downloadUrl);
      }
    } catch (e) {
      console.warn('Error uploading image:', e);
    } finally {
      setIsUploading(false);
    }
  };

  // Získání uložených tras
  const savedPostupy = useMemo(() => {
    return postupyIndex.filter((p: any) => {
      const basename = p.file.replace('.geojson', '').replace('.json', '');
      return savedRoutes.includes(basename);
    });
  }, [savedRoutes]);

  // Unikátní terény mezi uloženými trasami pro filtry
  const availableTerrains = useMemo(() => {
    const list = new Set<string>();
    savedPostupy.forEach((p: any) => {
      if (p.terrain) list.add(p.terrain);
    });
    return Array.from(list);
  }, [savedPostupy]);

  // Filtrování zobrazených karet podle vybraného terénu
  const displayData = useMemo(() => {
    if (selectedTerrain === 'Vše') return savedPostupy;
    return savedPostupy.filter((p: any) => p.terrain === selectedTerrain);
  }, [savedPostupy, selectedTerrain]);

  const hoursSpent = (appTimeMs / 3600000).toFixed(1);

  // Karta postupu s orienťáckou SVG trasou 1:1 z webu
  const renderCard = (route: any, index: number) => {
    const basename = route.file.replace('.geojson', '').replace('.json', '');
    const pts = thumbsMeta?.routes?.[basename];
    const mapImg = MAP_IMAGES[route.map_id] || MAP_IMAGES.homolka;

    let svgMarkup = null;
    if (pts) {
      const p1_x = pts.start[0] * 14.0;
      const p1_y = pts.start[1] * 17.5;
      const p2_x = pts.end[0] * 14.0;
      const p2_y = pts.end[1] * 17.5;

      const vdx = p2_x - p1_x;
      const vdy = p2_y - p1_y;
      const vdist = Math.hypot(vdx, vdy);

      const R = 17.0;
      const strokeW = 4.6;

      let sx = p1_x;
      let sy = p1_y;
      let ex = p2_x;
      let ey = p2_y;

      if (vdist > R * 2) {
        sx = p1_x + (vdx / vdist) * R;
        sy = p1_y + (vdy / vdist) * R;
        ex = p2_x - (vdx / vdist) * R;
        ey = p2_y - (vdy / vdist) * R;
      }

      svgMarkup = (
        <Svg viewBox="0 0 1400 1750" style={styles.cardSvg}>
          {vdist > R * 2 && (
            <Line
              x1={sx}
              y1={sy}
              x2={ex}
              y2={ey}
              stroke={IOF_PURPLE}
              strokeWidth={strokeW}
              strokeOpacity={0.85}
              strokeLinecap="round"
            />
          )}
          <Circle cx={p1_x} cy={p1_y} r={R} stroke={IOF_PURPLE} strokeWidth={strokeW} fill="none" />
          <Circle cx={p2_x} cy={p2_y} r={R} stroke={IOF_PURPLE} strokeWidth={strokeW} fill="none" />
        </Svg>
      );
    }

    return (
      <TouchableOpacity
        key={route.file || index}
        activeOpacity={0.8}
        style={styles.card}
        onPress={() => router.push(`/reels?map=${route.map_id}`)}
      >
        <Image source={mapImg} style={styles.cardImage} resizeMode="cover" />
        {svgMarkup}
      </TouchableOpacity>
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
        {/* HORNÍ LIŠTA: Uživatelské jméno */}
        <View style={styles.topHeader}>
          <TouchableOpacity
            style={styles.usernameRow}
            onPress={() => {
              setTempName(userName);
              setIsEditingName(true);
            }}
          >
            <Text style={styles.usernameText}>{userName}</Text>
            <Feather name="edit-2" size={14} color="#737373" />
          </TouchableOpacity>
        </View>

        {/* AVATAR A STATISTIKY */}
        <View style={styles.statsSection}>
          <TouchableOpacity 
            style={styles.avatarCircle} 
            onPress={pickImage}
            disabled={isUploading}
          >
            {isUploading ? (
               <Text style={{fontSize: 12, color: colors.secondaryText}}>Ukládám...</Text>
            ) : userAvatar ? (
               <Image source={{ uri: userAvatar }} style={styles.avatarImage} />
            ) : (
               <Feather name="user" size={38} color={colors.secondaryText} />
            )}
          </TouchableOpacity>

          <View style={styles.statsRow}>
            <View style={styles.statItem}>
              <Text style={styles.statNum}>{viewedRoutes.length}</Text>
              <Text style={styles.statLabel}>{t('analyzed')}</Text>
            </View>

            <View style={styles.statItem}>
              <Text style={styles.statNum}>{savedPostupy.length}</Text>
              <Text style={styles.statLabel}>{t('saved')}</Text>
            </View>

            <View style={styles.statItem}>
              <Text style={styles.statNum}>{hoursSpent}</Text>
              <Text style={styles.statLabel}>{t('hours')}</Text>
            </View>
          </View>
        </View>

        {/* BIO SEKCE */}
        <View style={styles.bioSection}>
          <Text style={styles.realName}>František Čtrnáct</Text>
          <TouchableOpacity
            style={styles.bioRow}
            onPress={() => {
              setTempBio(userBio);
              setIsEditingBio(true);
            }}
          >
            <Text style={styles.bioText}>{userBio}</Text>
            <Feather name="edit-2" size={12} color="#737373" style={{ marginTop: 2 }} />
          </TouchableOpacity>
        </View>

        {/* FILTRY TERÉNŮ (PILLS) */}
        {savedPostupy.length > 0 && (
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.pillsContainer}
          >
            <TouchableOpacity
              style={[styles.pill, selectedTerrain === 'Vše' && styles.pillActive]}
              onPress={() => setSelectedTerrain('Vše')}
            >
              <Text style={[styles.pillText, selectedTerrain === 'Vše' && styles.pillTextActive]}>
                {t('all')}
              </Text>
            </TouchableOpacity>

            {availableTerrains.map((ter) => (
              <TouchableOpacity
                key={ter}
                style={[styles.pill, selectedTerrain === ter && styles.pillActive]}
                onPress={() => setSelectedTerrain(ter)}
              >
                <Text style={[styles.pillText, selectedTerrain === ter && styles.pillTextActive]}>
                  {TERRAIN_NAMES[ter] || ter}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        )}

        {/* 3-SLOUPOVÁ MŘÍŽKA ULOŽENÝCH TRAS */}
        {savedPostupy.length === 0 ? (
          <View style={styles.emptyContainer}>
            <Ionicons name="bookmark-outline" size={44} color={colors.secondaryText} style={{ marginBottom: 10 }} />
            <Text style={styles.emptyTitle}>{t('noSaved')}</Text>
            <Text style={styles.emptyDesc}>{t('noSavedDesc')}</Text>
          </View>
        ) : (
          <View style={styles.gridContainer}>
            {displayData.map((route: any, index: number) => renderCard(route, index))}
          </View>
        )}
      </ScrollView>

      {/* MODAL PRO EDITACI JMÉNA */}
      <Modal visible={isEditingName} transparent animationType="fade">
        <View style={styles.modalBg}>
          <View style={styles.modalBox}>
            <Text style={styles.modalTitle}>Upravit uživatelské jméno</Text>
            <TextInput
              style={styles.modalInput}
              value={tempName}
              onChangeText={setTempName}
              autoFocus
            />
            <View style={styles.modalBtnRow}>
              <TouchableOpacity
                style={styles.modalCancelBtn}
                onPress={() => setIsEditingName(false)}
              >
                <Text style={styles.modalBtnText}>Zrušit</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.modalConfirmBtn}
                onPress={() => {
                  if (tempName.trim()) setUserName(tempName.trim());
                  setIsEditingName(false);
                }}
              >
                <Text style={[styles.modalBtnText, { color: '#0095f6', fontWeight: '700' }]}>
                  Uložit
                </Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* MODAL PRO EDITACI BIO */}
      <Modal visible={isEditingBio} transparent animationType="fade">
        <View style={styles.modalBg}>
          <View style={styles.modalBox}>
            <Text style={styles.modalTitle}>Upravit bio</Text>
            <TextInput
              style={[styles.modalInput, { height: 80 }]}
              value={tempBio}
              onChangeText={setTempBio}
              multiline
              autoFocus
            />
            <View style={styles.modalBtnRow}>
              <TouchableOpacity
                style={styles.modalCancelBtn}
                onPress={() => setIsEditingBio(false)}
              >
                <Text style={styles.modalBtnText}>Zrušit</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.modalConfirmBtn}
                onPress={() => {
                  if (tempBio.trim()) setUserBio(tempBio.trim());
                  setIsEditingBio(false);
                }}
              >
                <Text style={[styles.modalBtnText, { color: '#0095f6', fontWeight: '700' }]}>
                  Uložit
                </Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    paddingBottom: 90,
  },
  topHeader: {
    paddingHorizontal: 16,
    paddingTop: 10,
    paddingBottom: 8,
    borderBottomWidth: 0.5,
    borderBottomColor: colors.border,
  },
  usernameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  usernameText: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.text,
    letterSpacing: -0.3,
  },
  statsSection: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 12,
    alignItems: 'center',
  },
  avatarCircle: {
    width: 77,
    height: 77,
    borderRadius: 38.5,
    backgroundColor: colors.secondaryBg,
    borderWidth: 0.5,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  avatarImage: {
    width: '100%',
    height: '100%',
  },
  statsRow: {
    flex: 1,
    flexDirection: 'row',
    justifyContent: 'space-evenly',
    alignItems: 'center',
  },
  statItem: {
    alignItems: 'center',
  },
  statNum: {
    fontSize: 17,
    fontWeight: '700',
    color: colors.text,
  },
  statLabel: {
    fontSize: 13,
    color: colors.secondaryText,
    marginTop: 2,
  },
  bioSection: {
    paddingHorizontal: 16,
    paddingBottom: 16,
  },
  realName: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 3,
  },
  bioRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 6,
  },
  bioText: {
    flex: 1,
    fontSize: 13,
    color: colors.secondaryText,
    lineHeight: 18,
  },
  pillsContainer: {
    paddingHorizontal: 16,
    paddingBottom: 12,
    gap: 8,
  },
  pill: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.pillBg,
  },
  pillActive: {
    backgroundColor: colors.text,
    borderColor: colors.text,
  },
  pillText: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.text,
  },
  pillTextActive: {
    color: colors.background,
  },
  gridContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: SPACING,
  },
  card: {
    width: CARD_WIDTH,
    height: CARD_HEIGHT,
    backgroundColor: colors.secondaryBg,
    position: 'relative',
    overflow: 'hidden',
  },
  cardImage: {
    width: '100%',
    height: '100%',
    position: 'absolute',
  },
  cardSvg: {
    width: '100%',
    height: '100%',
    position: 'absolute',
  },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 60,
    paddingHorizontal: 24,
  },
  emptyTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 4,
  },
  emptyDesc: {
    fontSize: 13,
    color: colors.secondaryText,
    textAlign: 'center',
  },
  modalBg: {
    flex: 1,
    backgroundColor: colors.overlay,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 30,
  },
  modalBox: {
    width: '100%',
    maxWidth: 320,
    backgroundColor: colors.modalBg,
    borderRadius: 16,
    padding: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 10,
    elevation: 8,
  },
  modalTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 12,
  },
  modalInput: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 15,
    color: colors.text,
    marginBottom: 16,
  },
  modalBtnRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 16,
  },
  modalCancelBtn: {
    paddingVertical: 6,
    paddingHorizontal: 10,
  },
  modalConfirmBtn: {
    paddingVertical: 6,
    paddingHorizontal: 10,
  },
  modalBtnText: {
    fontSize: 14,
    color: colors.secondaryText,
  },
});
