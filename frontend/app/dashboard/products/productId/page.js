
import Link from 'next/link';

const StatCard = ({ title, value, detail, icon, color }) => (
    <div className="bg-white p-5 rounded-lg shadow-sm flex-grow border border-gray-200">
        <div className="flex justify-between items-start">
            <div>
                <p className="text-sm font-medium text-gray-500">{title}</p>
                <p className="text-3xl font-bold text-gray-900 mt-1">{value}</p>
            </div>
            <div className={`p-2 rounded-full ${color} bg-opacity-30`}>
                <span className="text-xl">{icon}</span>
            </div>
        </div>
        {detail && (
            <p className="mt-2 text-xs font-medium text-green-600 flex items-center">
                <span className="mr-1">▲</span> {detail}
            </p>
        )}
    </div>
);

const CorrelationGraph = ({ title, dataPoints1, dataPoints2, labels = [] }) => {
    
    const maxVal1 = Math.max(...dataPoints1);
    const minVal1 = Math.min(...dataPoints1);
    const range1 = maxVal1 - minVal1;

    const maxVal2 = Math.max(...dataPoints2);
    const minVal2 = Math.min(...dataPoints2);
    const range2 = maxVal2 - minVal2;

    return (
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200 flex flex-col h-full">
            <h2 className="text-xl font-semibold text-gray-800 mb-4">{title}</h2>
            <div className="flex-grow relative h-48">
                {/* Y-Axis 1 Labels (Left) */}
                <div className="absolute left-0 top-0 bottom-0 flex flex-col justify-between text-xs text-gray-500 pr-2">
                    <span>{maxVal1}</span>
                    <span>{Math.round(maxVal1 - range1 / 2)}</span>
                    <span>{minVal1}</span>
                </div>
                {/* Y-Axis 2 Labels (Right) */}
                <div className="absolute right-0 top-0 bottom-0 flex flex-col justify-between text-xs text-gray-500 pl-2">
                    <span>{maxVal2}</span>
                    <span>{Math.round(maxVal2 - range2 / 2)}</span>
                    <span>{minVal2}</span>
                </div>

                <div className="absolute left-8 right-8 bottom-0 top-0">
                     {/* X-Axis Labels */}
                    <div className="absolute bottom-0 left-0 right-0 flex justify-between text-xs text-gray-500 pt-2">
                        {labels.map((label, i) => (
                            <span key={i} className="text-[10px] sm:text-xs text-gray-500 mx-1">{label}</span>
                        ))}
                    </div>

                    <svg className="w-full h-full absolute" viewBox="0 0 100 100" preserveAspectRatio="none">
                        {/* Grid Lines */}
                        <line x1="0" y1="100" x2="100" y2="100" stroke="#e0e0e0" strokeWidth="0.5"/>
                        <line x1="0" y1="50" x2="100" y2="50" stroke="#e0e0e0" strokeDasharray="2 2" strokeWidth="0.5"/>
                        
                        {/* Line 1 (Price - Blue) */}
                        <polyline
                            fill="none"
                            stroke="#3b82f6" 
                            strokeWidth="3"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            points={dataPoints1.map((val, i) =>
                                `${(i / (dataPoints1.length - 1)) * 100},${100 - ((val - minVal1) / range1) * 90 - 5}`
                            ).join(' ')}
                        />
                        {/* Line 2 (Sentiment - Green) */}
                        <polyline
                            fill="none"
                            stroke="#10b981" 
                            strokeWidth="3"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            points={dataPoints2.map((val, i) =>
                                `${(i / (dataPoints2.length - 1)) * 100},${100 - ((val - minVal2) / range2) * 90 - 5}`
                            ).join(' ')}
                        />
                    </svg>
                </div>
            </div>
        </div>
    );
};


// --- Product Detail Page Component ---
export default function ProductDetailPage({ params }) {
    const { productId } = params;

    // --- Placeholder Product Data ---
    const productData = {
        id: productId,
        name: 'Premium Headphones',
        sku: 'PRD-001',
        lastUpdated: '2 hours ago',
        currentPrice: 299,
        sentimentScore: '88%',
        competitorAvg: 315,
        monthlyRevenue: 24500,
        category: 'Audio & Headphones',
        stockStatus: 'In Stock (234 units)',
        lastPriceChange: '15 days ago',
        totalMentions: '1,247 mentions (last 30 days)',
        mentions: [
            { source: 'Twitter', score: '95%', text: 'These headphones are amazing! Best purchase this year.', time: '2 hours ago' },
            { source: 'Reddit', score: '72%', text: 'Sound quality is excellent but price is a bit high.', time: '5 hours ago' },
            { source: 'Twitter', score: '98%', text: 'Worth every penny. Noise cancellation is top-notch!', time: '8 hours ago' },
        ],
        // Graph data
        priceHistory: [280, 290, 300, 295, 305, 310], 
        sentimentHistory: [70, 75, 78, 82, 85, 88], 
        graphLabels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
    };

    return (
        <div className="bg-gray-100 min-h-screen">
            <main className="flex-1 p-4 sm:p-6 md:p-8 max-w-7xl mx-auto"> 
                
                {/* 1. Back to Products & Edit Button */}
                <div className="flex justify-between items-center mb-6 pt-4"> {/* Added pt-4 for top spacing */}
                    <Link href="/dashboard/products" className="text-blue-600 hover:text-blue-800 flex items-center transition-colors font-medium">
                        <span className="mr-2 text-xl">←</span> Go back to Products
                    </Link>
                    <button className="bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded-lg shadow transition-colors duration-200">
                        Edit Product
                    </button>
                </div>

                {/* 2. Product Header */}
                <div className="mb-8 border-b pb-4">
                    <h1 className="text-3xl font-bold text-gray-900 mb-1">{productData.name}</h1>
                    <p className="text-gray-600 text-sm">SKU: {productData.sku} • Last updated {productData.lastUpdated}</p>
                </div>

                {/* 3. Top Stat Cards (Responsive) */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                    <StatCard
                        title="Current Price"
                        value={`$${productData.currentPrice}`}
                        detail="No change" 
                        icon="$"
                        color="text-blue-600"
                    />
                    <StatCard
                        title="Sentiment Score"
                        value={productData.sentimentScore}
                        detail="+3% this week" 
                        icon="📈"
                        color="text-green-600"
                    />
                    <StatCard
                        title="Competitor Avg"
                        value={`$${productData.competitorAvg}`}
                        detail="$15 below average" 
                        icon="📊"
                        color="text-blue-600"
                    />
                    <StatCard
                        title="Monthly Revenue"
                        value={`$${(productData.monthlyRevenue / 1000).toFixed(1)}K`}
                        detail="+12% vs last month" 
                        icon="💵"
                        color="text-green-600"
                    />
                </div>

                {/* 4. Price & Sentiment Correlation Graph */}
                <div className="mb-8">
                    <CorrelationGraph
                        title="Price & Sentiment Correlation"
                        dataPoints1={productData.priceHistory}
                        dataPoints2={productData.sentimentHistory}
                        labels={productData.graphLabels}
                    />
                </div>

                {/* 5. Product Information & Recent Mentions (Responsive) */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
                    {/* Product Information Card */}
                    <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
                        <h2 className="text-xl font-semibold text-gray-800 mb-4">Product Information</h2>
                        <div className="space-y-2 text-gray-700">
                            <div><span className="font-medium">Category:</span> {productData.category}</div>
                            <div><span className="font-medium">Stock Status:</span> {productData.stockStatus}</div>
                            <div><span className="font-medium">Last Price Change:</span> {productData.lastPriceChange}</div>
                            <div><span className="font-medium">Total Mentions:</span> {productData.totalMentions}</div>
                        </div>
                    </div>

                    {/* Recent Mentions Card */}
                    <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
                        <h2 className="text-xl font-semibold text-gray-800 mb-4">Recent Mentions</h2>
                        <div className="space-y-4 max-h-72 overflow-y-auto pr-2"> {/* Added max height and scroll for content */}
                            {productData.mentions.map((mention, index) => (
                                <div key={index} className="border-b border-gray-100 pb-4 last:border-b-0 last:pb-0">
                                    <div className="flex justify-between items-start text-sm mb-1">
                                        <span className="font-medium text-blue-600">{mention.source}</span>
                                        <span className="font-semibold text-green-600">{mention.score}</span>
                                    </div>
                                    <p className="text-gray-800 text-sm mb-1">{mention.text}</p>
                                    <p className="text-gray-500 text-xs">{mention.time}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}