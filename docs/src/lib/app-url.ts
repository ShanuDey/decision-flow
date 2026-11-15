import { PROD_APP_URL } from "./prod-app-url.mjs";

export const APP_URL: string =
  import.meta.env.PUBLIC_APP_URL ?? (import.meta.env.DEV ? "http://localhost:3000" : PROD_APP_URL);
