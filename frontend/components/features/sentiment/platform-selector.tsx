'use client';

export type Platform = 'all' | 'twitter' | 'reddit' | 'news' | 'instagram' | 'facebook' | 'youtube' | 'manual';

interface PlatformSelectorProps {
  value: Platform;
  onChange: (platform: Platform) => void;
}

export function PlatformSelector({ value, onChange }: PlatformSelectorProps) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as Platform)}
      className="px-3 py-1.5 text-sm rounded-md border border-gray-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
    >
      <option value="all">All Platforms</option>
      <option value="twitter">Twitter</option>
      <option value="reddit">Reddit</option>
      <option value="news">News</option>
      <option value="instagram">Instagram</option>
      <option value="facebook">Facebook</option>
      <option value="youtube">YouTube</option>
      <option value="manual">Manual</option>
    </select>
  );
}
