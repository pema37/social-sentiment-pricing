// app/products/page.tsx
import React from 'react';
import Link from 'next/link';

// --- 1. INTERFACE DEFINITIONS ---

interface Product {
    name: string;
    sku: string;
    price: number;
    sentiment: string;
    stock: 'In Stock' | 'Low Stock' | 'Out of Stock';
    stockColor: string;
}

// --- 2. MAIN PAGE COMPONENT (NO SIDEBAR) ---

export default function ProductsPage(): JSX.Element {
    const products: Product[] = [
        { name: 'Premium Headphones', sku: 'PRD-001', price: 299, sentiment: '88%', stock: 'In Stock', stockColor: 'text-green-600 bg-green-100' },
        { name: 'Wireless Earbuds', sku: 'PRD-002', price: 129, sentiment: '92%', stock: 'In Stock', stockColor: 'text-green-600 bg-green-100' },
        { name: 'Smart Watch Pro', sku: 'PRD-003', price: 399, sentiment: '65%', stock: 'Low Stock', stockColor: 'text-orange-600 bg-orange-100' },
        { name: 'Fitness Tracker', sku: 'PRD-004', price: 89, sentiment: '95%', stock: 'In Stock', stockColor: 'text-green-600 bg-green-100' },
        { name: 'Bluetooth Speaker', sku: 'PRD-005', price: 159, sentiment: '78%', stock: 'In Stock', stockColor: 'text-green-600 bg-green-100' },
        { name: 'USB-C Hub', sku: 'PRD-006', price: 49, sentiment: '82%', stock: 'In Stock', stockColor: 'text-green-600 bg-green-100' },
        { name: 'Laptop Stand', sku: 'PRD-007', price: 79, sentiment: '71%', stock: 'Out of Stock', stockColor: 'text-red-600 bg-red-100' },
        { name: 'Wireless Charger', sku: 'PRD-008', price: 39, sentiment: '86%', stock: 'In Stock', stockColor: 'text-green-600 bg-green-100' },
    ];

    return (
        <div className="bg-gray-100 min-h-screen">

            {/* Header */}
            <header className="bg-blue-700 text-white p-4 shadow-md flex justify-between items-center px-8">
                <h1 className="text-2xl font-bold">Products</h1>
                <Link href="/products/add" passHref legacyBehavior>
                    <a className="bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded-lg shadow transition-colors duration-200 flex items-center">
                        <span className="text-xl mr-2">+</span> Add Product
                    </a>
                </Link>
            </header>

            <div className="p-4 sm:p-6 md:p-8">
                <p className="text-gray-600 mb-6">Manage your product catalog and pricing</p>

                {/* Search Bar */}
                <div className="mb-6">
                    <div className="relative flex items-center">
                        <input
                            type="text"
                            placeholder="Search products..."
                            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500 text-gray-900"
                        />
                        <span className="absolute left-3 text-gray-400">🔍</span>
                    </div>
                </div>

                {/* Products Table */}
                <div className="bg-white p-4 sm:p-6 rounded-lg shadow-sm border border-gray-200 overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                            <tr>
                                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Product Name</th>
                                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">SKU</th>
                                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Price</th>
                                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Sentiment</th>
                                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Stock Status</th>
                                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                            {products.map((product, index) => (
                                <tr key={index}>
                                    <td className="px-3 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{product.name}</td>
                                    <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-500">{product.sku}</td>
                                    <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-500">${product.price}</td>
                                    <td className="px-3 py-4 whitespace-nowrap text-sm">
                                        <span className="flex items-center">
                                            {product.sentiment} <span className="ml-1 text-green-500">↗️</span>
                                        </span>
                                    </td>
                                    <td className="px-3 py-4 whitespace-nowrap text-sm">
                                        <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${product.stockColor}`}>
                                            {product.stock}
                                        </span>
                                    </td>
                                    <td className="px-3 py-4 whitespace-nowrap text-sm">
                                        <Link href={`/products/${product.sku}`} passHref legacyBehavior>
                                            <a className="bg-gray-200 hover:bg-gray-300 text-gray-700 font-medium py-1 px-3 rounded-md transition-colors text-xs flex items-center">
                                                <span className="mr-1">👁️</span> View
                                            </a>
                                        </Link>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

        </div>
    );
}
