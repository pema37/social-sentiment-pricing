// Button Component
// Reusable button with multiple variants and sizes

import { cn } from '@/lib/utils';
import { ButtonHTMLAttributes, forwardRef } from 'react';

// Button variants - matches our design system
const variants = {
  // Primary blue button
  primary: 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500',
  // White button with border
  secondary: 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50 focus:ring-blue-500',
  // Transparent button
  ghost: 'bg-transparent text-blue-600 hover:bg-blue-50 focus:ring-blue-500',
  // Red button for destructive actions
  danger: 'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500',
};

// Button sizes
const sizes = {
  sm: 'px-3 py-1.5 text-sm',        // Small
  md: 'px-4 py-2 text-sm',          // Medium (default)
  lg: 'px-5 py-3 text-base',        // Large
};

// TypeScript interface for Button props
interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof variants;  // primary, secondary, ghost, danger
  size?: keyof typeof sizes;        // sm, md, lg
  isLoading?: boolean;              // Show loading spinner
}

// forwardRef allows parent components to get a ref to the button element
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ 
    className, 
    variant = 'primary', 
    size = 'md', 
    isLoading = false,
    disabled,
    children, 
    ...props 
  }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(
          // Base styles (always applied)
          'inline-flex items-center justify-center font-medium rounded-lg',
          'transition-all duration-200 ease-in-out',
          'focus:outline-none focus:ring-2 focus:ring-offset-2',
          // Disabled styles
          'disabled:opacity-50 disabled:cursor-not-allowed',
          // Variant styles (primary, secondary, etc.)
          variants[variant],
          // Size styles (sm, md, lg)
          sizes[size],
          // Custom className from props
          className
        )}
        {...props}
      >
        {/* Loading spinner */}
        {isLoading && (
          <svg
            className="animate-spin -ml-1 mr-2 h-4 w-4"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
        )}
        {children}
      </button>
    );
  }
);

// Display name for React DevTools
Button.displayName = 'Button';
