"use client";

import React, { useState } from "react";
// Using lucide-react for professional icons
import { Mail, ArrowLeft, CheckCircle, AlertTriangle } from 'lucide-react';

// --- Interface Definitions ---
interface MessageProps {
  message: string;
  type: 'error' | 'success';
}

// --- Component for Displaying Messages (Error or Success) ---
const StatusMessage: React.FC<MessageProps> = ({ message, type }) => {
  const isError = type === 'error';
  const bgColor = isError ? 'bg-red-100' : 'bg-green-100';
  const textColor = isError ? 'text-red-800' : 'text-green-800';
  const borderColor = isError ? 'border-red-300' : 'border-green-300';
  const Icon = isError ? AlertTriangle : CheckCircle;
  const iconColor = isError ? 'text-red-600' : 'text-green-600';

  return (
    <div className={`flex items-center p-3 mb-4 text-sm font-medium ${textColor} ${bgColor} rounded-lg shadow-md border ${borderColor}`}>
      <Icon className={`w-5 h-5 mr-2 shrink-0 ${iconColor}`} />
      <span>{message}</span>
    </div>
  );
};


export default function ForgotPassword(): JSX.Element {
  const [email, setEmail] = useState<string>("");
  const [statusMessage, setStatusMessage] = useState<{ message: string; type: 'error' | 'success' } | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // Note: I removed the username field from the UI as modern password resets usually rely solely on email address.
  // If you need it, we can easily add it back!

  const handlePasswordReset = (e: React.FormEvent) => {
    e.preventDefault();
    setStatusMessage(null);
    
    if (!email) {
      setStatusMessage({ message: "Please enter your email address.", type: 'error' });
      return;
    }
    
    setIsLoading(true);

    // Simulate API call for sending reset link
    setTimeout(() => {
      setIsLoading(false);
      // In a real application, you would make an asynchronous API call here.
      
      const success = Math.random() > 0.1; // Simulate occasional failure for demonstration

      if (success) {
        setStatusMessage({
          message: `A password reset link has been sent to ${email}. Please check your inbox.`,
          type: 'success'
        });
      } else {
        setStatusMessage({
          message: "Failed to send reset link. Please check the email address and try again.",
          type: 'error'
        });
      }
      // Clear email input after submission attempt
      setEmail("");
    }, 1500); 
  };

  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center p-4 sm:p-6 font-sans">
      <div className="bg-white shadow-2xl rounded-xl p-6 sm:p-8 w-full max-w-md border border-gray-200">

        <h1 className="text-sm font-medium text-gray-500 mb-1">
          Social Sentiment Pricing
        </h1>
        <h2 className="text-3xl font-extrabold text-gray-900 mb-6">
          Forgot Password?
        </h2>
        <p className="text-gray-600 mb-6 text-sm">
          Enter the email address associated with your account and we'll send you a link to reset your password.
        </p>

        {statusMessage && <StatusMessage message={statusMessage.message} type={statusMessage.type} />}

        <form onSubmit={handlePasswordReset} className="space-y-5">
          
          {/* Email Input */}
          <div className="relative">
            <label htmlFor="email-input" className="block text-sm text-gray-700 font-medium mb-1">Email Address</label>
            <div className="flex items-center border border-gray-300 rounded-lg focus-within:ring-2 focus-within:ring-blue-500 transition-shadow">
              <Mail className="w-5 h-5 text-gray-400 ml-3 shrink-0" />
              <input
                id="email-input"
                type="email"
                required
                className="w-full px-3 py-3 bg-white rounded-r-lg focus:outline-none placeholder-gray-400"
                placeholder="Enter your email"
                value={email}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEmail(e.target.value)}
                disabled={isLoading}
              />
            </div>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            className="w-full py-3 bg-blue-600 text-white rounded-lg font-bold hover:bg-blue-700 transition duration-200 shadow-lg shadow-blue-500/50 flex items-center justify-center space-x-2 disabled:opacity-50"
            disabled={isLoading}
          >
            {isLoading ? (
              <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            ) : (
              <span>Send Reset Link</span>
            )}
          </button>
        </form>

        {/* Back to Login Button/Link */}
        <p className="text-center text-gray-600 mt-6 text-sm">
          <a 
            href="/login" 
            className="text-gray-600 hover:text-blue-600 font-medium transition duration-200 inline-flex items-center"
          >
            <ArrowLeft className="w-4 h-4 mr-1" />
            Back to Log in
          </a>
        </p>
      </div>
    </div>
  );
}