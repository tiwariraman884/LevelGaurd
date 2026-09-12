'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import {
  TrendingUp,
  MapPin,
  ShoppingBag,
  AlertTriangle,
  CheckCircle2,
  Layers,
  ArrowUpRight,
  Download,
  Building,
  Loader2,
  Bell,
  CheckCircle,
  FileCheck2,
} from 'lucide-react';
import { ApiClient } from '@/lib/api-client';
import { BackendEscalation, BackendNotification, InspectionRecord } from '@/lib/types';
import { useAuth } from '@/lib/auth-context';

export default function NationalAdminDashboard() {
  const { user } = useAuth();
  const [escalations, setEscalations] = useState<BackendEscalation[]>([]);
  const [notifications, setNotifications] = useState<BackendNotification[]>([]);
  const [inspections, setInspections] = useState<InspectionRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [actionInProgress, setActionInProgress] = useState<number | null>(null);
  const [actionNotes, setActionNotes] = useState<Record<number, string>>({});

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [escs, notifs, insps] = await Promise.all([
        ApiClient.getEscalations().catch(() => [] as BackendEscalation[]),
        ApiClient.getNotifications().catch(() => [] as BackendNotification[]),
        ApiClient.getInspections().catch(() => [] as InspectionRecord[]),
      ]);
      setEscalations(escs);
      setNotifications(notifs);
      setInspections(insps);
    } catch (err) {
      console.error('Failed to load admin dashboard data:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleEscalationAction = async (
    id: number,
    action: 'acknowledge' | 'resolve' | 'refer_state' | 'refer_national'
  ) => {
    setActionInProgress(id);
    try {
      const notes = actionNotes[id] || '';
      await ApiClient.performEscalationAction(id, action, notes);
      await loadData();
    } catch (err: any) {
      alert(`Action failed: ${err?.message || 'Error updating escalation'}`);
    } finally {
      setActionInProgress(null);
    }
  };

  const ecommRankings = [
    { platform: 'Blinkit (Quick Commerce)', scans: 1420, violations: 58, rate: '4.1%', status: 'Leading' },
    { platform: 'Amazon India', scans: 4890, violations: 320, rate: '6.5%', status: 'Compliant' },
    { platform: 'Flipkart', scans: 4100, violations: 390, rate: '9.5%', status: 'Warning' },
    { platform: 'Zepto', scans: 1100, violations: 140, rate: '12.7%', status: 'Audit Ordered' },
  ];

  const totalViolations = inspections.reduce((acc, i) => acc + i.violations.length, 0);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-200 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold px-2 py-0.5 rounded bg-rose-100 text-rose-800 border border-rose-300">
              National Metrology Directorate
            </span>
            <span className="text-xs text-zinc-500 font-mono">
              Admin: {user?.fullName || 'National Administrator'}
            </span>
          </div>
          <h1 className="text-2xl font-bold text-zinc-900 mt-1">National Compliance & Market Governance</h1>
          <p className="text-xs text-zinc-500">
            Multi-tier statutory escalation resolution, Legal Metrology rule administration, and national audit overview.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/admin/rules"
            className="px-4 py-2 bg-purple-700 hover:bg-purple-800 text-white font-semibold rounded-lg text-xs flex items-center gap-1.5 shadow-sm transition"
          >
            <Layers className="w-4 h-4" />
            <span>Manage Codified Rules</span>
          </Link>
          <button
            onClick={loadData}
            disabled={isLoading}
            className="px-3 py-2 bg-white hover:bg-zinc-100 text-zinc-700 border border-zinc-300 rounded-lg text-xs font-semibold transition"
          >
            <span className={isLoading ? 'animate-spin' : ''}>🔄</span>
          </button>
        </div>
      </div>

      {/* Top Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-zinc-200 rounded-xl p-5 shadow-xs">
          <p className="text-xs font-medium text-zinc-500">Total Database Inspections</p>
          <p className="text-3xl font-extrabold text-zinc-900 mt-1">{inspections.length}</p>
          <p className="text-[11px] text-emerald-700 font-semibold mt-1">Central PostgreSQL Live</p>
        </div>

        <div className="bg-white border border-zinc-200 rounded-xl p-5 shadow-xs">
          <p className="text-xs font-medium text-zinc-500">Total Statutory Violations</p>
          <p className="text-3xl font-extrabold text-rose-600 mt-1">{totalViolations}</p>
          <p className="text-[11px] text-zinc-500 mt-1">Under 12 Codified Rules</p>
        </div>

        <div className="bg-white border border-zinc-200 rounded-xl p-5 shadow-xs border-l-4 border-l-purple-600">
          <p className="text-xs font-medium text-zinc-500">Total Escalations</p>
          <p className="text-3xl font-extrabold text-purple-700 mt-1">{escalations.length}</p>
          <p className="text-[11px] text-purple-800 font-semibold mt-1">District / State / National</p>
        </div>

        <div className="bg-white border border-zinc-200 rounded-xl p-5 shadow-xs border-l-4 border-l-blue-600">
          <p className="text-xs font-medium text-zinc-500">Dispatched Notifications</p>
          <p className="text-3xl font-extrabold text-blue-600 mt-1">{notifications.length}</p>
          <p className="text-[11px] text-blue-700 font-semibold mt-1">Audit Logged</p>
        </div>
      </div>

      {/* Multi-Tier Authority Escalations Section */}
      <div className="bg-white border border-zinc-200 rounded-xl shadow-xs p-5 space-y-4">
        <div className="flex justify-between items-center border-b border-zinc-200 pb-3">
          <div>
            <h2 className="text-sm font-bold text-zinc-900 flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4 text-purple-600" />
              <span>Multi-Tier Authority Escalations ({escalations.length})</span>
            </h2>
            <p className="text-xs text-zinc-500">
              Admin oversight across District, State, and National jurisdiction queues.
            </p>
          </div>
        </div>

        {escalations.length === 0 ? (
          <div className="py-8 text-center text-zinc-500 text-xs bg-zinc-50 rounded-lg border border-dashed border-zinc-200">
            No escalations found in database.
          </div>
        ) : (
          <div className="space-y-3">
            {escalations.map((esc) => (
              <div key={esc.id} className="p-4 rounded-xl border border-zinc-200 bg-zinc-50/60 space-y-2.5 text-xs">
                <div className="flex flex-wrap justify-between items-center gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-zinc-900">Escalation #{esc.id}</span>
                    <span className="px-2 py-0.5 rounded font-mono font-bold text-[10px] uppercase bg-purple-100 text-purple-800 border border-purple-200">
                      {esc.level}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded font-mono font-bold text-[10px] uppercase ${
                        esc.status === 'resolved'
                          ? 'bg-emerald-100 text-emerald-800'
                          : 'bg-amber-100 text-amber-800'
                      }`}
                    >
                      {esc.status}
                    </span>
                  </div>
                  <span className="text-zinc-400 font-mono text-[11px]">
                    {new Date(esc.created_at).toLocaleString()}
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-zinc-600">
                  <div>Product: <strong>Product #{esc.product_id}</strong></div>
                  <div>Failures: <strong className="text-rose-700">{esc.failed_inspection_count} times</strong></div>
                  <div>
                    <Link href={`/scan/${esc.trigger_inspection_id}`} className="text-emerald-600 font-semibold hover:underline">
                      Trigger Inspection #{esc.trigger_inspection_id} &rarr;
                    </Link>
                  </div>
                </div>

                <p className="text-zinc-700 bg-white p-2.5 rounded-lg border border-zinc-200">
                  {esc.reason}
                </p>

                {esc.status !== 'resolved' && (
                  <div className="pt-2 flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                    <input
                      type="text"
                      placeholder="Admin action notes..."
                      value={actionNotes[esc.id] || ''}
                      onChange={(e) =>
                        setActionNotes((prev) => ({ ...prev, [esc.id]: e.target.value }))
                      }
                      className="flex-1 bg-white border border-zinc-300 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:border-purple-500"
                    />
                    <div className="flex gap-2">
                      {esc.status === 'open' && (
                        <button
                          onClick={() => handleEscalationAction(esc.id, 'acknowledge')}
                          disabled={actionInProgress === esc.id}
                          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold text-xs transition disabled:opacity-50"
                        >
                          ACK
                        </button>
                      )}
                      <button
                        onClick={() => handleEscalationAction(esc.id, 'resolve')}
                        disabled={actionInProgress === esc.id}
                        className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-semibold text-xs transition disabled:opacity-50"
                      >
                        Resolve
                      </button>
                      {esc.level === 'district' && (
                        <button
                          onClick={() => handleEscalationAction(esc.id, 'refer_state')}
                          disabled={actionInProgress === esc.id}
                          className="px-3 py-1.5 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-semibold text-xs transition disabled:opacity-50"
                        >
                          Refer to State
                        </button>
                      )}
                      {esc.level === 'state' && (
                        <button
                          onClick={() => handleEscalationAction(esc.id, 'refer_national')}
                          disabled={actionInProgress === esc.id}
                          className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-lg font-semibold text-xs transition disabled:opacity-50"
                        >
                          Refer to National
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* E-Commerce Marketplaces Ranking */}
      <div className="bg-white border border-zinc-200 rounded-xl overflow-x-auto shadow-xs">
        <div className="p-5 border-b border-zinc-200">
          <h2 className="text-sm font-bold text-zinc-900">
            E-Commerce Digital Marketplace Compliance Leaderboard
          </h2>
          <p className="text-xs text-zinc-500">
            Verification under Legal Metrology (Packaged Commodities) Amendment Rules, 2022 for digital product listings.
          </p>
        </div>

        <table className="w-full min-w-[550px] text-left text-xs">
          <thead>
            <tr className="bg-zinc-50 border-b border-zinc-200 text-zinc-500 font-semibold uppercase">
              <th className="py-3 px-6">Marketplace Platform</th>
              <th className="py-3 px-4">Audited Listings</th>
              <th className="py-3 px-4">Violations Flagged</th>
              <th className="py-3 px-4">Defect Rate</th>
              <th className="py-3 px-6 text-right">Regulatory Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-200 text-zinc-700">
            {ecommRankings.map((e, i) => (
              <tr key={i} className="hover:bg-zinc-50 transition">
                <td className="py-4 px-6 font-bold text-zinc-900">{e.platform}</td>
                <td className="py-4 px-4 font-mono">{e.scans.toLocaleString()}</td>
                <td className="py-4 px-4 font-mono font-bold text-rose-700">{e.violations}</td>
                <td className="py-4 px-4 font-mono font-bold">{e.rate}</td>
                <td className="py-4 px-6 text-right">
                  <span
                    className={`px-2 py-0.5 rounded font-mono font-bold text-[10px] ${
                      e.status === 'Leading'
                        ? 'bg-emerald-100 text-emerald-800'
                        : e.status === 'Compliant'
                        ? 'bg-blue-100 text-blue-800'
                        : 'bg-rose-100 text-rose-800'
                    }`}
                  >
                    {e.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
