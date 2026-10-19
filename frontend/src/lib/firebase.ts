import { initializeApp } from "firebase/app";
import { connectAuthEmulator, getAuth } from "firebase/auth";

/** True once real Firebase project values are present — not the placeholder
 * fallback below. Lets the app boot and show a clear message locally before
 * a Firebase project exists, instead of crashing at import time: getAuth()
 * validates its API key eagerly and throws synchronously on an empty one,
 * which would otherwise blank the whole app before React even mounts. */
export const isFirebaseConfigured = Boolean(
  import.meta.env.VITE_FIREBASE_API_KEY && import.meta.env.VITE_FIREBASE_PROJECT_ID,
);

const firebaseConfig = isFirebaseConfigured
  ? {
      apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
      authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
      projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
      appId: import.meta.env.VITE_FIREBASE_APP_ID,
    }
  : {
      // Non-empty placeholders only — enough for getAuth() to initialise
      // without throwing. Any real sign-in attempt still fails, but as a
      // normal catchable network/auth error at the point of use, not a
      // module-load crash.
      apiKey: "unconfigured",
      authDomain: "unconfigured.firebaseapp.com",
      projectId: "unconfigured",
      appId: "unconfigured",
    };

if (!isFirebaseConfigured) {
  // A console warning, not a thrown error — the login page still needs to
  // render so it can tell the person what's missing, rather than a blank
  // screen.
  console.warn(
    "Firebase is not configured (VITE_FIREBASE_* env vars are missing). " +
      "Sign-in will not work until they are set. See frontend/.env.example.",
  );
}

const app = initializeApp(firebaseConfig);

export const auth = getAuth(app);

const emulatorHost = import.meta.env.VITE_FIREBASE_AUTH_EMULATOR_HOST;
if (emulatorHost) {
  connectAuthEmulator(auth, `http://${emulatorHost}`, { disableWarnings: true });
}
