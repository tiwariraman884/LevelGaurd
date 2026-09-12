'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Camera,
  MapPin,
  Wifi,
  WifiOff,
  Package,
  ArrowRight,
  Loader2,
  AlertCircle,
  PlusCircle,
  Building2,
} from 'lucide-react';
import { ApiClient } from '@/lib/api-client';
import { BackendProduct } from '@/lib/types';

export default function MobileFieldScanSimulator() {
  const router = useRouter();
  const [offlineMode, setOfflineMode] = useState(false);
  const [products, setProducts] = useState<BackendProduct[]>([]);
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null);
  const [storeName, setStoreName] = useState('Central Retail Store, Inspection Point');
  const [district, setDistrict] = useState('Delhi National Capital Region');
  const [gpsCoords, setGpsCoords] = useState<string>('Detecting location...');
  const [latitude, setLatitude] = useState<number | null>(null);
  const [longitude, setLongitude] = useState<number | null>(null);
  const [accuracy, setAccuracy] = useState<number | null>(null);

  const [isLoadingProducts, setIsLoadingProducts] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Capture real geolocation
  useEffect(() => {
    if (typeof window !== 'undefined' && 'geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setLatitude(pos.coords.latitude);
          setLongitude(pos.coords.longitude);
          setAccuracy(pos.coords.accuracy);
          setGpsCoords(`${pos.coords.latitude.toFixed(4)}° N, ${pos.coords.longitude.toFixed(4)}° E`);
        },
        () => {
          setGpsCoords('28.6139° N, 77.2090° E (New Delhi)');
          setLatitude(28.6139);
          setLongitude(77.209);
        },
        { timeout: 5000 }
      );
    } else {
      setGpsCoords('28.6139° N, 77.2090° E');
    }
  }, []);

  // Fetch registered products
  useEffect(() => {
    async function loadProducts() {
      try {
        const list = await ApiClient.getProducts();
        setProducts(list);
        if (list.length > 0) {
          setSelectedProductId(list[0].id);
        }
      } catch (err: any) {
        console.warn('Could not load products list:', err);
      } finally {
        setIsLoadingProducts(false);
      }
    }
    loadProducts();
  }, []);

  const handleStartInspection = async () => {
    setIsCreating(true);
    setErrorMsg(null);

    try {
      const newInspection = await ApiClient.createInspection({
        product_id: selectedProductId,
        latitude: latitude ?? 28.6139,
        longitude: longitude ?? 77.209,
        location_accuracy_m: accuracy ?? 10.0,
        location_captured_at: new Date().toISOString(),
        location_source: `${storeName} (${district})`,
      });

      // Navigate to camera with the real inspection ID
      router.push(`/inspector/camera?inspectionId=${newInspection.id}`);
    } catch (err: any) {
      setErrorMsg(err?.message || 'Failed to create new inspection record on server.');
      setIsCreating(false);
    }
  };

  const selectedProduct = products.find((p) => p.id === selectedProductId);

  return (
    <div className="max-w-xl mx-auto px-4 py-8 space-y-6">
      {/* Mobile Device Frame Header */}
      <div className="bg-zinc-900 text-white rounded-2xl p-5 shadow-xl border border-zinc-800 space-y-4">
        <div className="flex justify-between items-center border-b border-zinc-800 pb-3 text-xs">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
            <span className="font-bold tracking-wider">NEW FIELD INSPECTION</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setOfflineMode(!offlineMode)}
              className={`px-2.5 py-1 rounded text-[11px] font-semibold flex items-center gap-1 transition ${
                offlineMode ? 'bg-amber-900/80 text-amber-300 border border-amber-600' : 'bg-zinc-800 text-emerald-400'
              }`}
            >
              {offlineMode ? <WifiOff className="w-3 h-3" /> : <Wifi className="w-3 h-3" />}
              <span>{offlineMode ? 'Local Cache' : 'Central Server Connected'}</span>
            </button>
          </div>
        </div>

        {/* GPS Geotag Info Box */}
        <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800 text-xs space-y-1.5">
          <div className="flex items-center justify-between text-zinc-400">
            <span className="flex items-center gap-1">
              <MapPin className="w-3.5 h-3.5 text-emerald-400" />
              <span>Inspection Location Geotag</span>
            </span>
            <span className="font-mono text-[10px] text-zinc-400">{gpsCoords}</span>
          </div>
          <div>
            <label className="text-[10px] text-zinc-500 uppercase font-semibold">Store / Inspection Premise</label>
            <input
              type="text"
              value={storeName}
              onChange={(e) => setStoreName(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 rounded px-2.5 py-1 text-zinc-100 text-xs mt-0.5 focus:outline-none focus:border-emerald-500"
              placeholder="Enter premise name or market address"
            />
          </div>
          <div className="pt-1">
            <label className="text-[10px] text-zinc-500 uppercase font-semibold">District / Jurisdiction</label>
            <input
              type="text"
              value={district}
              onChange={(e) => setDistrict(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 rounded px-2.5 py-1 text-zinc-100 text-xs mt-0.5 focus:outline-none focus:border-emerald-500"
              placeholder="District"
            />
          </div>
        </div>

        {/* Product Selection Form */}
        <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-zinc-200 uppercase tracking-wider flex items-center gap-1.5">
              <Package className="w-4 h-4 text-emerald-400" />
              <span>Product / Commodity Reference</span>
            </span>
            <span className="text-[11px] text-zinc-400">
              {products.length} registered in DB
            </span>
          </div>

          {isLoadingProducts ? (
            <div className="py-4 flex items-center justify-center gap-2 text-zinc-400 text-xs">
              <Loader2 className="w-4 h-4 animate-spin text-emerald-400" />
              <span>Loading products catalog...</span>
            </div>
          ) : (
            <div className="space-y-2">
              <label htmlFor="product-select" className="text-xs text-zinc-400">Select target product:</label>
              <select
                id="product-select"
                value={selectedProductId ?? ''}
                onChange={(e) => {
                  const val = e.target.value;
                  setSelectedProductId(val ? parseInt(val, 10) : null);
                }}
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-white text-xs font-medium focus:outline-none focus:border-emerald-500"
              >
                <option value="">-- Unregistered / Spot Inspection Commodity --</option>
                {products.map((prod) => (
                  <option key={prod.id} value={prod.id}>
                    {prod.brand_name ? `[${prod.brand_name}] ` : ''}{prod.product_name} ({prod.category || 'Commodity'})
                  </option>
                ))}
              </select>

              {selectedProduct && (
                <div className="p-3 bg-zinc-900/90 rounded-lg border border-zinc-800 text-[11px] space-y-1 mt-2">
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Brand:</span>
                    <span className="text-zinc-200 font-semibold">{selectedProduct.brand_name || 'Standard'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Manufacturer:</span>
                    <span className="text-zinc-200 truncate max-w-[240px]">{selectedProduct.manufacturer_name || 'Registered on record'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Package Type:</span>
                    <span className="text-emerald-400 font-mono">{selectedProduct.package_type || 'Standard Pkg'}</span>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Error message */}
        {errorMsg && (
          <div className="p-3 rounded-lg bg-rose-950/80 border border-rose-800 text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Action Button */}
        <button
          onClick={handleStartInspection}
          disabled={isCreating}
          className="w-full py-3.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold rounded-xl text-sm flex items-center justify-center gap-2 shadow-lg transition active:scale-[0.99] disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {isCreating ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>Creating Inspection Record...</span>
            </>
          ) : (
            <>
              <Camera className="w-5 h-5" />
              <span>Proceed to Camera Scanner</span>
              <ArrowRight className="w-4 h-4 ml-1" />
            </>
          )}
        </button>
      </div>

      <div className="text-center">
        <Link href="/inspector/scans" className="text-xs font-semibold text-zinc-500 hover:text-zinc-800">
          &larr; Back to Inspection Scans
        </Link>
      </div>
    </div>
  );
}
