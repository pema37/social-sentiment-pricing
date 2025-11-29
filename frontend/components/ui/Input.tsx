// Input Component
// Reusable text input with label and error states

import { cn } from '@/lib/utils';
import { InputHTMLAttributes, forwardRef } from 'react';

// TypeScript interface for Input props
interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;         // Label text above input
  error?: string;         // Error message below input
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, id, ...props }, ref) => {
    return (
      <div className="w-full">
        {/* Label */}
        {label && (
          <label
            htmlFor={id}
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            {label}
          </label>
        )}
        
        {/* Input field */}
        <input
          ref={ref}
          id={id}
          className={cn(
            // Base styles
            'w-full h-11 px-3 rounded-lg text-base',
            'border bg-white text-gray-900',
            'placeholder:text-gray-400',
            'transition-all duration-200 ease-in-out',
            // Focus styles
            'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            // Disabled styles
            'disabled:bg-gray-100 disabled:text-gray-500 disabled:cursor-not-allowed',
            // Error styles
            error
              ? 'border-red-500 focus:ring-red-500 focus:border-red-500'
              : 'border-gray-300',
            // Custom className
            className
          )}
          {...props}
        />
        
        {/* Error message */}
        {error && (
          <p className="mt-1 text-sm text-red-600">{error}</p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
