// Settings Page - Redirects to profile
import { redirect } from 'next/navigation';

export default function SettingsPage() {
  redirect('/settings/profile');
}
