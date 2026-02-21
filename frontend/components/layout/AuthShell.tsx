// AuthShell Component
// Wraps login/register pages with centered card layout

interface AuthShellProps {
  children: React.ReactNode;  // Form content goes here
}

export function AuthShell({ children }: AuthShellProps) {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      {/* Centered container */}
      <div className="w-full max-w-md">
        {/* Logo / Brand */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 bg-blue-600 rounded-xl mb-4">
            <span className="text-white font-bold text-lg">AP</span>
          </div>
          <h1 className="text-2xl font-semibold text-gray-900">
            ActualPrice
          </h1>
          <p className="mt-2 text-sm text-gray-500">
            AI-powered pricing optimization for e-commerce
          </p>
        </div>

        {/* Card with form content */}
        <div className="bg-white rounded-xl border border-gray-200 p-8">
          {children}
        </div>
      </div>
    </div>
  );
}

