import React, { useEffect, useRef, useState } from 'react';
import { StyleSheet, Text, View, TouchableOpacity, Dimensions } from 'react-native';
import { useLocalSearchParams, useRouter, Stack } from 'expo-router';
import Animated from 'react-native-reanimated';
import MapView, { PROVIDER_DEFAULT, Polyline, Marker } from 'react-native-maps';

// Načteme dynamicky nagenerovaný seznam GeoJSONů
import { geojsons } from '../../../assets/postupy/geojsons';

const { width, height } = Dimensions.get('window');

export default function PostupDetail() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const mapRef = useRef<MapView>(null);
  
  const [coordinates, setCoordinates] = useState<any[]>([]);
  
  useEffect(() => {
    // Načteme data z lokálního JSON bundlu
    const data = (geojsons as Record<string, any>)[id as string];
    if (data && data.features) {
      // Extrahujeme všechny LineStringy
      const coords: any[] = [];
      data.features.forEach((feature: any) => {
        if (feature.geometry.type === 'LineString') {
          feature.geometry.coordinates.forEach((coord: any) => {
            // GeoJSON má formát [longitude, latitude], react-native-maps potřebuje {latitude, longitude}
            coords.push({
              latitude: coord[1],
              longitude: coord[0],
            });
          });
        }
      });
      setCoordinates(coords);
      
      // Vycentrujeme mapu na tuto trasu po krátkém zpoždění (aby proběhla animace otevření)
      setTimeout(() => {
        if (coords.length > 0 && mapRef.current) {
          mapRef.current.fitToCoordinates(coords, {
            edgePadding: { top: 100, right: 50, bottom: 50, left: 50 },
            animated: true,
          });
        }
      }, 400);
    }
  }, [id]);

  return (
    <View style={styles.container}>
      <Stack.Screen options={{ headerShown: false }} />

      <Animated.View sharedTransitionTag={`postup-${id}`} style={styles.fullscreenPlaceholder}>
        <MapView 
          ref={mapRef}
          style={{ width: '100%', height: '100%' }}
          mapType="hybrid"
          initialRegion={{
            latitude: 49.80, 
            longitude: 15.20,
            latitudeDelta: 1.5,
            longitudeDelta: 1.5,
          }}
        >
          {coordinates.length > 0 && (
            <Polyline
              coordinates={coordinates}
              strokeColor="#ff0055" // Krásná zářivá Instagram barva
              strokeWidth={5}
              lineCap="round"
              lineJoin="round"
            />
          )}
        </MapView>
      </Animated.View>

      <TouchableOpacity 
        style={styles.backButton} 
        onPress={() => router.back()}
        activeOpacity={0.8}
      >
        <Text style={styles.backText}>← Zpět do mřížky</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  fullscreenPlaceholder: {
    width: width,
    height: height,
    backgroundColor: '#222', 
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden', 
  },
  backButton: {
    position: 'absolute',
    top: 50, 
    left: 20,
    backgroundColor: 'rgba(0,0,0,0.6)',
    paddingVertical: 10,
    paddingHorizontal: 15,
    borderRadius: 20,
  },
  backText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
  },
});
