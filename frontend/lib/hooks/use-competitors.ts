// Competitor hooks
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { competitorsApi } from '@/lib/api';
import { toast } from '@/lib/hooks/use-toast';
import type { 
  CreateCompetitorRequest, 
  UpdateCompetitorRequest,
  CreateCompetitorProductRequest,
  UpdateCompetitorProductRequest,
} from '@/types';

// Query keys
export const competitorKeys = {
  all: ['competitors'] as const,
  list: (params?: { page?: number; page_size?: number; is_active?: boolean }) =>
    [...competitorKeys.all, 'list', params] as const,
  detail: (id: string) => [...competitorKeys.all, 'detail', id] as const,
  products: () => [...competitorKeys.all, 'products'] as const,
  productsList: (params?: { product_id?: string; competitor_id?: string; is_active?: boolean }) =>
    [...competitorKeys.products(), 'list', params] as const,
  productDetail: (id: string) => [...competitorKeys.products(), 'detail', id] as const,
  priceHistory: (competitorProductId: string, params?: { days?: number }) =>
    [...competitorKeys.products(), 'history', competitorProductId, params] as const,
  comparison: (productId: string) => [...competitorKeys.all, 'comparison', productId] as const,
};

// ============== Competitor Hooks ==============

// Get paginated competitors
export function useCompetitors(params?: { page?: number; page_size?: number; is_active?: boolean }) {
  return useQuery({
    queryKey: competitorKeys.list(params),
    queryFn: () => competitorsApi.getAll(params),
    staleTime: 30 * 1000,
  });
}

// Get single competitor
export function useCompetitor(id: string | null) {
  return useQuery({
    queryKey: competitorKeys.detail(id || ''),
    queryFn: () => competitorsApi.getById(id!),
    enabled: !!id,
    staleTime: 30 * 1000,
  });
}

// Create competitor
export function useCreateCompetitor() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateCompetitorRequest) => competitorsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: competitorKeys.all });
      toast.success({ title: 'Competitor added', message: 'Competitor has been added successfully' });
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to add competitor', message: error.message });
    },
  });
}

// Update competitor
export function useUpdateCompetitor() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateCompetitorRequest }) =>
      competitorsApi.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: competitorKeys.detail(variables.id) });
      queryClient.invalidateQueries({ queryKey: competitorKeys.list() });
      toast.success({ title: 'Competitor updated', message: 'Competitor details have been updated' });
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to update competitor', message: error.message });
    },
  });
}

// Delete competitor
export function useDeleteCompetitor() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => competitorsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: competitorKeys.all });
      toast.success({ title: 'Competitor deleted', message: 'Competitor has been removed' });
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to delete competitor', message: error.message });
    },
  });
}

// ============== Competitor Product Hooks ==============

// Get competitor products
export function useCompetitorProducts(params?: { 
  product_id?: string; 
  competitor_id?: string; 
  is_active?: boolean;
  page?: number;
  page_size?: number;
}) {
  return useQuery({
    queryKey: competitorKeys.productsList(params),
    queryFn: () => competitorsApi.getProducts(params),
    staleTime: 30 * 1000,
  });
}

// Get single competitor product with details
export function useCompetitorProduct(id: string | null) {
  return useQuery({
    queryKey: competitorKeys.productDetail(id || ''),
    queryFn: () => competitorsApi.getProduct(id!),
    enabled: !!id,
    staleTime: 30 * 1000,
  });
}

// Create competitor product link
export function useCreateCompetitorProduct() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateCompetitorProductRequest) => competitorsApi.createProduct(data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: competitorKeys.products() });
      queryClient.invalidateQueries({ queryKey: competitorKeys.comparison(variables.product_id) });
      toast.success({ title: 'Product linked', message: 'Competitor product has been linked' });
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to link product', message: error.message });
    },
  });
}

// Update competitor product
export function useUpdateCompetitorProduct() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateCompetitorProductRequest }) =>
      competitorsApi.updateProduct(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: competitorKeys.productDetail(variables.id) });
      queryClient.invalidateQueries({ queryKey: competitorKeys.productsList() });
      toast.success({ title: 'Product updated', message: 'Competitor product has been updated' });
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to update product', message: error.message });
    },
  });
}

// Delete competitor product
export function useDeleteCompetitorProduct() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => competitorsApi.deleteProduct(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: competitorKeys.products() });
      toast.success({ title: 'Product unlinked', message: 'Competitor product has been removed' });
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to unlink product', message: error.message });
    },
  });
}

// ============== Price History & Scraping Hooks ==============

// Get price history
export function useCompetitorPriceHistory(
  competitorProductId: string | null,
  params?: { days?: number }
) {
  return useQuery({
    queryKey: competitorKeys.priceHistory(competitorProductId || '', params),
    queryFn: () => competitorsApi.getPriceHistory(competitorProductId!, params),
    enabled: !!competitorProductId,
    staleTime: 60 * 1000,
  });
}

// Trigger price scrape
export function useScrapeCompetitorPrice() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (competitorProductId: string) => competitorsApi.scrapePrice(competitorProductId),
    onSuccess: (_, competitorProductId) => {
      queryClient.invalidateQueries({ queryKey: competitorKeys.productDetail(competitorProductId) });
      queryClient.invalidateQueries({ queryKey: competitorKeys.priceHistory(competitorProductId) });
      queryClient.invalidateQueries({ queryKey: competitorKeys.productsList() });
      toast.success({ title: 'Price updated', message: 'Latest competitor price has been fetched' });
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to fetch price', message: error.message });
    },
  });
}

// ============== Analysis Hooks ==============

// Get price comparison for a product
export function usePriceComparison(productId: string | null) {
  return useQuery({
    queryKey: competitorKeys.comparison(productId || ''),
    queryFn: () => competitorsApi.comparePrices(productId!),
    enabled: !!productId,
    staleTime: 60 * 1000,
  });
}
