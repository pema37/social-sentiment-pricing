// frontend/middleware.ts

/**
 * Server-side auth guard
 *
 * Prevents the "flash of unauthorized content" — where unauthenticated users
 * briefly see the dashboard before the client-side redirect kicks in.
 *
 * How it works:
 * - On login, token.ts sets a cookie flag `ssp_auth=1` alongside the
 *   localStorage JWT. This cookie contains no sensitive data — it's just
 *   a hint that the user has logged in.
 * - This middleware runs server-side before any page renders. It checks
 *   for the cookie and redirects to /login if missing.
 * - The actual JWT validation still happens client-side in the Zustand
 *   auth store (layout.tsx DashboardAuthGate). If someone fakes the
 *   cookie, they'll pass middleware but fail client-side auth.
 *
 * Shopify embedded apps skip this entirely — they use App Bridge session
 * tokens, not cookies or localStorage. The matcher config below excludes
 * the Shopify auth callback routes.
 *
 * FIXED (2026-03-08): /integrations/claim is a public route — it handles
 * its own auth after the Shopify install flow. Middleware must not block it.
 */

import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// Routes that don't require authentication
const PUBLIC_ROUTES = [
  '/login',
  '/register',
  '/forgot-password',
  '/reset-password',
  '/auth/callback',
  '/api/shopify',
  '/api/auth',
  '/integrations/claim', // Shopify post-install claim flow — handles own auth
];

function isPublicRoute(pathname: string): boolean {
  return PUBLIC_ROUTES.some(route => pathname.startsWith(route));
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip middleware for public routes
  if (isPublicRoute(pathname)) {
    // If user IS authenticated and hits /login, redirect to dashboard
    const hasAuth = request.cookies.get('ssp_auth')?.value === '1';
    if (hasAuth && pathname === '/login') {
      return NextResponse.redirect(new URL('/dashboard', request.url));
    }
    return NextResponse.next();
  }

  // Check for auth cookie
  const hasAuth = request.cookies.get('ssp_auth')?.value === '1';

  if (!hasAuth) {
    const loginUrl = new URL('/login', request.url);

    // Preserve the full path + search so login can redirect back after auth.
    // Used by the Shopify install flow: after OAuth the backend redirects to
    // /login?redirect=/integrations/claim?integration_id=xxx
    // The login page reads this param and navigates there after auth succeeds.
    const redirectTarget = pathname + request.nextUrl.search;
    loginUrl.searchParams.set('redirect', redirectTarget);

    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)',
  ],
};


