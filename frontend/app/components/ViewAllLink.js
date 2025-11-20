
"use client";

import Link from 'next/link';
import React from 'react';

export default function ViewAllLink({ href, text }) {
    return (
       
        <Link 
            href={href} 
            className="text-sm text-blue-600 font-medium hover:text-blue-500 px-3 py-1 rounded-md border border-blue-600 hover:border-blue-500 transition-colors"
        >
            {/* 🔄 UPDATED content is directly inside Link */}
            {text}
        </Link>
    );
}