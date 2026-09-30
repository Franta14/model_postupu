import { initializeApp, getApps, getApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';
import { getStorage } from 'firebase/storage';

const firebaseConfig = {
  apiKey: "AIzaSyBDlLvcLPqZ3iyy8ugDqHH-KJZa_t0tvgM",
  authDomain: "scrollienteering.firebaseapp.com",
  projectId: "scrollienteering",
  storageBucket: "scrollienteering.firebasestorage.app",
  messagingSenderId: "1062555766603",
  appId: "1:1062555766603:web:be09e089f80bfef04fa2ce",
  measurementId: "G-YE6PPNFZ54"
};

// Initialize Firebase
const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApp();

const auth = getAuth(app);

const db = getFirestore(app);
const storage = getStorage(app);

export { app, auth, db, storage };
