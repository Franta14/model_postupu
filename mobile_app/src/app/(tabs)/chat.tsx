import React, { useState } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  TouchableOpacity,
  ScrollView,
  Image,
  Dimensions,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import Feather from '@expo/vector-icons/Feather';
import Ionicons from '@expo/vector-icons/Ionicons';
import { useApp, useThemeColors } from '../../context/AppContext';
import { collection, query, orderBy, limit, onSnapshot, addDoc, serverTimestamp } from 'firebase/firestore';
import { db } from '../../config/firebase';
import { useEffect, useRef } from 'react';

const { width } = Dimensions.get('window');

interface ChatMessage {
  id: string;
  author: string;
  isMe: boolean;
  text?: string;
  type?: 'text' | 'shared_route';
  mapId?: string;
  mapName?: string;
  distM?: number;
  routeFile?: string;
  time?: string;
}

const MAP_IMAGES: Record<string, any> = {
  holna: require('../../../assets/thumbs/map_holna.jpg'),
  bilaskala: require('../../../assets/thumbs/map_bilaskala.jpg'),
  homolka: require('../../../assets/thumbs/map_homolka.jpg'),
};

export default function ChatScreen() {
  const router = useRouter();
  const { userName, isBookmarked, toggleBookmark } = useApp();
  const colors = useThemeColors();
  const styles = React.useMemo(() => getStyles(colors), [colors]);

  const [activeConv, setActiveConv] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [messageInput, setMessageInput] = useState('');

  // Výchozí zprávy v Globálním diskuzním klubu včetně ukázky 9:16 sdíleného orienťáckého postupu
  // Globální chat zprávy
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const scrollViewRef = useRef<ScrollView>(null);

  // Firestore listener
  useEffect(() => {
    if (activeConv !== 'Globální Diskuzní Klub') return;

    const q = query(
      collection(db, 'global_chat'),
      orderBy('timestamp', 'asc'),
      limit(100)
    );

    const unsubscribe = onSnapshot(q, (snapshot) => {
      const newMsgs: ChatMessage[] = [];
      snapshot.forEach((doc) => {
        const data = doc.data();
        let timeStr = 'Teď';
        if (data.timestamp) {
          const d = data.timestamp.toDate ? data.timestamp.toDate() : new Date(data.timestamp.seconds * 1000);
          timeStr = d.toLocaleTimeString('cs-CZ', { hour: '2-digit', minute: '2-digit' });
        }
        newMsgs.push({
          id: doc.id,
          author: data.author || 'Neznámý',
          isMe: data.author === userName,
          text: data.text,
          type: data.type || 'text',
          mapId: data.mapId,
          mapName: data.mapName,
          distM: data.distM,
          routeFile: data.routeFile,
          time: timeStr,
        });
      });
      setMessages(newMsgs);
      // Auto scroll
      setTimeout(() => {
        scrollViewRef.current?.scrollToEnd({ animated: true });
      }, 100);
    });

    return () => unsubscribe();
  }, [activeConv, userName]);

  const handleSendMessage = async () => {
    if (!messageInput.trim()) return;
    const currentText = messageInput;
    setMessageInput('');
    try {
      await addDoc(collection(db, 'global_chat'), {
        author: userName || 'Anonym',
        text: currentText.trim(),
        type: 'text',
        timestamp: serverTimestamp(),
      });
    } catch (e) {
      console.warn('Error sending message:', e);
      setMessageInput(currentText);
    }
  };

  // Seznam kontaktů pro vyhledávání
  const contacts = [
    { name: 'Tomas_bez', lastMsg: 'Ahoj všem! Jak se vám líbily včerejší postupy?' },
    { name: 'Klara123', lastMsg: 'Tenhle postup byl naprosto skvělý...' },
    { name: 'Ondřej_O', lastMsg: 'Kdy jdeš běhat příště?' },
    { name: 'Martin_OB', lastMsg: 'Ta mapa byla luxusní.' },
  ];

  const filteredContacts = contacts.filter((c) =>
    c.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <SafeAreaView style={styles.container}>
      {/* 1. OBRAZOVKA SEZNAMU CHATŮ */}
      {!activeConv ? (
        <View style={styles.mainChatList}>
          {/* Hlavička s uživatelským jménem */}
          <View style={styles.header}>
            <Text style={styles.headerTitle}>{userName}</Text>
          </View>

          {/* Vyhledávací pole */}
          <View style={styles.searchBar}>
            <Feather name="search" size={16} color={colors.secondaryText} />
            <TextInput
              style={styles.searchInput}
              placeholder="Hledat"
              placeholderTextColor={colors.secondaryText}
              value={searchQuery}
              onChangeText={setSearchQuery}
            />
          </View>

          {/* Seznam chatů */}
          <ScrollView style={styles.chatListContent}>
            {/* Globální diskuzní klub */}
            <TouchableOpacity
              activeOpacity={0.7}
              style={styles.chatRow}
              onPress={() => setActiveConv('Globální Diskuzní Klub')}
            >
              <View style={styles.groupAvatar}>
                <Feather name="users" size={24} color={colors.secondaryText} />
              </View>
              <View style={styles.chatRowInfo}>
                <Text style={styles.chatRowName}>Globální Diskuzní Klub</Text>
                <Text style={styles.chatRowMsg}>Klikni a vstup do živého chatu!</Text>
              </View>
            </TouchableOpacity>

            {/* Ostatní kontakty */}
            {filteredContacts.map((c) => (
              <TouchableOpacity
                key={c.name}
                activeOpacity={0.7}
                style={styles.chatRow}
                onPress={() => setActiveConv(c.name)}
              >
                <View style={styles.userAvatar}>
                  <Feather name="user" size={22} color={colors.secondaryText} />
                </View>
                <View style={styles.chatRowInfo}>
                  <Text style={styles.chatRowName}>{c.name}</Text>
                  <Text style={styles.chatRowMsg}>{c.lastMsg}</Text>
                </View>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>
      ) : (
        /* 2. OBRAZOVKA OTEVŘENÉ KONVERZACE */
        <KeyboardAvoidingView
          style={styles.conversationContainer}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
        >
          {/* Hlavička konverzace se šipkou zpět */}
          <View style={styles.convHeader}>
            <TouchableOpacity
              style={styles.backBtn}
              onPress={() => setActiveConv(null)}
            >
              <Feather name="chevron-left" size={28} color={colors.text} />
            </TouchableOpacity>
            <Text style={styles.convHeaderTitle}>{activeConv}</Text>
          </View>

          {/* Zprávy */}
          <ScrollView
            ref={scrollViewRef}
            style={styles.messagesBox}
            contentContainerStyle={styles.messagesContent}
            onContentSizeChange={() => scrollViewRef.current?.scrollToEnd({ animated: true })}
          >
            {messages.map((m) => {
              if (m.type === 'shared_route') {
                const mapImg = MAP_IMAGES[m.mapId || 'holna'] || MAP_IMAGES.holna;
                const basename = (m.routeFile || '').replace('.geojson', '').replace('.json', '');
                const bookmarked = isBookmarked(basename);

                return (
                  <View
                    key={m.id}
                    style={[
                      styles.msgBubbleWrapper,
                      m.isMe ? styles.alignMe : styles.alignOther,
                    ]}
                  >
                    {!m.isMe && <Text style={styles.authorLabel}>{m.author}</Text>}

                    <View style={styles.sharedCardRow}>
                      {/* 9:16 INSTAGRAM REEL KARTA */}
                      <TouchableOpacity
                        activeOpacity={0.88}
                        style={styles.reelShareCard}
                        onPress={() => router.push(`/reels?map=${m.mapId || 'holna'}`)}
                      >
                        <Image source={mapImg} style={styles.reelShareImg} resizeMode="cover" />
                        <View style={styles.reelShareOverlay}>
                          <Text style={styles.reelShareName}>{m.mapName}</Text>
                          <Text style={styles.reelShareDist}>{m.distM} m vzdušně</Text>
                        </View>
                      </TouchableOpacity>

                      {/* Postranní rychlá tlačítka */}
                      <View style={styles.cardActions}>
                        <TouchableOpacity
                          style={styles.circleActionBtn}
                          onPress={() => toggleBookmark(basename)}
                        >
                          <Ionicons
                            name={bookmarked ? 'bookmark' : 'bookmark-outline'}
                            size={18}
                            color={colors.text}
                          />
                        </TouchableOpacity>
                      </View>
                    </View>
                  </View>
                );
              }

              // Běžná textová zpráva
              return (
                <View
                  key={m.id}
                  style={[
                    styles.msgBubbleWrapper,
                    m.isMe ? styles.alignMe : styles.alignOther,
                  ]}
                >
                  {!m.isMe && <Text style={styles.authorLabel}>{m.author}</Text>}
                  <View
                    style={[
                      styles.textBubble,
                      m.isMe ? styles.bubbleMe : styles.bubbleOther,
                    ]}
                  >
                    <Text
                      style={[
                        styles.bubbleText,
                        m.isMe ? styles.bubbleTextMe : styles.bubbleTextOther,
                      ]}
                    >
                      {m.text}
                    </Text>
                  </View>
                </View>
              );
            })}
          </ScrollView>

          {/* Vstupní pole pro zprávu */}
          <View style={styles.inputContainer}>
            <TextInput
              style={styles.msgInput}
              placeholder="Napsat zprávu..."
              placeholderTextColor={colors.secondaryText}
              value={messageInput}
              onChangeText={setMessageInput}
            />
            <TouchableOpacity style={styles.sendMsgBtn} onPress={handleSendMessage}>
              <Feather name="send" size={16} color="#ffffff" />
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      )}
    </SafeAreaView>
  );
}

const getStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  mainChatList: {
    flex: 1,
  },
  header: {
    paddingHorizontal: 16,
    paddingTop: 10,
    paddingBottom: 10,
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: colors.text,
    letterSpacing: -0.3,
  },
  searchBar: {
    marginHorizontal: 16,
    marginBottom: 12,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: colors.pillBg,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  searchInput: {
    flex: 1,
    fontSize: 14,
    color: colors.text,
    padding: 0,
  },
  chatListContent: {
    flex: 1,
  },
  chatRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  groupAvatar: {
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: colors.pillBg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  userAvatar: {
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: colors.secondaryBg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  chatRowInfo: {
    flex: 1,
  },
  chatRowName: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 2,
  },
  chatRowMsg: {
    fontSize: 13,
    color: colors.secondaryText,
  },
  conversationContainer: {
    flex: 1,
    backgroundColor: colors.background,
  },
  convHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderBottomWidth: 0.5,
    borderBottomColor: colors.border,
    gap: 8,
  },
  backBtn: {
    padding: 4,
  },
  convHeaderTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.text,
  },
  messagesBox: {
    flex: 1,
  },
  messagesContent: {
    padding: 16,
    gap: 10,
  },
  msgBubbleWrapper: {
    flexDirection: 'column',
    maxWidth: '80%',
  },
  alignMe: {
    alignSelf: 'flex-end',
  },
  alignOther: {
    alignSelf: 'flex-start',
  },
  authorLabel: {
    fontSize: 11,
    color: colors.secondaryText,
    fontWeight: '500',
    marginBottom: 3,
    marginLeft: 6,
  },
  textBubble: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 20,
  },
  bubbleMe: {
    backgroundColor: colors.blue,
    borderBottomRightRadius: 4,
  },
  bubbleOther: {
    backgroundColor: colors.pillBg,
    borderBottomLeftRadius: 4,
  },
  bubbleText: {
    fontSize: 14,
    lineHeight: 19,
  },
  bubbleTextMe: {
    color: '#ffffff',
  },
  bubbleTextOther: {
    color: colors.text,
  },
  sharedCardRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  reelShareCard: {
    width: 145,
    height: 257, // 9:16 aspect ratio
    borderRadius: 14,
    overflow: 'hidden',
    position: 'relative',
    backgroundColor: '#111111',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 10,
    elevation: 6,
  },
  reelShareImg: {
    width: '100%',
    height: '100%',
  },
  reelShareOverlay: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    padding: 8,
    backgroundColor: 'rgba(0,0,0,0.65)',
  },
  reelShareName: {
    color: '#ffffff',
    fontSize: 12,
    fontWeight: '700',
  },
  reelShareDist: {
    color: 'rgba(255,255,255,0.8)',
    fontSize: 10,
    marginTop: 1,
  },
  cardActions: {
    flexDirection: 'column',
    gap: 8,
  },
  circleActionBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.pillBg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderTopWidth: 0.5,
    borderTopColor: colors.border,
    gap: 8,
  },
  msgInput: {
    flex: 1,
    backgroundColor: colors.secondaryBg,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 22,
    paddingHorizontal: 16,
    paddingVertical: 9,
    fontSize: 14,
    color: colors.text,
  },
  sendMsgBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: '#0095f6',
    alignItems: 'center',
    justifyContent: 'center',
  },
});
