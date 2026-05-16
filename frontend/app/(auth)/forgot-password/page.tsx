'use client';

// Forgot Password Page
import { useState } from 'react';
import Link from 'next/link';
import { Button, Input } from '@/components/ui';
import { api } from '@/lib/api/client';

export default function ForgotPasswordPage() {
  // Form state
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      await api.post('/api/v1/auth/forgot-password', { email });
      setIsSubmitted(true);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Something went wrong. Please try again.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  // Show success message after submission
  if (isSubmitted) {
    return (
      <div className="text-center">
        <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg
            className="w-6 h-6 text-green-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-gray-900 mb-2">
          Check your email
        </h2>
        <p className="text-sm text-gray-500 mb-6">
          We sent a password reset link to <strong>{email}</strong>
        </p>
        <Link
          href="/login"
          className="text-blue-600 hover:text-blue-700 font-medium text-sm"
        >
          Back to sign in
        </Link>
      </div>
    );
  }

  return (
    <div>
      {/* Page title */}
      <h2 className="text-xl font-semibold text-gray-900 mb-2">
        Forgot your password?
      </h2>
      <p className="text-sm text-gray-500 mb-6">
        Enter your email and we&apos;ll send you a reset link.
      </p>

      {/* Error message */}
      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Forgot password form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          id="email"
          type="email"
          label="Email Address"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          disabled={isLoading}
        />

        {/* Submit button */}
        <Button
          type="submit"
          className="w-full"
          isLoading={isLoading}
          disabled={isLoading}
        >
          {isLoading ? 'Sending...' : 'Send reset link'}
        </Button>
      </form>

      {/* Back to login link */}
      <p className="mt-6 text-center text-sm text-gray-500">
        Remember your password?{' '}
        <Link
          href="/login"
          className="text-blue-600 hover:text-blue-700 font-medium"
        >
          Sign in
        </Link>
      </p>
    </div>
  );
}

