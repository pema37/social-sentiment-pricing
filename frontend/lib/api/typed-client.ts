// frontend/lib/api/typed-client.ts

/**
 * Type-safe API client using openapi-typescript generated types
 * 
 * This provides full type inference for:
 * - Request bodies
 * - Query parameters  
 * - Response types
 * - Path parameters
 * 
 * Usage:
 *   import { typedApi } from '@/lib/api/typed-client';
 *   
 *   // GET with inferred response type
 *   const products = await typedApi.get('/api/v1/products');
 *   
 *   // POST with type-checked body
 *   const newProduct = await typedApi.post('/api/v1/products', {
 *     body: { name: 'Widget', base_price: '29.99' }
 *   });
 */

import { apiClient } from './client';
import type { paths, components } from '@/types/api-generated';

// =============================================================================
// TYPE HELPERS
// =============================================================================

/** Extract response type for a given path and method */
type ApiResponse<
  Path extends keyof paths,
  Method extends keyof paths[Path]
> = paths[Path][Method] extends { responses: { 200: { content: { 'application/json': infer R } } } }
  ? R
  : paths[Path][Method] extends { responses: { 201: { content: { 'application/json': infer R } } } }
  ? R
  : paths[Path][Method] extends { responses: { 204: never } }
  ? void
  : unknown;

/** Extract request body type for a given path and method */
type ApiRequestBody<
  Path extends keyof paths,
  Method extends keyof paths[Path]
> = paths[Path][Method] extends { requestBody: { content: { 'application/json': infer B } } }
  ? B
  : never;

/** Extract query parameters for a given path and method */
type ApiQueryParams<
  Path extends keyof paths,
  Method extends keyof paths[Path]
> = paths[Path][Method] extends { parameters: { query?: infer Q } }
  ? Q
  : never;

/** Check if a path+method has a request body */
type HasBody<
  Path extends keyof paths,
  Method extends keyof paths[Path]
> = paths[Path][Method] extends { requestBody: unknown } ? true : false;

// =============================================================================
// TYPED API CLIENT
// =============================================================================

/**
 * Type-safe GET request
 */
async function get<Path extends keyof paths>(
  path: Path,
  options?: {
    params?: ApiQueryParams<Path, 'get'>;
  }
): Promise<ApiResponse<Path, 'get'>> {
  return apiClient(path as string, {
    method: 'GET',
    params: options?.params as Record<string, string | number | boolean | undefined>,
  });
}

/**
 * Type-safe POST request
 */
async function post<Path extends keyof paths>(
  path: Path,
  options?: {
    body?: ApiRequestBody<Path, 'post'>;
    params?: ApiQueryParams<Path, 'post'>;
  }
): Promise<ApiResponse<Path, 'post'>> {
  return apiClient(path as string, {
    method: 'POST',
    body: options?.body,
    params: options?.params as Record<string, string | number | boolean | undefined>,
  });
}

/**
 * Type-safe PUT request
 */
async function put<Path extends keyof paths>(
  path: Path,
  options?: {
    body?: ApiRequestBody<Path, 'put'>;
    params?: ApiQueryParams<Path, 'put'>;
  }
): Promise<ApiResponse<Path, 'put'>> {
  return apiClient(path as string, {
    method: 'PUT',
    body: options?.body,
    params: options?.params as Record<string, string | number | boolean | undefined>,
  });
}

/**
 * Type-safe PATCH request
 */
async function patch<Path extends keyof paths>(
  path: Path,
  options?: {
    body?: ApiRequestBody<Path, 'patch'>;
    params?: ApiQueryParams<Path, 'patch'>;
  }
): Promise<ApiResponse<Path, 'patch'>> {
  return apiClient(path as string, {
    method: 'PATCH',
    body: options?.body,
    params: options?.params as Record<string, string | number | boolean | undefined>,
  });
}

/**
 * Type-safe DELETE request
 */
async function del<Path extends keyof paths>(
  path: Path,
  options?: {
    params?: ApiQueryParams<Path, 'delete'>;
  }
): Promise<ApiResponse<Path, 'delete'>> {
  return apiClient(path as string, {
    method: 'DELETE',
    params: options?.params as Record<string, string | number | boolean | undefined>,
  });
}

// =============================================================================
// EXPORTS
// =============================================================================

/**
 * Typed API client with full inference from OpenAPI spec
 */
export const typedApi = {
  get,
  post,
  put,
  patch,
  delete: del,
};

/**
 * Re-export schema types for easy access
 * 
 * Usage:
 *   import { schemas } from '@/lib/api/typed-client';
 *   type Product = schemas['ProductRead'];
 */
export type schemas = components['schemas'];

/**
 * Helper to get a specific schema type
 * 
 * Usage:
 *   import type { Schema } from '@/lib/api/typed-client';
 *   type Product = Schema<'ProductRead'>;
 */
export type Schema<T extends keyof components['schemas']> = components['schemas'][T];



