import React from 'react';
import Link from 'next/link';


const AddProductForm = () => {
    // Placeholder function for handling form submission
    const handleSubmit = (e) => {
        e.preventDefault();
        //  Integration Point: This is where you would collect the form data
        // and send it to your backend API using fetch or Axios.
        console.log("Form submitted. Sending data to backend...");
        // like ex : router.push('/products'); // Redirect to products list after success
    };

    const categories = [
        "Audio & Headphones",
        "Smart Wearables",
        "Computer Accessories",
        "Mobile Devices",
        "Home Appliances",
    ];

    return (
        <div className="bg-white p-6 sm:p-8 rounded-lg shadow-xl border border-gray-200 max-w-lg w-full mx-auto my-12">
            <h1 className="text-2xl font-bold text-gray-900 mb-6">Add Product</h1>

            <form onSubmit={handleSubmit} className="space-y-6">
                
                {/* Product Name */}
                <div>
                    <label htmlFor="product-name" className="block text-sm font-medium text-gray-700 mb-1">Product name</label>
                    <input
                        type="text"
                        id="product-name"
                        required
                        className="w-full px-4 py-2 border border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500"
                        placeholder="e.g., Wireless Earbuds X2"
                    />
                </div>

                {/* Category Dropdown */}
                <div>
                    <label htmlFor="category" className="block text-sm font-medium text-gray-700 mb-1">Category</label>
                    <select
                        id="category"
                        required
                        className="w-full px-4 py-2 border border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500 bg-white"
                    >
                        <option value="">Select a category</option>
                        {categories.map((cat) => (
                            <option key={cat} value={cat}>{cat}</option>
                        ))}
                    </select>
                </div>

                {/* Product URL */}
                <div>
                    <label htmlFor="product-url" className="block text-sm font-medium text-gray-700 mb-1">Product URL</label>
                    <input
                        type="url"
                        id="product-url"
                        required
                        className="w-full px-4 py-2 border border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500"
                        placeholder="https://example.com/product-link"
                    />
                </div>

                {/* Keywords to track */}
                <div>
                    <label htmlFor="keywords" className="block text-sm font-medium text-gray-700 mb-1">Keywords to track (comma separated)</label>
                    <input
                        type="text"
                        id="keywords"
                        required
                        className="w-full px-4 py-2 border border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500"
                        placeholder="best headphones, headphones review, sound quality"
                    />
                </div>

                {/* Action Buttons */}
                <div className="flex justify-end space-x-4 pt-4">
                    <Link href="/products" passHref legacyBehavior>
                        <a className="px-5 py-2 border border-gray-300 rounded-lg text-gray-700 font-medium hover:bg-gray-50 transition-colors">
                            Cancel
                        </a>
                    </Link>
                    <button
                        type="submit"
                        className="px-5 py-2 bg-blue-600 text-white font-medium rounded-lg shadow-md hover:bg-blue-700 transition-colors"
                    >
                        Save
                    </button>
                </div>
            </form>
        </div>
    );
};

// --- Main Page Component ---
export default function AddProductPage() {
    return (
        <div className="bg-gray-100 min-h-screen flex items-start justify-center p-4 sm:p-8">
            <AddProductForm />
        </div>
    );
}