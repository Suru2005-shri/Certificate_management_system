import Keycloak from "keycloak-js";

export const kc = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL ?? "http://localhost:8080",
  realm: import.meta.env.VITE_KEYCLOAK_REALM ?? "college",
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT ?? "portal",
});

let initPromise: Promise<boolean> | null = null;

/** Redirects to the Keycloak login page when not signed in (authorization-code flow with PKCE). Safe to call twice. */
export function initAuth(): Promise<boolean> {
  if (!initPromise) {
    initPromise = kc.init({ onLoad: "login-required", pkceMethod: "S256", checkLoginIframe: false });
  }
  return initPromise;
}

export async function getToken(): Promise<string> {
  await kc.updateToken(30);
  if (!kc.token) throw new Error("Not signed in");
  return kc.token;
}

export const logout = () => kc.logout({ redirectUri: window.location.origin });
export const accountName = () => (kc.tokenParsed as { name?: string } | undefined)?.name ?? "";
