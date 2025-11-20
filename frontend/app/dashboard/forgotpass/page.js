export default function ForgotPassword() {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <div className="bg-white p-8 rounded-xl shadow-md w-full max-w-md">
          <h2 className="text-xl font-bold mb-6 text-center">
            Reset Your Password
          </h2>
  
          {/* Username */}
          <input
            type="text"
            placeholder="Enter your username"
            className="w-full mb-4 p-3 border rounded-lg"
          />


          
  
          {/* Email */}
          <input
            type="email"
            placeholder="Enter your email"
            className="w-full mb-4 p-3 border rounded-lg"
          />
  
          {/* Submit Button */}
          <button className="w-full bg-blue-600 text-white py-3 rounded-lg hover:bg-blue-700">
            Send Reset Link
          </button>

          
        </div>
 



      </div>
      
    );
  }
  