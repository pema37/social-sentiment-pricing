// Product type - represents a product from your store
export interface Product {
  id: string;             // Unique identifier (UUID)
  name: string;           // Product name (e.g., "Wireless Headphones")
  sku: string;            // Stock Keeping Unit (e.g., "WH-1000")
  current_price: number;  // Current selling price
  base_price: number;     // Original/base price before adjustments
  category: string;       // Product category (e.g., "Electronics")
  description?: string;   // Optional product description
  image_url?: string;     // Optional product image URL
  is_active: boolean;     // Is product currently listed?
  user_id: string;        // Owner of this product (your user ID)
  created_at: string;     // When product was added
  updated_at: string;     // When product was last modified
}

// What you send when creating a new product
export interface CreateProductInput {
  name: string;
  sku: string;
  current_price: number;
  base_price: number;
  category: string;
  description?: string;   // Optional
  image_url?: string;     // Optional
}

// What you send when updating a product (all fields optional)
export interface UpdateProductInput {
  name?: string;
  current_price?: number;
  category?: string;
  description?: string;
  is_active?: boolean;
}
