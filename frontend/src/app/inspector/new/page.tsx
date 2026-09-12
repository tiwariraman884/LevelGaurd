'use client';

<<<<<<< HEAD
import React, { useState, useEffect } from 'react';
=======
import React, { useState } from 'react';
>>>>>>> origin/main
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Camera,
  MapPin,
  Wifi,
  WifiOff,
<<<<<<< HEAD
  Package,
  ArrowRight,
  Loader2,
  AlertCircle,
  PlusCircle,
  Building2,
} from 'lucide-react';
import { ApiClient } from '@/lib/api-client';
import { BackendProduct } from '@/lib/types';
=======
  AlertTriangle,
  CheckCircle,
  ScanLine,
  Layers,
  ArrowRight,
  RotateCcw,
  Sparkles,
} from 'lucide-react';
>>>>>>> origin/main

export default function MobileFieldScanSimulator() {
  const router = useRouter();
  const [offlineMode, setOfflineMode] = useState(false);
<<<<<<< HEAD
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
=======
  const [storeName, setStoreName] = useState('Aggarwal Departmental Store, Sector 62');
  const [district, setDistrict] = useState('Gautam Buddha Nagar');
  const [gpsCoords, setGpsCoords] = useState('28.6139° N, 77.3592° E');
  const [blurSimulation, setBlurSimulation] = useState(false);
  const [step, setStep] = useState<'capture' | 'quality_check' | 'preview' | 'syncing'>('capture');
  const [sampleType, setSampleType] = useState<'clean' | 'dual_mrp'>('dual_mrp');

  const handleCapture = () => {
    setStep('quality_check');
    setTimeout(() => {
      if (blurSimulation) {
        // Quality check fails
        setStep('capture');
        alert('Image Quality Gate Failed: High optical blur detected (blur score 42.1 > 25 threshold). Please steady device and retake photo.');
      } else {
        setStep('preview');
      }
    }, 800);
  };

  const handleSync = () => {
    setStep('syncing');
    setTimeout(() => {
      if (sampleType === 'dual_mrp') {
        router.push('/scan/INSP-2026-003');
      } else {
        router.push('/scan/INSP-2026-001');
      }
    }, 1200);
  };
>>>>>>> origin/main

  return (
    <div className="max-w-xl mx-auto px-4 py-8 space-y-6">
      {/* Mobile Device Frame Header */}
      <div className="bg-zinc-900 text-white rounded-2xl p-5 shadow-xl border border-zinc-800 space-y-4">
        <div className="flex justify-between items-center border-b border-zinc-800 pb-3 text-xs">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
<<<<<<< HEAD
            <span className="font-bold tracking-wider">NEW FIELD INSPECTION</span>
=======
            <span className="font-bold tracking-wider">INSPECTOR FIELD APP</span>
>>>>>>> origin/main
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setOfflineMode(!offlineMode)}
              className={`px-2.5 py-1 rounded text-[11px] font-semibold flex items-center gap-1 transition ${
                offlineMode ? 'bg-amber-900/80 text-amber-300 border border-amber-600' : 'bg-zinc-800 text-emerald-400'
              }`}
            >
              {offlineMode ? <WifiOff className="w-3 h-3" /> : <Wifi className="w-3 h-3" />}
<<<<<<< HEAD
              <span>{offlineMode ? 'Local Cache' : 'Central Server Connected'}</span>
=======
              <span>{offlineMode ? 'Offline Mode' : 'Online (MeghRaj)'}</span>
>>>>>>> origin/main
            </button>
          </div>
        </div>

        {/* GPS Geotag Info Box */}
<<<<<<< HEAD
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
=======
        <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800 text-xs space-y-1">
          <div className="flex items-center justify-between text-zinc-400">
            <span className="flex items-center gap-1">
              <MapPin className="w-3.5 h-3.5 text-emerald-400" />
              <span>Auto-Geotagged Location</span>
            </span>
            <span className="font-mono text-[10px] text-zinc-500">{gpsCoords}</span>
          </div>
          <p className="font-semibold text-zinc-100">{storeName}</p>
          <p className="text-[11px] text-zinc-400">{district}, Uttar Pradesh</p>
        </div>

        {/* Capture Stage */}
        {step === 'capture' && (
          <div className="space-y-4">
            <div className="relative rounded-xl overflow-hidden border-2 border-zinc-700 bg-black h-72 flex flex-col items-center justify-center text-center p-4">
              <img
                src={
                  sampleType === 'dual_mrp'
                    ? 'https://images.unsplash.com/photo-1566478989037-eec170784d0b?auto=format&fit=crop&w=600&q=80'
                    : 'https://images.unsplash.com/photo-1590080875515-8a3a8dc5735e?auto=format&fit=crop&w=600&q=80'
                }
                alt="Camera viewfinder"
                className={`w-full h-full object-cover opacity-80 ${blurSimulation ? 'blur-xs' : ''}`}
              />

              {/* Viewfinder Overlay Lines */}
              <div className="absolute inset-8 border border-white/40 rounded-lg pointer-events-none flex items-center justify-center">
                <span className="text-[10px] font-mono tracking-widest text-white/70 bg-black/60 px-2 py-0.5 rounded">
                  ALIGN MANDATORY DECLARATION PANEL
                </span>
              </div>
            </div>

            {/* Test Controls */}
            <div className="bg-zinc-950 p-3 rounded-lg border border-zinc-800 space-y-2 text-xs">
              <div className="flex justify-between items-center">
                <span className="text-zinc-400 font-medium">Test Packaging Scenario:</span>
                <select
                  value={sampleType}
                  onChange={(e) => setSampleType(e.target.value as any)}
                  className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-white text-xs"
                >
                  <option value="dual_mrp">Dual-MRP Tampered Chips</option>
                  <option value="clean">Compliant Biscuit Box</option>
                </select>
              </div>

              <div className="flex justify-between items-center pt-1 border-t border-zinc-800">
                <span className="text-zinc-400 font-medium">Simulate Unsteady / Blurry Photo:</span>
                <input
                  type="checkbox"
                  checked={blurSimulation}
                  onChange={(e) => setBlurSimulation(e.target.checked)}
                  className="w-4 h-4 rounded text-emerald-600 focus:ring-0"
                />
              </div>
            </div>

            <button
              onClick={handleCapture}
              className="w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl text-sm flex items-center justify-center gap-2 shadow-lg transition"
            >
              <Camera className="w-5 h-5" />
              <span>Capture Packaging Photo</span>
            </button>
          </div>
        )}

        {/* Quality Check Spinner */}
        {step === 'quality_check' && (
          <div className="py-16 text-center space-y-3">
            <div className="w-10 h-10 border-3 border-emerald-400 border-t-transparent rounded-full animate-spin mx-auto"></div>
            <p className="text-sm font-semibold text-zinc-200">Evaluating Edge Quality Gate...</p>
            <p className="text-xs text-zinc-500">Checking blur index, glare reflections, and pixel sharpness.</p>
          </div>
        )}

        {/* Offline Quick Preview Mode */}
        {step === 'preview' && (
          <div className="space-y-4 text-xs">
            <div className="bg-emerald-950/70 border border-emerald-800 p-3 rounded-lg text-emerald-300 flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>Quality gate passed. Ready for local preview and cloud transmission.</span>
            </div>

            <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800 space-y-3">
              <p className="font-bold text-zinc-200 uppercase tracking-wider text-[11px]">
                On-Device Quick OCR Preview (Works Without Internet)
              </p>
              <div className="space-y-1.5 font-mono text-[11px] text-zinc-300">
                <div className="flex justify-between">
                  <span className="text-zinc-500">Declared MRP:</span>
                  <span className="text-emerald-400">{sampleType === 'dual_mrp' ? '₹ 50.00 (Tampered Sticker)' : '₹ 145.00'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Net Quantity:</span>
                  <span>{sampleType === 'dual_mrp' ? '75 g' : '500 g'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">Tamper Anomaly:</span>
                  <span className={sampleType === 'dual_mrp' ? 'text-rose-400 font-bold' : 'text-emerald-400'}>
                    {sampleType === 'dual_mrp' ? 'SUSPECTED DOUBLE EDGE' : 'NONE DETECTED'}
                  </span>
                </div>
              </div>
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => setStep('capture')}
                className="flex-1 py-2.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-semibold rounded-xl text-xs"
              >
                Retake Photo
              </button>
              <button
                onClick={handleSync}
                className="flex-1 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl text-xs flex items-center justify-center gap-1.5 shadow-md"
              >
                <span>Transmit to Server</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Syncing Animation */}
        {step === 'syncing' && (
          <div className="py-16 text-center space-y-3">
            <div className="w-10 h-10 border-3 border-emerald-400 border-t-transparent rounded-full animate-spin mx-auto"></div>
            <p className="text-sm font-semibold text-zinc-200">Syncing with Central Repository...</p>
            <p className="text-xs text-zinc-500">Signing EXIF metadata, storing evidence, drafting notices if critical.</p>
          </div>
        )}
>>>>>>> origin/main
      </div>

      <div className="text-center">
        <Link href="/inspector/scans" className="text-xs font-semibold text-zinc-500 hover:text-zinc-800">
<<<<<<< HEAD
          &larr; Back to Inspection Scans
=======
          &larr; Back to Field Inspection List
>>>>>>> origin/main
        </Link>
      </div>
    </div>
  );
}
