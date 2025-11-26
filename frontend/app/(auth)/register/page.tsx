"use client";

import React, { useState } from "react";
import { User, Mail, Lock, CheckCircle, AlertTriangle } from 'lucide-react';


interface ErrorMessageProps {
  message: string;
  onClose: () => void;
}

// --- Component for Displaying Errors (Replaces alert()) ---
const ErrorMessage: React.FC<ErrorMessageProps> = ({ message, onClose }) => (
  <div className="flex items-center justify-between p-3 mb-4 text-sm font-medium text-red-800 bg-red-100 rounded-lg shadow-md border border-red-300">
    <div className="flex items-center">
      <AlertTriangle className="w-5 h-5 mr-2 text-red-600" />
      <span>{message}</span>
    </div>
    <button
      onClick={onClose}
      className="p-1 rounded-full text-red-600 hover:bg-red-200 transition-colors"
      aria-label="Close alert"
    >
      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
      </svg>
    </button>
  </div>
);

// FIX: Removed explicit ': JSX.Element' return type annotation.
export default function SignupPage() {
  // State Initialization with explicit types
  const [fullName, setFullName] = useState<string>("");
  const [email, setEmail] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [confirmPassword, setConfirmPassword] = useState<string>("");
  const [agreeTerms, setAgreeTerms] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSignup = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null); // Clear previous errors

    if (!agreeTerms) {
      setErrorMessage("Please agree to the Terms & Conditions before signing up.");
      return;
    }

    if (password !== confirmPassword) {
      setErrorMessage("Passwords do not match!");
      return;
    }

    // Password complexity check 
    if (password.length < 8) {
      setErrorMessage("Password must be at least 8 characters long.");
      return;
    }

    // Success logic placeholder
    console.log("Signup successful!");
    console.log("Full Name:", fullName);
    console.log("Email:", email);
    // In a real app, you would now integrate with Firebase or another auth service
    // e.g., auth.createUserWithEmailAndPassword(email, password);

    // Optionally clear form or redirect after success
    // setFullName(''); setPassword(''); 
  };

  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center p-4 sm:p-6 font-sans">
      <div className="bg-white shadow-2xl rounded-xl p-6 sm:p-8 w-full max-w-md border border-gray-200">

        <h1 className="text-sm font-medium text-gray-500 mb-1">
          Social Sentiment Pricing
        </h1>
        <h2 className="text-3xl font-extrabold text-gray-900 mb-6">
          Create Your Account
        </h2>

        {errorMessage && (
          <ErrorMessage 
            message={errorMessage} 
            onClose={() => setErrorMessage(null)} 
          />
        )}

        <form onSubmit={handleSignup} className="space-y-5">

          {/* Full Name */}
          <div className="relative">
            <label className="block text-sm text-gray-700 font-medium mb-1">Full Name</label>
            <div className="flex items-center border border-gray-300 rounded-lg focus-within:ring-2 focus-within:ring-blue-500 transition-shadow">
              <User className="w-5 h-5 text-gray-400 ml-3 shrink-0" />
              <input
                type="text"
                required
                className="w-full px-3 py-3 bg-white rounded-r-lg focus:outline-none placeholder-gray-400"
                placeholder="Enter your full name"
                value={fullName}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFullName(e.target.value)}
              />
            </div>
          </div>

          {/* Email */}
          <div className="relative">
            <label className="block text-sm text-gray-700 font-medium mb-1">Email Address</label>
            <div className="flex items-center border border-gray-300 rounded-lg focus-within:ring-2 focus-within:ring-blue-500 transition-shadow">
              <Mail className="w-5 h-5 text-gray-400 ml-3 shrink-0" />
              <input
                type="email"
                required
                className="w-full px-3 py-3 bg-white rounded-r-lg focus:outline-none placeholder-gray-400"
                placeholder="Enter your email"
                value={email}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEmail(e.target.value)}
              />
            </div>
          </div>

          {/* Password */}
          <div className="relative">
            <label className="block text-sm text-gray-700 font-medium mb-1">Password</label>
            <div className="flex items-center border border-gray-300 rounded-lg focus-within:ring-2 focus-within:ring-blue-500 transition-shadow">
              <Lock className="w-5 h-5 text-gray-400 ml-3 shrink-0" />
              <input
                type="password"
                required
                className="w-full px-3 py-3 bg-white rounded-r-lg focus:outline-none placeholder-gray-400"
                placeholder="Enter your password (min 8 chars)"
                value={password}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPassword(e.target.value)}
              />
            </div>
          </div>

          {/* Confirm Password */}
          <div className="relative">
            <label className="block text-sm text-gray-700 font-medium mb-1">Confirm Password</label>
            <div className="flex items-center border border-gray-300 rounded-lg focus-within:ring-2 focus-within:ring-blue-500 transition-shadow">
              <Lock className="w-5 h-5 text-gray-400 ml-3 shrink-0" />
              <input
                type="password"
                required
                className="w-full px-3 py-3 bg-white rounded-r-lg focus:outline-none placeholder-gray-400"
                placeholder="Confirm your password"
                value={confirmPassword}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setConfirmPassword(e.target.value)}
              />
            </div>
          </div>

          {/* Terms & Conditions */}
          <div className="flex items-start gap-3 pt-1">
            <input
              id="agreeTerms"
              type="checkbox"
              className="mt-1 h-5 w-5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              checked={agreeTerms}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setAgreeTerms(e.target.checked)}
            />

            <label htmlFor="agreeTerms" className="text-gray-700 text-sm cursor-pointer">
              I agree to the{" "}
              <a
                href="https://price-segmental-terms-url.com"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 font-semibold hover:underline"
              >
                Terms & Conditions
              </a>
            </label>
          </div>

          {/* Signup Button */}
          <button
            type="submit"
            className="w-full py-3 bg-blue-600 text-white rounded-lg font-bold hover:bg-blue-700 transition duration-200 shadow-lg shadow-blue-500/50 flex items-center justify-center space-x-2 disabled:opacity-50"
            disabled={!agreeTerms}
          >
            <CheckCircle className="w-5 h-5" />
            <span>Sign Up</span>
          </button>
        </form>

        <p className="text-center text-gray-600 mt-6 text-sm">
          Already have an account?{" "}
        
          <a href="/login" className="text-blue-600 font-bold hover:underline">
            Log in
          </a>
        </p>
      </div>
    </div>
  );
}