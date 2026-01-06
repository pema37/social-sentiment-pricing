// components/features/products/ImportCSVModal.tsx
'use client';

import { useState, useCallback, useRef } from 'react';
import { Upload, X, FileText, AlertCircle, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { useImportProducts } from '@/lib/hooks/use-products';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface ImportCSVModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

interface ParsedRow {
  name: string;
  sku?: string;
  base_price: number;
  description?: string;
  category?: string;
  image_url?: string;
  stock_quantity?: number;
}

interface PreviewData {
  headers: string[];
  rows: string[][];
  mappedRows: ParsedRow[];
  errors: string[];
}

// ─────────────────────────────────────────────────────────────────────────────
// Column Mapping - WooCommerce & Shopify compatible
// ─────────────────────────────────────────────────────────────────────────────

const COLUMN_MAPPINGS: Record<string, keyof ParsedRow> = {
  // Name variations
  'name': 'name',
  'product name': 'name',
  'title': 'name',
  'product title': 'name',
  
  // SKU variations
  'sku': 'sku',
  'product sku': 'sku',
  'item number': 'sku',
  'item_number': 'sku',
  
  // Price variations
  'price': 'base_price',
  'base_price': 'base_price',
  'base price': 'base_price',
  'regular_price': 'base_price',
  'regular price': 'base_price',
  
  // Description variations
  'description': 'description',
  'short_description': 'description',
  'short description': 'description',
  'product description': 'description',
  
  // Category variations
  'category': 'category',
  'categories': 'category',
  'product category': 'category',
  'type': 'category',
  
  // Image variations
  'image': 'image_url',
  'image_url': 'image_url',
  'image url': 'image_url',
  'images': 'image_url',
  'featured_image': 'image_url',
  
  // Stock variations
  'stock': 'stock_quantity',
  'stock_quantity': 'stock_quantity',
  'stock quantity': 'stock_quantity',
  'quantity': 'stock_quantity',
  'inventory': 'stock_quantity',
};

// ─────────────────────────────────────────────────────────────────────────────
// CSV Parser
// ─────────────────────────────────────────────────────────────────────────────

function parseCSV(text: string): { headers: string[]; rows: string[][] } {
  const lines = text.split(/\r?\n/).filter(line => line.trim());
  if (lines.length === 0) return { headers: [], rows: [] };

  const headers = parseCSVLine(lines[0]);
  
  const rows: string[][] = [];
  for (let i = 1; i < lines.length; i++) {
    const row = parseCSVLine(lines[i]);
    if (row.length > 0 && row.some(cell => cell.trim())) {
      rows.push(row);
    }
  }

  return { headers, rows };
}

function parseCSVLine(line: string): string[] {
  const result: string[] = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    const nextChar = line[i + 1];

    if (inQuotes) {
      if (char === '"' && nextChar === '"') {
        current += '"';
        i++;
      } else if (char === '"') {
        inQuotes = false;
      } else {
        current += char;
      }
    } else {
      if (char === '"') {
        inQuotes = true;
      } else if (char === ',') {
        result.push(current.trim());
        current = '';
      } else {
        current += char;
      }
    }
  }
  result.push(current.trim());

  return result;
}

function mapRowToProduct(
  headers: string[],
  row: string[]
): { product: ParsedRow | null; error: string | null } {
  const mapped: Partial<ParsedRow> = {};
  
  headers.forEach((header, index) => {
    const normalizedHeader = header.toLowerCase().trim();
    const fieldName = COLUMN_MAPPINGS[normalizedHeader];
    
    if (fieldName && row[index]) {
      const value = row[index].trim();
      
      if (fieldName === 'base_price' || fieldName === 'stock_quantity') {
        const num = parseFloat(value.replace(/[^0-9.-]/g, ''));
        if (!isNaN(num)) {
          mapped[fieldName] = num;
        }
      } else if (fieldName === 'image_url' && value.includes(',')) {
        mapped[fieldName] = value.split(',')[0].trim();
      } else {
        mapped[fieldName] = value;
      }
    }
  });

  if (!mapped.name) {
    return { product: null, error: 'Missing product name' };
  }
  if (!mapped.base_price || mapped.base_price <= 0) {
    return { product: null, error: `Invalid price for "${mapped.name}"` };
  }

  return {
    product: {
      name: mapped.name,
      sku: mapped.sku,
      base_price: mapped.base_price,
      description: mapped.description,
      category: mapped.category,
      image_url: mapped.image_url,
      stock_quantity: mapped.stock_quantity,
    },
    error: null,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────────────

export function ImportCSVModal({ isOpen, onClose, onSuccess }: ImportCSVModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<PreviewData | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const importProducts = useImportProducts();

  const processFile = useCallback(async (selectedFile: File) => {
    setFile(selectedFile);
    
    const text = await selectedFile.text();
    const { headers, rows } = parseCSV(text);
    
    const mappedRows: ParsedRow[] = [];
    const errors: string[] = [];
    
    rows.forEach((row, index) => {
      const { product, error } = mapRowToProduct(headers, row);
      if (product) {
        mappedRows.push(product);
      } else if (error) {
        errors.push(`Row ${index + 2}: ${error}`);
      }
    });
    
    setPreview({
      headers,
      rows: rows.slice(0, 5),
      mappedRows,
      errors,
    });
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile && (selectedFile.type === 'text/csv' || selectedFile.name.endsWith('.csv'))) {
      processFile(selectedFile);
    }
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && (droppedFile.type === 'text/csv' || droppedFile.name.endsWith('.csv'))) {
      processFile(droppedFile);
    }
  }, [processFile]);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleBrowseClick = () => {
    fileInputRef.current?.click();
  };

  const handleImport = () => {
    if (!preview || preview.mappedRows.length === 0) return;
    
    importProducts.mutate(
      { products: preview.mappedRows },
      {
        onSuccess: (result) => {
          if (result.created > 0) {
            onSuccess();
          }
        },
      }
    );
  };

  const handleReset = () => {
    setFile(null);
    setPreview(null);
    importProducts.reset();
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      
      {/* Modal */}
      <div className="relative bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-lg font-semibold text-gray-900">Import Products from CSV</h2>
          <button
            type="button"
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded-full transition-colors"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 overflow-y-auto flex-1">
          {/* Success State */}
          {importProducts.isSuccess && (
            <div className="text-center py-8">
              <CheckCircle2 className="w-16 h-16 text-green-500 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">Import Complete!</h3>
              <p className="text-gray-600 mb-4">
                Successfully imported {importProducts.data?.created} products.
                {importProducts.data?.failed > 0 && (
                  <span className="text-amber-600">
                    {' '}{importProducts.data.failed} failed.
                  </span>
                )}
              </p>
              <div className="flex gap-2 justify-center">
                <Button variant="secondary" onClick={handleReset}>
                  Import More
                </Button>
                <Button onClick={onClose}>
                  Done
                </Button>
              </div>
            </div>
          )}

          {/* Upload State */}
          {!importProducts.isSuccess && !preview && (
            <div
              className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                isDragging
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-300 hover:border-gray-400'
              }`}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
            >
              <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600 mb-2">
                Drag and drop your CSV file here, or
              </p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                onChange={handleFileSelect}
                className="hidden"
              />
              <Button variant="secondary" onClick={handleBrowseClick}>
                Browse Files
              </Button>
              
              <div className="mt-6 text-left bg-gray-50 rounded-lg p-4">
                <p className="text-sm font-medium text-gray-700 mb-2">
                  Supported columns:
                </p>
                <p className="text-xs text-gray-500">
                  name, sku, price/regular_price, description, category, image_url, stock_quantity
                </p>
                <p className="text-xs text-gray-500 mt-2">
                  Compatible with WooCommerce and Shopify CSV exports.
                </p>
              </div>
            </div>
          )}

          {/* Preview State */}
          {!importProducts.isSuccess && preview && (
            <div className="space-y-4">
              {/* File Info */}
              <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                <FileText className="w-8 h-8 text-gray-400" />
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-900 truncate">{file?.name}</p>
                  <p className="text-sm text-gray-500">
                    {preview.mappedRows.length} products ready to import
                  </p>
                </div>
                <Button variant="ghost" size="sm" onClick={handleReset}>
                  Change
                </Button>
              </div>

              {/* Errors */}
              {preview.errors.length > 0 && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
                  <div className="flex items-start gap-2">
                    <AlertCircle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium text-amber-800">
                        {preview.errors.length} rows skipped
                      </p>
                      <ul className="text-sm text-amber-700 mt-1 space-y-0.5">
                        {preview.errors.slice(0, 3).map((error, i) => (
                          <li key={i}>{error}</li>
                        ))}
                        {preview.errors.length > 3 && (
                          <li>...and {preview.errors.length - 3} more</li>
                        )}
                      </ul>
                    </div>
                  </div>
                </div>
              )}

              {/* Preview Table */}
              <div>
                <p className="text-sm font-medium text-gray-700 mb-2">Preview</p>
                <div className="border rounded-lg overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50 border-b">
                        <tr>
                          <th className="px-3 py-2 text-left font-medium text-gray-700">Name</th>
                          <th className="px-3 py-2 text-left font-medium text-gray-700">SKU</th>
                          <th className="px-3 py-2 text-left font-medium text-gray-700">Price</th>
                          <th className="px-3 py-2 text-left font-medium text-gray-700">Category</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {preview.mappedRows.slice(0, 5).map((product, i) => (
                          <tr key={i}>
                            <td className="px-3 py-2 text-gray-900">{product.name}</td>
                            <td className="px-3 py-2 text-gray-500">{product.sku || '-'}</td>
                            <td className="px-3 py-2 text-gray-900">${(Number(product.base_price ?? 0)).toFixed(2)}</td>
                            <td className="px-3 py-2 text-gray-500">{product.category || '-'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {preview.mappedRows.length > 5 && (
                    <div className="px-3 py-2 bg-gray-50 text-sm text-gray-500 text-center border-t">
                      ...and {preview.mappedRows.length - 5} more products
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        {!importProducts.isSuccess && preview && preview.mappedRows.length > 0 && (
          <div className="flex justify-end gap-2 p-4 border-t bg-gray-50">
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button
              onClick={handleImport}
              isLoading={importProducts.isPending}
              disabled={importProducts.isPending}
            >
              Import {preview.mappedRows.length} Products
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

export default ImportCSVModal;


