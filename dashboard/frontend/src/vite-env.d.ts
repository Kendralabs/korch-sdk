/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  readonly VITE_BEDROCK_MODEL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
