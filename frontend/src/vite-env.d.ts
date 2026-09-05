/// <reference types="vite/client" />

declare module "*.css";

interface ImportMetaEnv {
  readonly VITE_MEDIAPIPE_WASM_URL?: string;
  readonly VITE_FACE_DETECTOR_MODEL_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
