import React from "react";

type ProductDetailPageProps = {
  params: {
    productId: string;
  };
};

export default function ProductDetailPage({ params }: ProductDetailPageProps) {
  return (
    <div>
      <h1 className="text-xl font-semibold mb-2">
        Product details – {params.productId}
      </h1>
      <p className="text-sm text-slate-500">
        Here you’ll see price history, sentiment, and competitor comparisons.
      </p>
    </div>
  );
}
