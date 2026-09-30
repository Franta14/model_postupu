import React, { useState } from 'react';
import {
  StyleSheet,
  Text,
  View,
  ScrollView,
  TouchableOpacity,
  Modal,
  TextInput,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Feather from '@expo/vector-icons/Feather';
import { useApp, useThemeColors } from '../../context/AppContext';

export default function SettingsScreen() {
  const { userSettings, updateSetting, formatPace, t } = useApp();
  const colors = useThemeColors();
  const styles = React.useMemo(() => getStyles(colors), [colors]);

  // Modaly
  const [isPaceModalOpen, setIsPaceModalOpen] = useState(false);
  const [isLangModalOpen, setIsLangModalOpen] = useState(false);
  const [isThemeModalOpen, setIsThemeModalOpen] = useState(false);

  // Hodnoty pro Pace modal
  const initialMin = Math.floor(userSettings.pace / 60);
  const initialSec = userSettings.pace % 60;
  const [paceMin, setPaceMin] = useState(String(initialMin));
  const [paceSec, setPaceSec] = useState(String(initialSec).padStart(2, '0'));

  const handleSavePace = () => {
    const m = parseInt(paceMin, 10) || 3;
    const s = parseInt(paceSec, 10) || 0;
    const totalSec = Math.max(60, Math.min(600, m * 60 + s));
    updateSetting('pace', totalSec);
    setIsPaceModalOpen(false);
  };

  const handleClearCache = () => {
    Alert.alert('Vymazat cache', 'Opravdu chcete vymazat mezipaměť aplikace?', [
      { text: 'Zrušit', style: 'cancel' },
      {
        text: 'Vymazat',
        style: 'destructive',
        onPress: () => {
          Alert.alert('Hotovo', 'Cache byla úspěšně vymazána.');
        },
      },
    ]);
  };

  const handleReplayTutorial = () => {
    Alert.alert('Tutoriál', 'Interaktivní tutoriál byl resetován. Spustí se při přechodu na záložku Explore.');
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
        {/* HORNÍ HLAVIČKA */}
        <View style={styles.header}>
          <Text style={styles.headerTitle}>{t('settings')} a aktivita</Text>
        </View>

        {/* 1. SEKCE: BĚŽEC */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>{t('runner')}</Text>
        </View>

        <TouchableOpacity
          activeOpacity={0.7}
          style={styles.settingRow}
          onPress={() => {
            setPaceMin(String(Math.floor(userSettings.pace / 60)));
            setPaceSec(String(userSettings.pace % 60).padStart(2, '0'));
            setIsPaceModalOpen(true);
          }}
        >
          <View style={styles.iconCircle}>
            <Feather name="clock" size={20} color={colors.icon} />
          </View>
          <View style={styles.rowMain}>
            <Text style={styles.rowLabel}>{t('paceOnRoad')}</Text>
          </View>
          <Text style={styles.rowValue}>{formatPace(userSettings.pace)}</Text>
          <Feather name="chevron-right" size={20} color={colors.secondaryText} style={{ opacity: 0.5 }} />
        </TouchableOpacity>

        {/* 2. SEKCE: APLIKACE */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>{t('application')}</Text>
        </View>

        {/* Jazyk */}
        <TouchableOpacity
          activeOpacity={0.7}
          style={styles.settingRow}
          onPress={() => setIsLangModalOpen(true)}
        >
          <View style={styles.iconCircle}>
            <Feather name="globe" size={20} color={colors.icon} />
          </View>
          <View style={styles.rowMain}>
            <Text style={styles.rowLabel}>{t('language')}</Text>
          </View>
          <Text style={styles.rowValue}>
            {userSettings.language === 'cs' ? 'Čeština' : 'English'}
          </Text>
          <Feather name="chevron-right" size={20} color={colors.secondaryText} style={{ opacity: 0.5 }} />
        </TouchableOpacity>

        {/* Vzhled */}
        <TouchableOpacity
          activeOpacity={0.7}
          style={styles.settingRow}
          onPress={() => setIsThemeModalOpen(true)}
        >
          <View style={styles.iconCircle}>
            <Feather name="sun" size={20} color={colors.icon} />
          </View>
          <View style={styles.rowMain}>
            <Text style={styles.rowLabel}>{t('theme')}</Text>
          </View>
          <Text style={styles.rowValue}>{t(`theme_${userSettings.theme}`)}</Text>
          <Feather name="chevron-right" size={20} color={colors.secondaryText} style={{ opacity: 0.5 }} />
        </TouchableOpacity>

        {/* Uložit mapy offline */}
        <TouchableOpacity
          activeOpacity={0.7}
          style={styles.settingRow}
          onPress={() => Alert.alert('Offline mapy', 'Všechny postupy a mapové podklady jsou uloženy přímo v mobilní aplikaci.')}
        >
          <View style={styles.iconCircle}>
            <Feather name="download-cloud" size={20} color={colors.icon} />
          </View>
          <View style={styles.rowMain}>
            <Text style={styles.rowLabel}>{t('offlineMaps')}</Text>
          </View>
          <Feather name="chevron-right" size={20} color={colors.secondaryText} style={{ opacity: 0.5 }} />
        </TouchableOpacity>

        {/* 3. SEKCE: MAPY */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>{t('maps')}</Text>
        </View>

        <TouchableOpacity
          activeOpacity={0.7}
          style={styles.settingRow}
          onPress={handleClearCache}
        >
          <View style={styles.iconCircle}>
            <Feather name="trash-2" size={20} color={colors.icon} />
          </View>
          <View style={styles.rowMain}>
            <Text style={styles.rowLabel}>{t('clearCache')}</Text>
          </View>
          <Text style={styles.rowValue}>0 MB</Text>
          <Feather name="chevron-right" size={20} color={colors.secondaryText} style={{ opacity: 0.5 }} />
        </TouchableOpacity>

        {/* 4. SEKCE: NÁPOVĚDA */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Nápověda</Text>
        </View>

        <TouchableOpacity
          activeOpacity={0.7}
          style={styles.settingRow}
          onPress={handleReplayTutorial}
        >
          <View style={styles.iconCircle}>
            <Feather name="help-circle" size={20} color={colors.icon} />
          </View>
          <View style={styles.rowMain}>
            <Text style={styles.rowLabel}>Znovu spustit tutoriál</Text>
          </View>
          <Feather name="chevron-right" size={20} color={colors.secondaryText} style={{ opacity: 0.5 }} />
        </TouchableOpacity>
      </ScrollView>

      {/* MODAL PRO TEMPO NA CESTĚ (MINUTY : SEKUNDY) */}
      <Modal visible={isPaceModalOpen} transparent animationType="fade">
        <View style={styles.modalBg}>
          <View style={styles.modalBox}>
            <Text style={styles.modalHeaderTitle}>{t('paceOnRoad')}</Text>
            <Text style={styles.modalHeaderSub}>
              Zadej průměrné tempo na rovině pro přepočet časů variant.
            </Text>

            <View style={styles.paceInputsRow}>
              <TextInput
                style={styles.paceInput}
                value={paceMin}
                onChangeText={setPaceMin}
                keyboardType="number-pad"
                maxLength={2}
              />
              <Text style={styles.paceColon}>:</Text>
              <TextInput
                style={styles.paceInput}
                value={paceSec}
                onChangeText={setPaceSec}
                keyboardType="number-pad"
                maxLength={2}
              />
            </View>

            <View style={styles.modalFooter}>
              <TouchableOpacity
                style={styles.modalCancelBtn}
                onPress={() => setIsPaceModalOpen(false)}
              >
                <Text style={styles.modalCancelText}>Zrušit</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.modalConfirmBtn} onPress={handleSavePace}>
                <Text style={styles.modalConfirmText}>Uložit</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* MODAL PRO JAZYK */}
      <Modal visible={isLangModalOpen} transparent animationType="fade">
        <View style={styles.modalBg}>
          <View style={styles.modalBox}>
            <Text style={styles.modalHeaderTitle}>{t('language')}</Text>

            <TouchableOpacity
              style={styles.optionRow}
              onPress={() => {
                updateSetting('language', 'cs');
                setIsLangModalOpen(false);
              }}
            >
              <Text
                style={[
                  styles.optionText,
                  userSettings.language === 'cs' && styles.optionTextActive,
                ]}
              >
                Čeština
              </Text>
              {userSettings.language === 'cs' && (
                <Feather name="check" size={20} color="#0095f6" />
              )}
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.optionRow}
              onPress={() => {
                updateSetting('language', 'en');
                setIsLangModalOpen(false);
              }}
            >
              <Text
                style={[
                  styles.optionText,
                  userSettings.language === 'en' && styles.optionTextActive,
                ]}
              >
                English
              </Text>
              {userSettings.language === 'en' && (
                <Feather name="check" size={20} color="#0095f6" />
              )}
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.modalCancelBtn, { borderTopWidth: 0.5, borderTopColor: '#dbdbdb', width: '100%', marginTop: 8 }]}
              onPress={() => setIsLangModalOpen(false)}
            >
              <Text style={styles.modalCancelText}>Zavřít</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* MODAL PRO VZHLED */}
      <Modal visible={isThemeModalOpen} transparent animationType="fade">
        <View style={styles.modalBg}>
          <View style={styles.modalBox}>
            <Text style={styles.modalHeaderTitle}>{t('theme')}</Text>

            {(['system', 'light', 'dark'] as const).map((thm) => (
              <TouchableOpacity
                key={thm}
                style={styles.optionRow}
                onPress={() => {
                  updateSetting('theme', thm);
                  setIsThemeModalOpen(false);
                }}
              >
                <Text
                  style={[
                    styles.optionText,
                    userSettings.theme === thm && styles.optionTextActive,
                  ]}
                >
                  {t(`theme_${thm}`)}
                </Text>
                {userSettings.theme === thm && (
                  <Feather name="check" size={20} color="#0095f6" />
                )}
              </TouchableOpacity>
            ))}

            <TouchableOpacity
              style={[styles.modalCancelBtn, { borderTopWidth: 0.5, borderTopColor: '#dbdbdb', width: '100%', marginTop: 8 }]}
              onPress={() => setIsThemeModalOpen(false)}
            >
              <Text style={styles.modalCancelText}>Zavřít</Text>
            </TouchableOpacity>
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
  header: {
    paddingHorizontal: 16,
    paddingTop: 10,
    paddingBottom: 12,
    borderBottomWidth: 0.5,
    borderBottomColor: colors.border,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.text,
    letterSpacing: -0.3,
  },
  sectionHeader: {
    paddingHorizontal: 16,
    paddingTop: 20,
    paddingBottom: 8,
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.secondaryText,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  settingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 14,
    gap: 14,
    backgroundColor: colors.background,
  },
  iconCircle: {
    width: 24,
    height: 24,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rowMain: {
    flex: 1,
  },
  rowLabel: {
    fontSize: 15,
    fontWeight: '400',
    color: colors.text,
  },
  rowValue: {
    fontSize: 15,
    color: colors.secondaryText,
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
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.2,
    shadowRadius: 16,
    elevation: 10,
  },
  modalHeaderTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.text,
    textAlign: 'center',
    paddingTop: 18,
    paddingBottom: 4,
  },
  modalHeaderSub: {
    fontSize: 13,
    color: colors.secondaryText,
    textAlign: 'center',
    paddingHorizontal: 16,
    marginBottom: 16,
  },
  paceInputsRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 12,
    paddingBottom: 24,
  },
  paceInput: {
    width: 68,
    height: 54,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    backgroundColor: colors.secondaryBg,
    textAlign: 'center',
    fontSize: 24,
    fontWeight: '700',
    color: colors.text,
  },
  paceColon: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.text,
  },
  modalFooter: {
    flexDirection: 'row',
    borderTopWidth: 0.5,
    borderTopColor: colors.border,
  },
  modalCancelBtn: {
    flex: 1,
    paddingVertical: 14,
    alignItems: 'center',
    borderRightWidth: 0.5,
    borderRightColor: colors.border,
  },
  modalConfirmBtn: {
    flex: 1,
    paddingVertical: 14,
    alignItems: 'center',
  },
  modalCancelText: {
    fontSize: 15,
    color: colors.text,
    fontWeight: '600',
  },
  modalConfirmText: {
    fontSize: 15,
    color: colors.blue,
    fontWeight: '700',
  },
  optionRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 14,
    borderBottomWidth: 0.5,
    borderBottomColor: colors.border,
  },
  optionText: {
    fontSize: 15,
    color: colors.text,
  },
  optionTextActive: {
    color: colors.blue,
    fontWeight: '700',
  },
});
