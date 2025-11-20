
import React from 'react';
import Link from 'next/link'; 
//import ViewAllLink from '@/components/ViewAllLink'; 


const Sidebar = () => (
    <div className="flex flex-col w-64 bg-gray-900 text-white min-h-screen p-4 shadow-lg">
        <div className="text-xl font-extrabold mb-8 flex items-center">
            <span className="text-blue-400 mr-2">SSP</span> Social Sentiment
        </div>
        <nav className="space-y-2">
            {[
                { name: 'Dashboard', icon: '🏠', active: false, href: '/dashboard' },
                { name: 'Products', icon: '📦', active: true, href: '/products' }, // Active for this page
                { name: 'Competitors', icon: '🤝', active: false, href: '/competitors' },
                { name: 'Sentiment', icon: '📈', active: false, href: '/sentiment' },
                { name: 'Price Suggestions', icon: '$', active: false, href: '/price-suggestions' },
                { name: 'Settings', icon: '⚙️', active: false, href: '/settings' },
                { name: 'API Keys', icon: '🔑', active: false, href: '/api-keys' },
                { name: 'Admin', icon: '👤', active: false, href: '/admin' },
            ].map((item) => (
                <Link
                    key={item.name}
                    href={item.href}
                    className={`flex items-center p-2 rounded-lg transition-colors duration-200 ${
                        item.active
                            ? 'bg-blue-600 text-white shadow-md'
                            : 'hover:bg-gray-700 text-gray-300'
                    }`}
                >
                    <span className="text-xl mr-3">{item.icon}</span>
                    <span className="font-medium">{item.name}</span>
                </Link>
            ))}
        </nav>
    </div>
);

export default function ProductsPage() {
    const products = [
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
        <div className="flex bg-gray-100 min-h-screen">
            <Sidebar />
            <main className="flex-1">
                {/* Top Bar (Blue) - Re-using style from Dashboard */}
                <header className="bg-blue-700 text-white p-4 shadow-md flex justify-between items-center px-8">
                    <h1 className="text-2xl font-bold">Products</h1>
                    <button className="bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded-lg shadow transition-colors duration-200 flex items-center">
                        <span className="text-xl mr-2">+</span> Add Product
                    </button>
                </header>

                <div className="p-4 sm:p-6 md:p-8"> {/* Responsive padding */}
                    <p className="text-gray-600 mb-6">Manage your product catalog and pricing</p>

                    {/* Search Bar */}
                    <div className="mb-6">
                        <div className="relative flex items-center">
                            <input
                                type="text"
                                placeholder="Search products..."
                                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500 text-gray-900"
                            />
                            <span className="absolute left-3 text-gray-400">
                                {/* Search Icon (you might use an actual SVG icon library here) */}
                                🔍
                            </span>
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
                                                {product.sentiment} <span className="ml-1 text-green-500">↗️</span> {/* Placeholder trend icon */}
                                            </span>
                                        </td>
                                        <td className="px-3 py-4 whitespace-nowrap text-sm">
                                            <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${product.stockColor}`}>
                                                {product.stock}
                                            </span>
                                        </td>
                                        <td className="px-3 py-4 whitespace-nowrap text-sm">
                                            <button className="bg-gray-200 hover:bg-gray-300 text-gray-700 font-medium py-1 px-3 rounded-md transition-colors text-xs flex items-center">
                                                <span className="mr-1">👁️</span> View
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </main>
        </div>
    );
}