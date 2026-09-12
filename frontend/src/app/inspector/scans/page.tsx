'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import {
  ScanLine,
  PlusCircle,
  MapPin,
  AlertTriangle,
  CheckCircle2,
  ArrowUpRight,
  Filter,
  RotateCw,
  Loader2,
  Package,
} from 'lucide-react';
import { ApiClient } from '@/lib/api-client';
import { InspectionRecord } from '@/lib/types';
import { useAuth } from '@/lib/auth-context';

export default function InspectorScansPage() {
  const { user } = useAuth();
  const [inspections, setInspections] = useState<InspectionRecord[]>([]);
  const [filter, setFilter] = useState<'all' | 'compliant' | 'violation'>('all');
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadInspections = useCallback(async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const data = await ApiClient.getInspections();
      setInspections(data);
    } catch (err: any) {
      console.error('Failed to load inspections:', err);
      setErrorMsg(err?.message || 'Could not fetch inspections from server.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadInspections();
  }, [loadInspections]);

  const filtered = inspections.filter((i) => {
    if (filter === 'compliant') return i.status === 'COMPLIANT';
    if (filter === 'violation') return i.status === 'NON_COMPLIANT' || i.status === 'REVIEW';
    return true;
  });

  const statusBadge = (item: InspectionRecord) => {
    if (item.status === 'COMPLIANT') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
          <CheckCircle2 className="w-3 h-3" /> COMPLIANT
        </span>
      );
    }
    if (item.status === 'REVIEW') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-100 text-amber-800 border border-amber-300">
          <AlertTriangle className="w-3 h-3" /> REVIEW
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-rose-100 text-rose-800 border border-rose-300">
        <AlertTriangle className="w-3 h-3" /> NON-COMPLIANT
      </span>
    );
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-zinc-200 pb-4">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-semibold px-2 py-0.5 rounded bg-blue-100 text-blue-800 border border-blue-300">
              Field Enforcement
            </span>
            <span className="text-xs text-zinc-500 font-mono">
              Officer: {user?.fullName || 'Legal Metrology Inspector'}
            </span>
          </div>
          <h1 className="text-xl sm:text-2xl font-bold text-zinc-900 mt-1">Field Inspection &amp; Shelf Scans</h1>
          <p className="text-xs text-zinc-500">
            Real-time packaged commodity compliance audits, declaration extractions, and statutory findings.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={loadInspections}
            disabled={isLoading}
            className="touch-compact p-2 min-h-[36px] bg-white hover:bg-zinc-100 text-zinc-700 border border-zinc-300 rounded-lg text-xs font-semibold shadow-xs flex items-center justify-center transition disabled:opacity-50"
            title="Refresh List"
            aria-label="Refresh inspection list"
          >
            <RotateCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
          <Link
            href="/inspector/new"
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-lg text-xs flex items-center gap-1.5 shadow-sm transition min-h-[36px] touch-compact"
          >
            <PlusCircle className="w-4 h-4" />
            <span>New Inspection</span>
          </Link>
        </div>
      </div>

      {/* Error state */}
      {errorMsg && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span>⚠️</span>
            <span>{errorMsg}</span>
          </div>
          <button
            type="button"
            onClick={loadInspections}
            className="shrink-0 px-3 py-1 bg-red-100 hover:bg-red-200 text-red-800 rounded font-semibold text-xs transition"
          >
            Retry
          </button>
        </div>
      )}

      {/* Filters Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-3 rounded-xl border border-zinc-200 shadow-xs text-xs">
        <div className="flex flex-wrap items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-zinc-500 shrink-0" />
          <span className="font-semibold text-zinc-700">Filter:</span>
          <button
            type="button"
            onClick={() => setFilter('all')}
            className={`touch-compact min-h-[32px] px-3 py-1 rounded-md transition ${filter === 'all' ? 'bg-zinc-900 text-white font-semibold' : 'bg-zinc-100 text-zinc-700 hover:bg-zinc-200'}`}
          >
            All ({inspections.length})
          </button>
          <button
            type="button"
            onClick={() => setFilter('compliant')}
            className={`touch-compact min-h-[32px] px-3 py-1 rounded-md transition ${filter === 'compliant' ? 'bg-emerald-600 text-white font-semibold' : 'bg-emerald-50 text-emerald-800 hover:bg-emerald-100'}`}
          >
            Compliant
          </button>
          <button
            type="button"
            onClick={() => setFilter('violation')}
            className={`touch-compact min-h-[32px] px-3 py-1 rounded-md transition ${filter === 'violation' ? 'bg-rose-600 text-white font-semibold' : 'bg-rose-50 text-rose-800 hover:bg-rose-100'}`}
          >
            Violations / Review
          </button>
        </div>

        <span className="text-zinc-500 text-[11px]">
          Showing <strong>{filtered.length}</strong> records
        </span>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="bg-white border border-zinc-200 rounded-xl py-16 text-center space-y-3">
          <Loader2 className="w-8 h-8 animate-spin text-emerald-600 mx-auto" />
          <p className="text-xs font-semibold text-zinc-600">Loading inspection records from database...</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="bg-white border border-zinc-200 rounded-xl py-16 text-center space-y-4 px-4">
          <div className="w-12 h-12 rounded-full bg-zinc-100 text-zinc-400 flex items-center justify-center mx-auto">
            <Package className="w-6 h-6" />
          </div>
          <div>
            <p className="text-sm font-bold text-zinc-800">No inspections found</p>
            <p className="text-xs text-zinc-500 mt-1">
              {filter !== 'all' ? 'Try changing the filter option above.' : 'Start a new inspection using the product catalog.'}
            </p>
          </div>
          <Link
            href="/inspector/new"
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-lg text-xs inline-flex items-center gap-1.5"
          >
            <PlusCircle className="w-4 h-4" />
            <span>Create First Inspection</span>
          </Link>
        </div>
      ) : (
        <>
          {/* Mobile: card list (< md) */}
          <div className="md:hidden space-y-3">
            {filtered.map((item) => (
              <div key={item.id} className="bg-white border border-zinc-200 rounded-xl p-4 shadow-xs space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-semibold text-zinc-900 text-sm truncate">{item.productName}</p>
                    <p className="text-[11px] text-zinc-500 font-mono mt-0.5">Ref: #{item.id} · SKU: {item.sku}</p>
                  </div>
                  <span
                    className={`shrink-0 px-2 py-0.5 rounded font-mono font-bold text-xs ${
                      item.complianceScore >= 90
                        ? 'bg-emerald-100 text-emerald-800'
                        : item.complianceScore >= 60
                        ? 'bg-amber-100 text-amber-800'
                        : 'bg-rose-100 text-rose-800'
                    }`}
                  >
                    {item.complianceScore}%
                  </span>
                </div>

                <div className="flex items-center gap-1 text-xs text-zinc-600">
                  <MapPin className="w-3 h-3 text-emerald-600 shrink-0" />
                  <span className="truncate">{item.storeName || 'Field Inspection Point'} · {item.location || 'Field Scan'}</span>
                </div>

                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    {statusBadge(item)}
                    {item.violations.length > 0 && (
                      <span className="text-[11px] font-semibold text-rose-700 font-mono">
                        {item.violations.length} violation{item.violations.length > 1 ? 's' : ''}
                      </span>
                    )}
                  </div>
                  <Link
                    href={`/scan/${item.id}`}
                    className="shrink-0 px-3 py-1.5 bg-zinc-100 hover:bg-zinc-200 text-zinc-800 rounded-lg font-medium text-xs transition inline-flex items-center gap-1"
                  >
                    <span>View</span>
                    <ArrowUpRight className="w-3 h-3" />
                  </Link>
                </div>

                <p className="text-[11px] text-zinc-400 font-mono">
                  {new Date(item.createdAt).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' })}
                </p>
              </div>
            ))}
          </div>

          {/* Desktop: table (md+) */}
          <div className="hidden md:block bg-white border border-zinc-200 rounded-xl overflow-x-auto shadow-xs">
            <table className="w-full min-w-[700px] text-left text-xs">
              <thead>
                <tr className="bg-zinc-50 border-b border-zinc-200 text-zinc-500 font-semibold uppercase tracking-wider">
                  <th className="py-3 px-6">Product / Reference</th>
                  <th className="py-3 px-4">Retail Location &amp; Premise</th>
                  <th className="py-3 px-4 text-center">Score</th>
                  <th className="py-3 px-4">Compliance Status</th>
                  <th className="py-3 px-4">Violations</th>
                  <th className="py-3 px-4">Date &amp; Time</th>
                  <th className="py-3 px-6 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 text-zinc-700">
                {filtered.map((item) => (
                  <tr key={item.id} className="hover:bg-zinc-50/80 transition">
                    <td className="py-4 px-6">
                      <div className="font-semibold text-zinc-900">{item.productName}</div>
                      <div className="text-[11px] text-zinc-500">Ref: #{item.id} • SKU: {item.sku}</div>
                    </td>
                    <td className="py-4 px-4">
                      <div className="font-medium text-zinc-900">{item.storeName || 'Inspection Point'}</div>
                      <div className="text-[11px] text-zinc-500 flex items-center gap-1 mt-0.5">
                        <MapPin className="w-3 h-3 text-emerald-600 shrink-0" />
                        <span>{item.location || 'Field Scan'}</span>
                      </div>
                    </td>
                    <td className="py-4 px-4 text-center">
                      <span
                        className={`inline-block px-2 py-0.5 rounded font-mono font-bold ${
                          item.complianceScore >= 90
                            ? 'bg-emerald-100 text-emerald-800'
                            : item.complianceScore >= 60
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-rose-100 text-rose-800'
                        }`}
                      >
                        {item.complianceScore}%
                      </span>
                    </td>
                    <td className="py-4 px-4">{statusBadge(item)}</td>
                    <td className="py-4 px-4">
                      {item.violations.length > 0 ? (
                        <span className="font-semibold text-rose-700 font-mono">
                          {item.violations.length} cited
                        </span>
                      ) : (
                        <span className="text-zinc-400 font-mono text-[11px]">None</span>
                      )}
                    </td>
                    <td className="py-4 px-4 text-zinc-500 font-mono text-[11px]">
                      {new Date(item.createdAt).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' })}
                    </td>
                    <td className="py-4 px-6 text-right">
                      <Link
                        href={`/scan/${item.id}`}
                        className="px-3 py-1 bg-zinc-100 hover:bg-zinc-200 text-zinc-800 rounded font-medium text-[11px] transition inline-flex items-center gap-1"
                      >
                        <span>View Details</span>
                        <ArrowUpRight className="w-3 h-3" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
