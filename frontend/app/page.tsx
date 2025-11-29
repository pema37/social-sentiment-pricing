// Root Page
// Redirects to login page (no landing page for MVP)

import { redirect } from 'next/navigation';

export default function Home() {
  redirect('/login');
}

