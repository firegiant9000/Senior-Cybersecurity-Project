import { initializeApp } from "firebase/app";
import { connectAuthEmulator, getAuth } from "firebase/auth";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);

// Local development only (docker-compose.emulator.yml). DEV is false in
// `vite build`, so production bundles never connect to an emulator.
const emulatorUrl = import.meta.env.VITE_FIREBASE_AUTH_EMULATOR_URL;
if (import.meta.env.DEV && emulatorUrl) {
  const { hostname } = new URL(emulatorUrl);
  if (hostname !== "localhost" && hostname !== "127.0.0.1") {
    throw new Error("Auth emulator URL must be localhost");
  }
  connectAuthEmulator(auth, emulatorUrl, { disableWarnings: true });
}
