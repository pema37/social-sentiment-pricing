// app/products/add/page.tsx
"use client"; // Forms typically require client-side interaction

import React, { useState, FormEvent, ChangeEvent } from 'react';
import Link from 'next/link';

// --- 1. INTERFACE DEFINITIONS ---

// Define the exact shape of the product data state
interface ProductFormData {
    name: string;
    category: string;
    productUrl: string;
    keywords: string;
}

// --- 2. ADD PRODUCT FORM COMPONENT ---

const AddProductForm: React.FC = () => {
    // Initialize state with the ProductFormData interface
    const [formData, setFormData] = useState<ProductFormData>({
        name: "",
        category: "",
        productUrl: "",
        keywords: "",
    });

    const categories: string[] = [ // Strongly typing the categories array
        "Audio & Headphones",
        "Smart Wearables",
        "Computer Accessories",
        "Mobile Devices",
        "Home Appliances",
    ];

    // Generic change handler for all form fields
    const handleChange = (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const { id, value } = e.target;
        setFormData(prevData => ({
            ...prevData,
            [id]: value, // TypeScript safely handles the id as a key of ProductFormData
        }));
    };

    // Handler for form submission
    const handleSubmit = (e: FormEvent) => {
        e.preventDefault();
        
        console.log("Form submitted. Data to be sent:", formData);

        // 🎯 Integration Point: Send formData to API (e.g., Axios post)
        // If successful: router.push('/products'); 
        // If error: display error message 
    };

    return (
        <div className="bg-white p-6 sm:p-8 rounded-lg shadow-xl border border-gray-200 max-w-lg w-full mx-auto my-12">
            <h1 className="text-2xl font-bold text-gray-900 mb-6">Add Product</h1>

            <form onSubmit={handleSubmit} className="space-y-6">
                
                {/* Product Name */}
                <div>
                    <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">Product name</label>
                    <input
                        type="text"
                        id="name"
                        required
                        className="w-full px-4 py-2 border border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500"
                        placeholder="e.g., Wireless Earbuds X2"
                        value={formData.name}
                        onChange={handleChange}
                    />
                </div>

                {/* Category Dropdown */}
                <div>
                    <label htmlFor="category" className="block text-sm font-medium text-gray-700 mb-1">Category</label>
                    <select
                        id="category"
                        required
                        className="w-full px-4 py-2 border border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500 bg-white"
                        value={formData.category}
                        onChange={handleChange}
                    >
                        <option value="" disabled>Select a category</option>
                        {categories.map((cat) => (
                            <option key={cat} value={cat}>{cat}</option>
                        ))}
                    </select>
                </div>

                {/* Product URL */}
                <div>
                    <label htmlFor="productUrl" className="block text-sm font-medium text-gray-700 mb-1">Product URL</label>
                    <input
                        type="url"
                        id="productUrl"
                        required
                        className="w-full px-4 py-2 border border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500"
                        placeholder="https://example.com/product-link"
                        value={formData.productUrl}
                        onChange={handleChange}
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
                        value={formData.keywords}
                        onChange={handleChange}
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

// --- 3. MAIN PAGE COMPONENT ---

export default function AddProductPage(): JSX.Element {
    return (
        <div className="bg-gray-100 min-h-screen flex items-start justify-center p-4 sm:p-8">
            <AddProductForm />
        </div>
    );
}