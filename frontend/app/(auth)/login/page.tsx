
"use client";

import { useState, FormEvent, ChangeEvent } from "react";
import Link from "next/link";

export default function LoginPage(): JSX.Element {
  // Explicitly defining the type for state variables as string
  const [email, setEmail] = useState<string>("");
  const [password, setPassword] = useState<string>("");

  // Explicitly defining the type for the event object (FormEvent)
  const handleLogin = (e: FormEvent) => {
    e.preventDefault();
    // 🎯 Integration Point: Authenticate user here
    console.log("Attempting login with Email:", email);
    // verify credentials and redirect.
    //  router.push('/dashboard'); 
  };

  // Explicitly defining the type for the change event
  const handleEmailChange = (e: ChangeEvent<HTMLInputElement>) => {
    setEmail(e.target.value);
  };

  const handlePasswordChange = (e: ChangeEvent<HTMLInputElement>) => {
    setPassword(e.target.value);
  };

  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center p-5">
      <div className="bg-white shadow-2xl rounded-xl p-8 w-full max-w-md border border-gray-200">
        
        <h1 className="text-1xl text-black mb-5">Social sentiment pricing</h1>
        <h2 className="text-3xl font-bold text-left text-black mb-6">Log In</h2>

        <form onSubmit={handleLogin} className="space-y-5">

          {/* Email */}
          <div>
            <label className="block text-gray-700 font-medium mb-1">
              Email Address
            </label>
            <input
              type="email"
              required
              placeholder="Enter your email"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
              value={email}
              onChange={handleEmailChange}
            />
          </div>

          {/* Password */}
          <div>
            <label className="block text-gray-700 font-medium mb-1">
              Password
            </label>
            <input
              type="password"
              required
              placeholder="Enter your password"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
              value={password}
              onChange={handlePasswordChange}
            />

            {/* Forgot Password link (right side) */}
            <div className="text-right mt-1">
              <Link
                href="/dashboard/forgotpass"
                className="text-blue-600 hover:underline text-sm"
              >
                Forgot Password?
              </Link>
            </div>

          </div>

          {/* Login Button */}
          <button
            type="submit"
            className="w-full py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition duration-200 shadow-md"
          >
            Login
           
          </button>
        </form>

        {/* Sign up link */}
        <p className="text-center text-gray-600 mt-5">
          Don't have an account?{" "}
          <Link href="/register" className="text-blue-600 font-semibold hover:underline">
            Sign up
          </Link>
        </p>

      </div>
    </div>
  );
}