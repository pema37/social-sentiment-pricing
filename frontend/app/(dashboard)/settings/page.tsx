"use client";

import React, { useState, FormEvent } from 'react';
import {
    Settings, User, Bell, Cpu, Repeat, Mail, Globe, BarChart2, MessageSquare, AlertTriangle
} from 'lucide-react';

type Integration = {
    name: string;
    icon: React.ElementType;
    status: string;
    button: string;
    color: string;
};

type ToggleSettings = {
    emailPriceDrop: boolean;
    emailSentimentAlert: boolean;
    inAppPriceDrop: boolean;
    inAppSentimentAlert: boolean;
    digestDaily: boolean;
    digestWeekly: boolean;
};

interface IconProps {
    className?: string;
}


const Lock: React.FC<IconProps> = ({ className }) => (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
        <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
);

interface CardProps {
    title: string;
    children: React.ReactNode;
    icon?: React.ElementType;
    className?: string;
}

const Card: React.FC<CardProps> = ({ title, children, icon: Icon, className = '' }) => (
    <div className={`bg-white p-6 rounded-xl shadow-lg border border-gray-100 ${className}`}>
        <h3 className="text-xl font-semibold text-gray-800 mb-4 flex items-center space-x-2">
            {Icon && <Icon className="w-5 h-5 text-indigo-500" />}
            <span>{title}</span>
        </h3>
        {children}
    </div>
);

interface SectionTitleProps {
    title: string;
    description: string;
}

const SectionTitle: React.FC<SectionTitleProps> = ({ title, description }) => (
    <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">{title}</h2>
        <p className="text-gray-500 mt-1">{description}</p>
    </div>
);

const ProfileSettings: React.FC = () => {
    const handleSubmit = (e: FormEvent) => {
        e.preventDefault();
        console.log("Form section submitted!");
        // Add actual form submission logic here
    };

    return (
        <div className="space-y-8">
                        <Card title="Profile Information" icon={User}>
                <form className="space-y-6" onSubmit={handleSubmit}>
                
                    <div className="flex items-center space-x-4">
                        <div className="w-16 h-16 rounded-full bg-indigo-500/10 text-indigo-500 flex items-center justify-center border border-indigo-200">
                            <User size={30} />
                        </div>
                        <div>
                            <button type="button" className="text-sm font-medium text-indigo-600 hover:text-indigo-800 transition">Change Photo</button>
                            <p className="text-xs text-gray-500 mt-1">JPG, PNG or GIF. Max size 2MB.</p>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <label htmlFor="firstName" className="block text-sm font-medium text-gray-700 mb-1">First Name</label>
                            <input id="firstName" type="text" defaultValue="Mr/Ms .." className="w-full p-3 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500" />
                        </div>
                        <div>
                            <label htmlFor="lastName" className="block text-sm font-medium text-gray-700 mb-1">Last Name</label>
                            <input id="lastName" type="text" defaultValue="Lname" className="w-full p-3 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500" />
                        </div>
                    </div>

                    <div>
                        <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">Email Address</label>
                        <input id="email" type="email" defaultValue="john.doe@company.com" disabled className="w-full p-3 border border-gray-300 rounded-lg bg-gray-50 text-gray-500" />
                    </div>

                    <div>
                        <label htmlFor="phoneNumber" className="block text-sm font-medium text-gray-700 mb-1">Phone Number</label>
                        <input id="phoneNumber" type="tel" defaultValue="+1 (555) 123-4567" className="w-full p-3 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500" />
                    </div>
                    
                    <div className="pt-2">
                        <button type="submit" className="px-5 py-2 bg-indigo-600 text-white rounded-lg shadow-md hover:bg-indigo-700 transition">Save Changes</button>
                    </div>
                </form>
            </Card>

            {/* Company Information Card */}
            <Card title="Company Information" icon={Settings}>
                 <form className="space-y-6" onSubmit={handleSubmit}>
                    <div>
                        <label htmlFor="companyName" className="block text-sm font-medium text-gray-700 mb-1">Company Name</label>
                        <input id="companyName" type="text" defaultValue="Acme Corporation" className="w-full p-3 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500" />
                    </div>
                    <div>
                        <label htmlFor="industry" className="block text-sm font-medium text-gray-700 mb-1">Industry</label>
                        <input id="industry" type="text" placeholder="e.g., E-commerce, SaaS" className="w-full p-3 border border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500" />
                    </div>
                    <div className="pt-2">
                        <button type="submit" className="px-5 py-2 bg-indigo-600 text-white rounded-lg shadow-md hover:bg-indigo-700 transition">Update Company</button>
                    </div>
                </form>
            </Card>

            {/* Danger Zone */}
            <div className="p-6 rounded-xl border-2 border-red-300 bg-red-50">
                <h3 className="text-xl font-semibold text-red-800 mb-2">Danger Zone</h3>
                <p className="text-red-600 mb-4 text-sm">Irreversible actions that affect your account.</p>
                <button type="button" className="px-4 py-2 bg-red-600 text-white rounded-lg shadow-md hover:bg-red-700 transition">
                    Delete Account
                </button>
            </div>
        </div>
    );
};


// Notification Settings


interface ToggleSwitchProps {
    checked: boolean;
    onChange: () => void;
    label: string;
    description: string;
}

const ToggleSwitch: React.FC<ToggleSwitchProps> = ({ checked, onChange, label, description }) => (
    <div className="flex items-center justify-between py-3 border-b border-gray-100 last:border-b-0">
        <div>
            <span className="text-gray-800 font-medium block">{label}</span>
            <span className="text-xs text-gray-500">{description}</span>
        </div>
        <label className="relative inline-flex items-center cursor-pointer">
            <input type="checkbox" checked={checked} onChange={onChange} className="sr-only peer" />
            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-indigo-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
        </label>
    </div>
);

const NotificationSettings: React.FC = () => {
    const [settings, setSettings] = useState<ToggleSettings>({
        emailPriceDrop: true,
        emailSentimentAlert: false,
        inAppPriceDrop: true,
        inAppSentimentAlert: true,
        digestDaily: true,
        digestWeekly: false,
    });

    const handleChange = (key: keyof ToggleSettings) => setSettings(prev => ({ ...prev, [key]: !prev[key] }));

    const handleSubmit = (e: FormEvent) => {
        e.preventDefault();
        console.log("Notification settings saved:", settings);
        // form submission logic space ...
    };

    return (
        <form className="space-y-6" onSubmit={handleSubmit}>
            <Card title="Critical Alerts" icon={AlertTriangle}>
                <p className="text-sm text-gray-500 mb-4">Receive immediate notifications for crucial pricing and sentiment shifts.</p>
                <ToggleSwitch
                    label="Email: Competitor Price Drop ( > 5%)"
                    description="Receive an email when a tracked competitor's price drops significantly."
                    checked={settings.emailPriceDrop}
                    onChange={() => handleChange('emailPriceDrop')}
                />
                <ToggleSwitch
                    label="Email: Negative Sentiment Alert"
                    description="Receive an email for sudden, high-volume negative social mentions."
                    checked={settings.emailSentimentAlert}
                    onChange={() => handleChange('emailSentimentAlert')}
                />
            </Card>

            <Card title="In-App Notifications" icon={Bell}>
                <p className="text-sm text-gray-500 mb-4">Control notifications that appear in the dashboard bell icon.</p>
                <ToggleSwitch
                    label="Price Change Events"
                    description="Show an in-app notification when any tracked price changes."
                    checked={settings.inAppPriceDrop}
                    onChange={() => handleChange('inAppPriceDrop')}
                />
                <ToggleSwitch
                    label="New Social Mentions"
                    description="Show a notification for new positive and neutral mentions in the feed."
                    checked={settings.inAppSentimentAlert}
                    onChange={() => handleChange('inAppSentimentAlert')}
                />
            </Card>

            <Card title="Digest Emails" icon={Mail}>
                <p className="text-sm text-gray-500 mb-4">Get a summary of market activity and AI suggestions.</p>
                <ToggleSwitch
                    label="Daily Summary Digest"
                    description="A recap of the last 24 hours sent to your primary email."
                    checked={settings.digestDaily}
                    onChange={() => handleChange('digestDaily')}
                />
                <ToggleSwitch
                    label="Weekly AI Performance Report"
                    description="Deep dive on AI suggestion performance and overall sentiment trends."
                    checked={settings.digestWeekly}
                    onChange={() => handleChange('digestWeekly')}
                />
            </Card>

            <div className="flex justify-end pt-4">
                <button type="submit" className="px-5 py-2 bg-indigo-600 text-white rounded-lg shadow-md hover:bg-indigo-700 transition">Save Notifications</button>
            </div>
        </form>
    );
};


//  Integration Settings


const IntegrationsList: Integration[] = [
    { name: 'Shopify', icon: Globe, status: 'Connected', button: 'Disconnect', color: 'bg-green-100 text-green-700' },
    { name: 'Google Sheets', icon: BarChart2, status: 'Not Configured', button: 'Connect', color: 'bg-yellow-100 text-yellow-700' },
    { name: 'Slack', icon: MessageSquare, status: 'Connected', button: 'Disconnect', color: 'bg-green-100 text-green-700' },
    { name: 'Zapier', icon: Repeat, status: 'Available', button: 'Configure', color: 'bg-indigo-100 text-indigo-700' },
];

const IntegrationSettings: React.FC = () => {
    return (
        <div className="space-y-6">
            <Card title="API Key Management" icon={Cpu}>
                <p className="text-sm text-gray-500 mb-4">Your secret key for accessing our external pricing API.</p>
                <div className="flex flex-col sm:flex-row space-y-3 sm:space-y-0 sm:space-x-3">
                    <input type="text" readOnly defaultValue="SSPAI-QWKJ-1029-ASLD-0897" className="flex-grow p-3 border border-gray-300 rounded-lg bg-gray-50 font-mono text-sm" />
                    <button className="px-4 py-3 bg-red-600 text-white rounded-lg shadow-md hover:bg-red-700 transition flex items-center justify-center space-x-2">
                        <Repeat size={18} />
                        <span>Regenerate Key</span>
                    </button>
                </div>
            </Card>

            <Card title="Available Integrations" icon={Globe}>
                <p className="text-sm text-gray-500 mb-4">Connect SocialPrice.AI with your favorite tools for automation.</p>
                <div className="grid gap-4">
                    {IntegrationsList.map((integration) => (
                        <div key={integration.name} className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                            <div className="flex items-center space-x-4">
                                <integration.icon className="w-6 h-6 text-indigo-500" />
                                <div>
                                    <p className="font-semibold text-gray-800">{integration.name}</p>
                                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${integration.color}`}>{integration.status}</span>
                                </div>
                            </div>
                            <button className={`px-4 py-2 text-sm font-medium rounded-lg shadow-sm transition ${
                                integration.button === 'Disconnect' ? 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50' : 'bg-indigo-600 text-white hover:bg-indigo-700'
                            }`}>
                                {integration.button}
                            </button>
                        </div>
                    ))}
                </div>
            </Card>
        </div>
    );
};


interface TabButtonProps {
    id: 'profile' | 'notifications' | 'integrations';
    label: string;
    icon: React.ElementType;
    activeTab: string;
    setActiveTab: (tab: 'profile' | 'notifications' | 'integrations') => void;
}

const TabButton: React.FC<TabButtonProps> = ({ id, label, icon: Icon, activeTab, setActiveTab }) => (
    <button
        onClick={() => setActiveTab(id)}
        className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition duration-150 text-sm font-medium ${
            activeTab === id
                ? 'bg-white text-indigo-600 shadow-md'
                : 'text-gray-600 hover:bg-gray-100'
        }`}
    >
        <Icon className="w-5 h-5" />
        <span>{label}</span>
    </button>
);

const SettingsPage: React.FC = () => {
    const [activeTab, setActiveTab] = useState<'profile' | 'notifications' | 'integrations'>('profile');

    const renderContent = () => {
        switch (activeTab) {
            case 'profile':
                return <ProfileSettings />;
            case 'notifications':
                return <NotificationSettings />;
            case 'integrations':
                return <IntegrationSettings />;
            default:
                
                return <ProfileSettings />;
        }
    };

    return (
        <div className="min-h-screen bg-gray-50 font-sans antialiased">
            {/* Header (Minimal for a single-page app context) */}
            <header className="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-10">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
                    <h1 className="text-xl font-bold text-indigo-700 tracking-wide">SocialPrice<span className="text-gray-400">.AI</span></h1>
                    <div className="flex items-center space-x-4">
                        <Bell className="w-5 h-5 text-gray-500 hover:text-indigo-600 cursor-pointer" />
                        <div className="w-8 h-8 rounded-full bg-indigo-500 flex items-center justify-center font-bold text-sm text-white">JD</div>
                    </div>
                </div>
            </header>
           
            <main className="max-w-7xl mx-auto p-4 sm:p-6 lg:p-8">
                <div className="max-w-4xl mx-auto">
                    <SectionTitle title="Settings" description="Manage your account profile, notification preferences, and integrations." />
                   
             
                    <div className="bg-gray-100 p-2 rounded-xl flex flex-wrap gap-2 mb-8 shadow-inner">
                        <TabButton id="profile" label="Profile" icon={User} activeTab={activeTab} setActiveTab={setActiveTab} />
                        <TabButton id="notifications" label="Notifications" icon={Bell} activeTab={activeTab} setActiveTab={setActiveTab} />
                        <TabButton id="integrations" label="Integrations" icon={Cpu} activeTab={activeTab} setActiveTab={setActiveTab} />
                    </div>

                 
                    <div className="min-h-[600px]">
                        {renderContent()}
                    </div>
                </div>
            </main>

                        <footer className="py-6 mt-10 border-t border-gray-200 text-center text-sm text-gray-500">
                © {new Date().getFullYear()} Social sentimental pricing . All rights reserved.
            </footer>
        </div>
    );
};

export default SettingsPage;