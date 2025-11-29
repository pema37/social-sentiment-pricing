// SSP Design System Tokens


export const colors = {
  // Base
  background: {
    light: '#F8F9FB',
    white: '#FFFFFF',
    dark: '#1F2937',
    darkHover: '#374151',
  },
  
  // Borders
  border: {
    default: '#E5E7EB',
    input: '#D1D5DB',
  },
  
  // Text
  text: {
    title: '#111827',
    body: '#374151',
    secondary: '#6B7280',
    placeholder: '#9CA3AF',
    disabled: '#D1D5DB',
    onDark: '#F9FAFB',
  },
  
  // Primary (Blue)
  primary: {
    default: '#2563EB',
    hover: '#1D4ED8',
    light: '#DBEAFE',
    ring: '#3B82F6',
  },
  
  // Status
  success: {
    default: '#10B981',
    light: '#D1FAE5',
    border: '#6EE7B7',
  },
  error: {
    default: '#EF4444',
    light: '#FEE2E2',
    border: '#FCA5A5',
  },
  warning: {
    default: '#F59E0B',
    light: '#FEF3C7',
    border: '#FCD34D',
  },
  neutral: {
    default: '#6B7280',
    light: '#F3F4F6',
    border: '#D1D5DB',
  },
  info: {
    default: '#3B82F6',
    light: '#DBEAFE',
    border: '#93C5FD',
  },
} as const;

export const spacing = {
  xs: '4px',
  sm: '8px',
  md: '12px',
  base: '16px',
  lg: '24px',
  xl: '32px',
  '2xl': '40px',
} as const;

export const radius = {
  sm: '4px',
  md: '6px',
  base: '8px',
  lg: '12px',
  xl: '16px',
  full: '9999px',
} as const;

export const shadows = {
  none: 'none',
  sm: '0 1px 2px 0 rgb(0 0 0 / 0.05)',
  default: '0 1px 3px 0 rgb(0 0 0 / 0.1)',
  md: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
  lg: '0 10px 15px -3px rgb(0 0 0 / 0.1)',
  xl: '0 20px 25px -5px rgb(0 0 0 / 0.1)',
} as const;

export const transitions = {
  fast: 'all 150ms ease-in-out',
  normal: 'all 200ms ease-in-out',
  slow: 'all 300ms ease-in-out',
} as const;

// Layout constants
export const layout = {
  sidebarWidth: '240px',
  topbarHeight: '64px',
  pagePadding: '40px',
  contentMaxWidth: '1280px',
} as const;

