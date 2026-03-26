"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { AlertCircle, CheckCircle, AlertTriangle, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";
import { api } from "@/lib/api/client";

// Types for diagnostic response
interface IntegrationSummary {
  id: string;
  platform: string;
  store_url: string;
  status: string;
  is_active: boolean;
  last_sync_at: string | null;
}

interface PlatformLink {
  platform: string;
  integration_id: string;
  integration_status: string;
  sync_enabled: boolean;
  external_product_id: string;
  external_price: number | null;
  would_push: boolean;
}

interface ProductMapping {
  product_name: string;
  sku: string | null;
  current_price: number | null;
  platforms_linked: PlatformLink[];
  total_platforms: number;
  active_push_targets: number;
}

interface Issue {
  type: string;
  severity: "HIGH" | "MEDIUM" | "LOW";
  message: string;
  product_id?: string;
  integration_id?: string;
  suggestion: string;
}

interface DiagnosticResponse {
  user_id: string;
  summary: {
    total_integrations: number;
    active_integrations: number;
    total_products: number;
    total_links: number;
    issues_found: number;
  };
  integrations: IntegrationSummary[];
  products: Record<string, ProductMapping>;
  issues: Issue[];
}

export function DiagnosticPanel() {
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [data, setData] = useState<DiagnosticResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runDiagnostic = async () => {
    setIsLoading(true);
    setError(null);

    try {
      // FIX (2026-01-27): Use api client instead of raw fetch
      // This ensures proper authentication header is included
      const result = await api.get<DiagnosticResponse>("/api/v1/diagnostic/integration-health");
      setData(result);
      setIsOpen(true);
    } catch (err) {
      // Handle structured error from api client
      if (err && typeof err === 'object' && 'detail' in err) {
        const detail = (err as { detail: string | object }).detail;
        setError(typeof detail === 'string' ? detail : JSON.stringify(detail));
      } else {
        setError(err instanceof Error ? err.message : "Failed to run diagnostic");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const bulkSyncMutation = useMutation({
    mutationFn: () => api.post<{ queued: boolean }>("/api/v1/product-sync/sync/bulk"),
    onSuccess: runDiagnostic,
  });

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "HIGH":
        return "bg-red-100 text-red-800 border-red-200";
      case "MEDIUM":
        return "bg-yellow-100 text-yellow-800 border-yellow-200";
      case "LOW":
        return "bg-blue-100 text-blue-800 border-blue-200";
      default:
        return "bg-gray-100 text-gray-800 border-gray-200";
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case "HIGH":
        return <AlertCircle className="h-4 w-4 text-red-600" />;
      case "MEDIUM":
        return <AlertTriangle className="h-4 w-4 text-yellow-600" />;
      default:
        return <AlertCircle className="h-4 w-4 text-blue-600" />;
    }
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm mb-6">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-900">
            🔧 Integration Diagnostic
          </span>
          {data && (
            <span
              className={`text-xs px-2 py-0.5 rounded-full ${
                data.summary.issues_found === 0
                  ? "bg-green-100 text-green-800"
                  : "bg-red-100 text-red-800"
              }`}
            >
              {data.summary.issues_found === 0
                ? "All Good"
                : `${data.summary.issues_found} Issue${data.summary.issues_found > 1 ? "s" : ""}`}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={runDiagnostic}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            {isLoading ? "Running..." : "Run Diagnostic"}
          </button>
          {data && (
            <button
              onClick={() => setIsOpen(!isOpen)}
              className="p-1.5 text-gray-500 hover:text-gray-700"
            >
              {isOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="px-4 py-3 bg-red-50 border-b border-red-200">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Results */}
      {data && isOpen && (
        <div className="p-4 space-y-4">
          {/* Summary */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="bg-gray-50 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-gray-900">
                {data.summary.total_integrations}
              </div>
              <div className="text-xs text-gray-500">Integrations</div>
            </div>
            <div className="bg-gray-50 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-green-600">
                {data.summary.active_integrations}
              </div>
              <div className="text-xs text-gray-500">Active</div>
            </div>
            <div className="bg-gray-50 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-gray-900">
                {data.summary.total_products}
              </div>
              <div className="text-xs text-gray-500">Products</div>
            </div>
            <div className="bg-gray-50 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-gray-900">
                {data.summary.total_links}
              </div>
              <div className="text-xs text-gray-500">Links</div>
            </div>
            <div className="bg-gray-50 rounded-lg p-3 text-center">
              <div
                className={`text-2xl font-bold ${
                  data.summary.issues_found === 0 ? "text-green-600" : "text-red-600"
                }`}
              >
                {data.summary.issues_found}
              </div>
              <div className="text-xs text-gray-500">Issues</div>
            </div>
          </div>

          {/* Integration Status */}
          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-2">Integration Status</h4>
            <div className="space-y-2">
              {data.integrations.map((integration) => (
                <div
                  key={integration.id}
                  className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium capitalize">
                      {integration.platform}
                    </span>
                    <span className="text-xs text-gray-500 truncate max-w-50">
                      {integration.store_url}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {integration.is_active ? (
                      <span className="inline-flex items-center gap-1 text-xs text-green-700 bg-green-100 px-2 py-0.5 rounded-full">
                        <CheckCircle className="h-3 w-3" />
                        Active
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs text-red-700 bg-red-100 px-2 py-0.5 rounded-full">
                        <AlertCircle className="h-3 w-3" />
                        {integration.status}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Issues */}
          {data.issues.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2">
                Issues Found ({data.issues.length})
              </h4>
              <div className="space-y-2">
                {data.issues.map((issue, index) => (
                  <div
                    key={index}
                    className={`border rounded-lg p-3 ${getSeverityColor(issue.severity)}`}
                  >
                    <div className="flex items-start gap-2">
                      {getSeverityIcon(issue.severity)}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-medium uppercase">
                            {issue.type.replace(/_/g, " ")}
                          </span>
                          <span
                            className={`text-xs px-1.5 py-0.5 rounded ${
                              issue.severity === "HIGH"
                                ? "bg-red-200"
                                : issue.severity === "MEDIUM"
                                ? "bg-yellow-200"
                                : "bg-blue-200"
                            }`}
                          >
                            {issue.severity}
                          </span>
                        </div>
                        <p className="text-sm">{issue.message}</p>
                        <p className="text-xs mt-1 opacity-75">
                          💡 {issue.suggestion}
                        </p>
                        {issue.type === "BULK_PRODUCTS_UNLINKED" && (
                          <div className="mt-2">
                            <button
                              onClick={() => bulkSyncMutation.mutate()}
                              disabled={bulkSyncMutation.isPending}
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              {bulkSyncMutation.isPending ? "Queueing sync..." : "Fix Now"}
                            </button>
                            {bulkSyncMutation.isSuccess && (
                              <span className="ml-2 text-xs text-green-600">Sync queued ✓</span>
                            )}
                            {bulkSyncMutation.isError && (
                              <span className="ml-2 text-xs text-red-600">Failed to queue sync</span>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* All Good Message */}
          {data.issues.length === 0 && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-center gap-3">
              <CheckCircle className="h-6 w-6 text-green-600" />
              <div>
                <p className="text-sm font-medium text-green-800">
                  All integrations healthy!
                </p>
                <p className="text-xs text-green-600">
                  All {data.summary.total_links} product links are configured correctly
                  and will push to their platforms.
                </p>
              </div>
            </div>
          )}

          {/* Product Details (collapsible) */}
          <details className="group">
            <summary className="text-sm font-medium text-gray-700 cursor-pointer hover:text-gray-900">
              Product Link Details ({Object.keys(data.products).length} products)
            </summary>
            <div className="mt-2 max-h-64 overflow-y-auto border rounded-lg">
              <table className="min-w-full text-xs">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium text-gray-600">Product</th>
                    <th className="px-3 py-2 text-left font-medium text-gray-600">Price</th>
                    <th className="px-3 py-2 text-left font-medium text-gray-600">Platforms</th>
                    <th className="px-3 py-2 text-left font-medium text-gray-600">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {Object.entries(data.products).map(([productId, product]) => (
                    <tr key={productId} className="hover:bg-gray-50">
                      <td className="px-3 py-2">
                        <div className="font-medium truncate max-w-37.5">
                          {product.product_name}
                        </div>
                        {product.sku && (
                          <div className="text-gray-400">SKU: {product.sku}</div>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        ${product.current_price?.toFixed(2) || "N/A"}
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex gap-1">
                          {product.platforms_linked.map((link, i) => (
                            <span
                              key={i}
                              className={`px-1.5 py-0.5 rounded text-xs ${
                                link.would_push
                                  ? "bg-green-100 text-green-700"
                                  : "bg-red-100 text-red-700"
                              }`}
                              title={link.would_push ? "Will push" : "Won't push"}
                            >
                              {link.platform}
                            </span>
                          ))}
                          {product.total_platforms === 0 && (
                            <span className="text-gray-400">No links</span>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        {product.active_push_targets === product.total_platforms &&
                        product.total_platforms > 0 ? (
                          <span className="text-green-600">✓ OK</span>
                        ) : product.total_platforms === 0 ? (
                          <span className="text-gray-400">Unlinked</span>
                        ) : (
                          <span className="text-yellow-600">
                            {product.active_push_targets}/{product.total_platforms}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </div>
      )}
    </div>
  );
}


