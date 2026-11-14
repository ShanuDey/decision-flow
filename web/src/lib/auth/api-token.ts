import { importPKCS8, SignJWT } from "jose";

export const TOKEN_LIFETIME_SECONDS = 300;
const ALGORITHM = "RS256";

export interface TokenUser {
  id: string;
  email?: string | null;
  emailVerified?: boolean | null;
  name?: string | null;
}

export interface TokenConfig {
  signingKey: string;
  issuer: string;
  audience: string;
}

const keys = new Map<string, Promise<CryptoKey>>();

function privateKey(pem: string): Promise<CryptoKey> {
  let key = keys.get(pem);
  if (!key) {
    key = importPKCS8(pem, ALGORITHM);
    keys.set(pem, key);
  }
  return key;
}

export async function signApiToken(user: TokenUser, config: TokenConfig): Promise<string> {
  const claims: Record<string, unknown> = {};
  if (user.email) {
    claims.email = user.email;
    claims.email_verified = user.emailVerified === true;
  }
  if (user.name) claims.name = user.name;
  return new SignJWT(claims)
    .setProtectedHeader({ alg: ALGORITHM })
    .setSubject(user.id)
    .setIssuer(config.issuer)
    .setAudience(config.audience)
    .setIssuedAt()
    .setExpirationTime(`${TOKEN_LIFETIME_SECONDS}s`)
    .sign(await privateKey(config.signingKey));
}
