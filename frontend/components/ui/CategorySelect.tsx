// components/ui/CategorySelect.tsx
'use client';

import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { Input } from '@/components/ui/Input';

interface CategorySelectProps {
  value: string;
  onChange: (value: string) => void;
  categories: string[];
  isLoading?: boolean;
}

export function CategorySelect({ value, onChange, categories, isLoading }: CategorySelectProps) {
  const [isCustom, setIsCustom] = useState(false);
  const [customValue, setCustomValue] = useState('');

  const isExistingCategory = categories.includes(value);
  
  const handleSelectChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const selected = e.target.value;
    if (selected === '__custom__') {
      setIsCustom(true);
      setCustomValue('');
      onChange('');
    } else {
      setIsCustom(false);
      onChange(selected);
    }
  };

  const handleCustomChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setCustomValue(val);
    onChange(val);
  };

  const handleBackToSelect = () => {
    setIsCustom(false);
    setCustomValue('');
    onChange('');
  };

  if (isCustom || (value && !isExistingCategory && categories.length > 0)) {
    return (
      <div className="space-y-2">
        <div className="relative">
          <Input
            value={isCustom ? customValue : value}
            onChange={handleCustomChange}
            placeholder="Enter new category name"
            className="pr-24"
          />
          <button
            type="button"
            onClick={handleBackToSelect}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-blue-600 hover:text-blue-800"
          >
            Select existing
          </button>
        </div>
        <p className="text-xs text-gray-500">Creating a new category</p>
      </div>
    );
  }

  return (
    <div className="relative">
      <select
        value={value}
        onChange={handleSelectChange}
        disabled={isLoading}
        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 appearance-none bg-white text-sm"
      >
        <option value="">Select a category...</option>
        {categories.map((cat) => (
          <option key={cat} value={cat}>{cat}</option>
        ))}
        <option value="__custom__">+ Add new category</option>
      </select>
      <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
    </div>
  );
}

