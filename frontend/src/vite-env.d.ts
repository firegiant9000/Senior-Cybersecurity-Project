/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Local dev only: Firebase Auth emulator URL, set by docker-compose.emulator.yml. */
  readonly VITE_FIREBASE_AUTH_EMULATOR_URL?: string;
}
