"use client";

import React from "react";
// We maintain the named imports for Lucide icons, as they are necessary and correct.
import { 
    LogOut, 
    User,
    LayoutDashboard, // Dashboard icon
    Package,         // Products icon
    Users,           // Competitors icon
    TrendingUp,      // Sentiment icon
    DollarSign,      // Price Suggestions icon
    Settings,        // Settings icon
    KeyRound,        // API Keys icon
    UserCog,         // Admin icon
} from 'lucide-react'; 

// --- Type Definitions ---
type NavItem = {
    href: string;
    label: string;
    icon: React.ElementType; 
};

// --- Updated Navigation Data (Using Lucide Icons) ---
const navItems: NavItem[] = [
    { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { href: "/products", label: "Products", icon: Package },
    { href: "/competitors", label: "Competitors", icon: Users },
    { href: "/sentiment", label: "Sentiment", icon: TrendingUp },
    { href: "/price-suggestions", label: "Price Suggestions", icon: DollarSign },
    { href: "/settings", label: "Settings", icon: Settings },
    { href: "/api-keys", label: "API Keys", icon: KeyRound },
    { href: "/admin", label: "Admin", icon: UserCog },
];

// Replaces Next.js Link
const CustomLink: React.FC<{ href: string; children: React.ReactNode; active: boolean }> = ({ href, children, active }) => (
    <a
        href={href}
        // Applied dark theme classes
        className={`
            flex items-center space-x-3 rounded-lg px-3 py-3 font-medium transition-colors duration-150
            ${active
                // Active state: Brighter background, strong white text
                ? "bg-[#36415a] text-white font-semibold shadow-inner" 
                // Inactive state: Light gray text, hover darker background
                : "text-slate-300 hover:bg-[#36415a]/50 hover:text-white"
            }
        `}
    >
        {children}
    </a>
);


// Exported as a DEFAULT EXPORT (functionally equivalent to what App components use)
// This is the most reliable export pattern for standalone React files in this environment.
export default function Sidebar() { 
    // Replaced usePathname() with window.location for current path simulation
    // Fallback to '/' if window is undefined (e.g., during server-side rendering/compilation)
    const currentPath = typeof window !== 'undefined' ? window.location.pathname : '/products'; 

    // Handler for logout action (Replaces useRouter().push)
    const handleLogout = () => {
        console.log("User logging out...");
        // Redirect using standard browser function
        if (typeof window !== 'undefined') {
            window.location.href = '/login'; 
        }
    };

    return (
        <aside className="hidden md:flex w-64 flex-col bg-[#1E293B] shadow-2xl z-30 min-h-screen">
            
            {/* 1. Header/Logo - Dark border line and white text */}
            <div className="px-6 py-4 border-b border-[#36415a]">
                <span className="text-xl font-bold text-white">SSP <span className="font-light text-slate-300">Social Sentiment</span></span>
            </div>

            {/* 2. Navigation Links */}
            <nav className="flex-1 px-4 py-4 space-y-1 text-sm overflow-y-auto">
                {navItems.map((item) => {
                    // Check if the current route starts with the item's href (for nested routes)
                    const active = currentPath.startsWith(item.href);
                    const Icon = item.icon; // Lucide icon component

                    return (
                        <CustomLink
                            key={item.href}
                            href={item.href}
                            active={active}
                        >
                            {/* Display Lucide Icon */}
                            <Icon className="w-5 h-5" /> 
                            <span>{item.label}</span>
                        </CustomLink>
                    );
                })}
            </nav>

            {/* 3. User Info and Logout Button - Adjusted to dark theme colors */}
            <div className="p-4 border-t border-[#36415a]">
                {/* User Profile Info - NOW A CLICKABLE LINK */}
                <CustomLink 
                    href="/profile" 
                    active={currentPath.startsWith('/profile')}
                >
                    <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center text-slate-100 font-bold text-sm transition-colors">
                        <User className="w-4 h-4" /> 
                    </div>
                    <div className="text-sm overflow-hidden">
                        <p className="font-semibold text-white truncate">Admin User</p>
                        <p className="text-xs text-slate-400 truncate">user@ssp.com</p>
                    </div>
                </CustomLink>
                
                {/* Logout Button - Adjusted to dark theme for hover/focus state */}
                <button
                    onClick={handleLogout}
                    // Retained red coloring for logout action visibility
                    className="w-full flex items-center justify-center space-x-3 text-red-400 bg-transparent hover:bg-[#36415a] p-3 rounded-lg transition-colors font-medium"
                >
                    <LogOut className="w-5 h-5" />
                    <span>Log Off</span>
                </button>
            </div>
        </aside>
    );
}