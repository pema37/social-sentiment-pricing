// Pricing Rules Page
// Lists all pricing rules with filtering and management actions
//
// FIX (2026-02-21): Added useProducts() fetch and productNames map.
// Previously only competitorNames was passed to RulesList, causing
// rules scoped to specific products to show "Unknown" instead of
// the product name. See BUG-008 in audit report.

'use client';

import { useState, useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { Sliders, Plus, RefreshCw, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { RulesList, RulesListSkeleton } from '@/components/features/pricing';
import {
  usePricingRules,
  useTogglePricingRule,
  useDeletePricingRule,
} from '@/lib/hooks/use-pricing';
import { useCompetitors } from '@/lib/hooks/use-competitors';
import { useProducts } from '@/lib/hooks/use-products';  // FIX BUG-008
import type { RuleType } from '@/types';

// ============================================
// PAGE COMPONENT
// ============================================

export default function PricingRulesPage() {
  const router = useRouter();
  const [filterType, setFilterType] = useState<RuleType | 'all'>('all');
  const [filterActive, setFilterActive] = useState<'all' | 'active' | 'inactive'>('all');
  const [actionLoadingId, setActionLoadingId] = useState<string | undefined>();

  // Fetch rules
  const {
    data: rulesData,
    isLoading,
    isError,
    refetch,
  } = usePricingRules();

  // Fetch competitors for name resolution
  const { data: competitorsData, isError: isCompetitorsError } = useCompetitors({ page_size: 100 });

  // FIX BUG-008: Fetch products for name resolution
  const { data: productsData, isError: isProductsError } = useProducts({ page_size: 200 });

  const hasLookupErrors = isCompetitorsError || isProductsError;

  // Build competitor ID → name map
  const competitorNames = useMemo(() => {
    const map: Record<string, string> = {};
    competitorsData?.items?.forEach((c) => {
      map[c.id] = c.name;
    });
    return map;
  }, [competitorsData]);

  // FIX BUG-008: Build product ID → name map
  const productNames = useMemo(() => {
    const map: Record<string, string> = {};
    (productsData?.items ?? []).forEach((p) => {
      map[p.id] = p.name;
    });
    return map;
  }, [productsData]);

  // Mutations
  const toggleMutation = useTogglePricingRule();
  const deleteMutation = useDeletePricingRule();

  // Handle toggle
  const handleToggle = useCallback(
    async (id: string, isActive: boolean) => {
      setActionLoadingId(id);
      try {
        await toggleMutation.mutateAsync({ id, isActive });
        toast.success(isActive ? 'Rule enabled' : 'Rule disabled');
      } catch (error) {
        toast.error('Failed to update rule');
        console.error('Toggle error:', error);
      } finally {
        setActionLoadingId(undefined);
      }
    },
    [toggleMutation]
  );

  // Handle edit
  const handleEdit = useCallback(
    (id: string) => {
      router.push(`/pricing/rules/${id}`);
    },
    [router]
  );

  // Handle delete
  const handleDelete = useCallback(
    async (id: string) => {
      const confirmed = window.confirm(
        'Are you sure you want to delete this rule? This action cannot be undone.'
      );
      if (!confirmed) return;

      setActionLoadingId(id);
      try {
        await deleteMutation.mutateAsync(id);
        toast.success('Rule deleted');
      } catch (error) {
        toast.error('Failed to delete rule');
        console.error('Delete error:', error);
      } finally {
        setActionLoadingId(undefined);
      }
    },
    [deleteMutation]
  );

  // Handle duplicate
  const handleDuplicate = useCallback(
    (id: string) => {
      router.push(`/pricing/rules/new?duplicate=${id}`);
    },
    [router]
  );

  // Handle filter changes
  const handleFilterTypeChange = useCallback((type: RuleType | 'all') => {
    setFilterType(type);
  }, []);

  const handleFilterActiveChange = useCallback((status: 'all' | 'active' | 'inactive') => {
    setFilterActive(status);
  }, []);

  // Error state
  if (isError) {
    return (
      <div className="p-6">
        <Card padding="md" className="bg-red-50 border-red-200">
          <h3 className="text-red-800 font-medium mb-2">Error Loading Rules</h3>
          <p className="text-red-600 text-sm mb-4">
            Something went wrong while fetching pricing rules.
          </p>
          <Button variant="secondary" size="sm" onClick={() => refetch()}>
            Try Again
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Page Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Sliders className="h-6 w-6 text-blue-600" />
            Pricing Rules
          </h1>
          <p className="text-gray-600 mt-1">
            Define rules for automatic price recommendations
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => refetch()}
            disabled={isLoading}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={() => router.push('/pricing/rules/new')}
          >
            <Plus className="h-4 w-4 mr-2" />
            Create Rule
          </Button>
        </div>
      </div>

      {/* Stats Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Card padding="sm">
          <p className="text-sm text-gray-600 mb-1">Total Rules</p>
          <p className="text-2xl font-bold text-gray-900">
            {rulesData?.items?.length ?? 0}
          </p>
        </Card>
        <Card padding="sm" className="bg-green-50 border-green-200">
          <p className="text-sm text-gray-600 mb-1">Active</p>
          <p className="text-2xl font-bold text-green-700">
            {rulesData?.items?.filter((r) => r.is_active).length ?? 0}
          </p>
        </Card>
        <Card padding="sm">
          <p className="text-sm text-gray-600 mb-1">Inactive</p>
          <p className="text-2xl font-bold text-gray-900">
            {rulesData?.items?.filter((r) => !r.is_active).length ?? 0}
          </p>
        </Card>
        <Card padding="sm">
          <p className="text-sm text-gray-600 mb-1">Rule Types</p>
          <p className="text-2xl font-bold text-gray-900">
            {new Set(rulesData?.items?.map((r) => r.rule_type)).size ?? 0}
          </p>
        </Card>
      </div>

      {/* Lookup failure warning */}
      {hasLookupErrors && (
        <Card padding="sm" className="bg-yellow-50 border-yellow-200 mb-4">
          <div className="flex items-center gap-2 text-yellow-800 text-sm">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>
              Could not load {isCompetitorsError && isProductsError ? 'competitor and product' : isCompetitorsError ? 'competitor' : 'product'} names.
              Rules may show truncated IDs instead of names.
            </span>
          </div>
        </Card>
      )}

      {/* Rules List */}
      {isLoading ? (
        <RulesListSkeleton count={3} />
      ) : (
        <RulesList
          rules={rulesData?.items ?? []}
          productNames={productNames}        /* FIX BUG-008 */
          competitorNames={competitorNames}
          filterType={filterType}
          filterActive={filterActive}
          onFilterTypeChange={handleFilterTypeChange}
          onFilterActiveChange={handleFilterActiveChange}
          onToggle={handleToggle}
          onEdit={handleEdit}
          onDelete={handleDelete}
          onDuplicate={handleDuplicate}
          actionLoadingId={actionLoadingId}
          showFilters
        />
      )}
    </div>
  );
}


