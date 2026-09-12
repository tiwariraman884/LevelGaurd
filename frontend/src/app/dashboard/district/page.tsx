'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import dynamic from 'next/dynamic';

const LeafletMap = dynamic(() => import('@/components/Map'), {
  ssr: false,
  loading: () => <div className="w-full h-full flex items-center justify-center text-zinc-500 bg-zinc-100 animate-pulse">Loading GIS Map...</div>,
});

import {
  Scale,
  AlertTriangle,
  FileCheck2,
  Users,
  MapPin,
  FileText,
  CheckCircle,
  ChevronRight,
  TrendingUp,
  Download,
  ShieldAlert,
  Loader2,
  Bell,
  Send,
  ArrowRight,
  CheckCircle2,
} from 'lucide-react';
import { ApiClient } from '@/lib/api-client';
import { BackendEscalation, BackendNotification, InspectionRecord } from '@/lib/types';
import { useAuth } from '@/lib/auth-context';

export default function DistrictControllerDashboard() {
  const { user } = useAuth();
  const [escalations, setEscalations] = useState<BackendEscalation[]>([]);
  const [notifications, setNotifications] = useState<BackendNotification[]>([]);
  const [inspections, setInspections] = useState<InspectionRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'escalations' | 'notifications' | 'map' | 'notices' | 'offenders'>('escalations');
  const [actionNotes, setActionNotes] = useState<Record<number, string>>({});
  const [actionInProgress, setActionInProgress] = useState<number | null>(null);

  const notices = ApiClient.getNotices();
  const offenders = ApiClient.getRepeatOffenders();

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [escs, notifs, insps] = await Promise.all([
        ApiClient.getEscalations({ level: 'district' }).catch(() => [] as BackendEscalation[]),
        ApiClient.getNotifications().catch(() => [] as BackendNotification[]),
        ApiClient.getInspections().catch(() => [] as InspectionRecord[]),
      ]);
      setEscalations(escs);
      setNotifications(notifs);
      setInspections(insps);
    } catch (err) {
      console.error('Failed to load district dashboard data:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleEscalationAction = async (id: number, action: 'acknowledge' | 'resolve' | 'refer_state') => {
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

  const pendingNoticesCount = notices.filter((n) => n.status === 'draft').length;
  const openEscalationsCount = escalations.filter((e) => e.status !== 'resolved').length;
  const violationsCount = inspections.reduce((acc, i) => acc + i.violations.length, 0);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-zinc-200 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold px-2 py-0.5 rounded bg-amber-100 text-amber-800 border border-amber-300">
              District Authority
            </span>
            <span className="text-xs text-zinc-500 font-mono">
              Officer: {user?.fullName || 'District Collector'}
            </span>
          </div>
          <h1 className="text-2xl font-bold text-zinc-900 mt-1">District Controller Enforcement Center</h1>
          <p className="text-xs text-zinc-500">
            Statutory oversight, product repeat-offender escalations, referral hierarchy, and GIS hotspot tracking.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadData}
            disabled={isLoading}
            className="px-4 py-2 bg-white hover:bg-zinc-100 text-zinc-800 border border-zinc-300 font-semibold rounded-lg text-xs flex items-center gap-1.5 shadow-2xs transition"
          >
            <span className={isLoading ? 'animate-spin' : ''}>🔄</span>
            <span>Refresh Data</span>
          </button>
        </div>
      </div>

      {/* Top 5 KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 text-xs">
        <div className="bg-white border border-zinc-200 rounded-xl p-4 shadow-xs">
          <span className="text-zinc-500 font-medium">Recorded Field Scans</span>
          <p className="text-2xl font-extrabold text-zinc-900 mt-1">{inspections.length}</p>
          <span className="text-[10px] text-emerald-700 font-semibold">Central Database Connected</span>
        </div>

        <div className="bg-white border border-zinc-200 rounded-xl p-4 shadow-xs">
          <span className="text-zinc-500 font-medium">Total Violations Cited</span>
          <p className="text-2xl font-extrabold text-rose-600 mt-1">{violationsCount}</p>
          <span className="text-[10px] text-rose-700 font-semibold">Under LM(PC) Rules 2011</span>
        </div>

        <div className="bg-white border border-zinc-200 rounded-xl p-4 shadow-xs border-l-4 border-l-rose-500">
          <span className="text-zinc-500 font-medium">Active District Escalations</span>
          <p className="text-2xl font-extrabold text-rose-700 mt-1">{openEscalationsCount}</p>
          <span className="text-[10px] text-rose-800 font-semibold">Chronic defect products</span>
        </div>

        <div className="bg-white border border-zinc-200 rounded-xl p-4 shadow-xs border-l-4 border-l-amber-500">
          <span className="text-zinc-500 font-medium">Pending Authority Notices</span>
          <p className="text-2xl font-extrabold text-amber-600 mt-1">{pendingNoticesCount}</p>
          <span className="text-[10px] text-amber-800 font-semibold">Section 36 Compounding</span>
        </div>

        <div className="bg-white border border-zinc-200 rounded-xl p-4 shadow-xs col-span-2 lg:col-span-1">
          <span className="text-zinc-500 font-medium">Authority Notifications</span>
          <p className="text-2xl font-extrabold text-blue-600 mt-1">{notifications.length}</p>
          <span className="text-[10px] text-blue-700 font-semibold">In-App & Email alerts</span>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="flex overflow-x-auto border-b border-zinc-200 text-xs font-semibold gap-0 -mx-4 px-4 sm:mx-0 sm:px-0" style={{ scrollbarWidth: 'none' }}>
        <button
          type="button"
          onClick={() => setActiveTab('escalations')}
          className={`shrink-0 pb-3 px-3 sm:px-4 border-b-2 transition flex items-center gap-1.5 whitespace-nowrap ${
            activeTab === 'escalations' ? 'border-emerald-600 text-emerald-800' : 'border-transparent text-zinc-500 hover:text-zinc-800'
          }`}
        >
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>Escalations ({escalations.length})</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('notifications')}
          className={`shrink-0 pb-3 px-3 sm:px-4 border-b-2 transition flex items-center gap-1.5 whitespace-nowrap ${
            activeTab === 'notifications' ? 'border-emerald-600 text-emerald-800' : 'border-transparent text-zinc-500 hover:text-zinc-800'
          }`}
        >
          <Bell className="w-4 h-4 shrink-0" />
          <span>Notifications ({notifications.length})</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('map')}
          className={`shrink-0 pb-3 px-3 sm:px-4 border-b-2 transition flex items-center gap-1.5 whitespace-nowrap ${
            activeTab === 'map' ? 'border-emerald-600 text-emerald-800' : 'border-transparent text-zinc-500 hover:text-zinc-800'
          }`}
        >
          <MapPin className="w-4 h-4 shrink-0" />
          <span>GIS Map</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('notices')}
          className={`shrink-0 pb-3 px-3 sm:px-4 border-b-2 transition flex items-center gap-1.5 whitespace-nowrap ${
            activeTab === 'notices' ? 'border-emerald-600 text-emerald-800' : 'border-transparent text-zinc-500 hover:text-zinc-800'
          }`}
        >
          <FileText className="w-4 h-4 shrink-0" />
          <span>Notices ({notices.length})</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('offenders')}
          className={`shrink-0 pb-3 px-3 sm:px-4 border-b-2 transition flex items-center gap-1.5 whitespace-nowrap ${
            activeTab === 'offenders' ? 'border-emerald-600 text-emerald-800' : 'border-transparent text-zinc-500 hover:text-zinc-800'
          }`}
        >
          <ShieldAlert className="w-4 h-4 shrink-0" />
          <span>Offenders ({offenders.length})</span>
        </button>
      </div>

      {/* TAB 1: Real Escalations Queue */}
      {activeTab === 'escalations' && (
        <div className="bg-white border border-zinc-200 rounded-xl shadow-xs overflow-x-auto space-y-4 p-4">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-sm font-bold text-zinc-900">District-Level Escalation Actions</h2>
              <p className="text-xs text-zinc-500">
                Products automatically escalated due to repeat non-compliance threshold violations.
              </p>
            </div>
          </div>

          {isLoading ? (
            <div className="py-12 text-center text-zinc-500 text-xs">
              <Loader2 className="w-6 h-6 animate-spin mx-auto text-emerald-600 mb-2" />
              Loading real escalations...
            </div>
          ) : escalations.length === 0 ? (
            <div className="py-12 text-center text-zinc-500 text-xs bg-zinc-50 rounded-lg border border-dashed border-zinc-200">
              No active district-level escalations recorded.
            </div>
          ) : (
            <div className="space-y-4">
              {escalations.map((esc) => (
                <div key={esc.id} className="border border-zinc-200 rounded-xl p-4 bg-zinc-50/50 space-y-3 text-xs">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-200 pb-2">
                    <div className="flex items-center gap-2">
                      <span className="font-bold font-mono text-zinc-900">Escalation #{esc.id}</span>
                      <span className="px-2 py-0.5 rounded font-mono font-bold text-[10px] uppercase bg-rose-100 text-rose-800 border border-rose-200">
                        {esc.level} LEVEL
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded font-mono font-bold text-[10px] uppercase ${
                          esc.status === 'resolved'
                            ? 'bg-emerald-100 text-emerald-800'
                            : esc.status === 'acknowledged'
                            ? 'bg-blue-100 text-blue-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}
                      >
                        {esc.status}
                      </span>
                    </div>
                    <span className="text-zinc-500 font-mono text-[11px]">
                      Created: {new Date(esc.created_at).toLocaleString()}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div>
                      <span className="text-zinc-400 block text-[10px]">Product ID:</span>
                      <span className="font-semibold text-zinc-800">Product #{esc.product_id}</span>
                    </div>
                    <div>
                      <span className="text-zinc-400 block text-[10px]">Failed Inspections Count:</span>
                      <span className="font-mono font-bold text-rose-700">{esc.failed_inspection_count} failures</span>
                    </div>
                    <div>
                      <span className="text-zinc-400 block text-[10px]">Trigger Inspection:</span>
                      <Link href={`/scan/${esc.trigger_inspection_id}`} className="text-emerald-600 font-semibold hover:underline">
                        Inspection #{esc.trigger_inspection_id} &rarr;
                      </Link>
                    </div>
                  </div>

                  <div className="bg-white p-2.5 rounded-lg border border-zinc-200">
                    <span className="text-zinc-400 block text-[10px]">Statutory Grounds / Reason:</span>
                    <p className="text-zinc-800 font-medium mt-0.5">{esc.reason}</p>
                  </div>

                  {esc.status !== 'resolved' && (
                    <div className="pt-2 flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                      <input
                        type="text"
                        placeholder="Action notes / instructions..."
                        value={actionNotes[esc.id] || ''}
                        onChange={(e) =>
                          setActionNotes((prev) => ({ ...prev, [esc.id]: e.target.value }))
                        }
                        className="flex-1 bg-white border border-zinc-300 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:border-emerald-500"
                      />
                      <div className="flex gap-2">
                        {esc.status === 'open' && (
                          <button
                            onClick={() => handleEscalationAction(esc.id, 'acknowledge')}
                            disabled={actionInProgress === esc.id}
                            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold text-xs transition disabled:opacity-50"
                          >
                            Acknowledge
                          </button>
                        )}
                        <button
                          onClick={() => handleEscalationAction(esc.id, 'resolve')}
                          disabled={actionInProgress === esc.id}
                          className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-semibold text-xs transition disabled:opacity-50"
                        >
                          Resolve
                        </button>
                        <button
                          onClick={() => handleEscalationAction(esc.id, 'refer_state')}
                          disabled={actionInProgress === esc.id}
                          className="px-3 py-1.5 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-semibold text-xs transition disabled:opacity-50"
                        >
                          Refer to State &rarr;
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: Notifications Queue */}
      {activeTab === 'notifications' && (
        <div className="bg-white border border-zinc-200 rounded-xl shadow-xs overflow-x-auto p-4 space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-sm font-bold text-zinc-900">Authority Notifications</h2>
              <p className="text-xs text-zinc-500">
                Official statutory notices dispatched to legal metrology authorities.
              </p>
            </div>
          </div>

          {notifications.length === 0 ? (
            <div className="py-12 text-center text-zinc-500 text-xs bg-zinc-50 rounded-lg border border-dashed border-zinc-200">
              No notifications dispatched yet.
            </div>
          ) : (
            <div className="space-y-3">
              {notifications.map((notif) => (
                <div key={notif.id} className="p-3 bg-zinc-50 rounded-lg border border-zinc-200 text-xs space-y-1.5">
                  <div className="flex justify-between items-center">
                    <span className="font-bold text-zinc-900">{notif.subject}</span>
                    <span
                      className={`px-2 py-0.5 rounded font-mono font-bold text-[10px] uppercase ${
                        notif.status === 'sent'
                          ? 'bg-emerald-100 text-emerald-800'
                          : notif.status === 'pending'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-zinc-100 text-zinc-700'
                      }`}
                    >
                      {notif.status}
                    </span>
                  </div>
                  <p className="text-zinc-600">{notif.message}</p>
                  <div className="flex justify-between text-[10px] text-zinc-400 pt-1 font-mono">
                    <span>Role: {notif.recipient_role} • Channel: {notif.channel}</span>
                    <span>{new Date(notif.created_at).toLocaleString()}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 3: GIS Map */}
      {activeTab === 'map' && (
        <div className="space-y-4">
          <div className="bg-white border border-zinc-200 rounded-xl p-6 shadow-xs space-y-4">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 text-xs">
              <span className="font-bold text-zinc-800">
                Spatial Density Hotspot Map (Noida, Greater Noida, Kanpur Retail Corridors)
              </span>
            </div>
            <div className="relative h-64 sm:h-96 w-full rounded-xl overflow-hidden border border-zinc-200 shadow-sm z-0">
              <LeafletMap />
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: Section 36 Notices */}
      {activeTab === 'notices' && (
        <div className="bg-white border border-zinc-200 rounded-xl shadow-xs overflow-x-auto">
          <table className="w-full min-w-[650px] text-left text-xs">
            <thead>
              <tr className="bg-zinc-50 border-b border-zinc-200 text-zinc-500 font-semibold uppercase">
                <th className="py-3 px-6">Notice Number</th>
                <th className="py-3 px-4">Brand & Company</th>
                <th className="py-3 px-4">Violations Cited</th>
                <th className="py-3 px-4">Drafted Date</th>
                <th className="py-3 px-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-200 text-zinc-700">
              {notices.map((n) => (
                <tr key={n.id} className="hover:bg-zinc-50 transition">
                  <td className="py-4 px-6 font-mono font-bold text-zinc-900">{n.noticeNumber}</td>
                  <td className="py-4 px-4">
                    <div className="font-semibold text-zinc-900">{n.brand}</div>
                    <div className="text-[11px] text-zinc-500">{n.companyName}</div>
                  </td>
                  <td className="py-4 px-4">
                    <span className="font-semibold text-rose-700">{n.violations.length} statutory count(s)</span>
                  </td>
                  <td className="py-4 px-4 text-zinc-500 font-mono text-[11px]">
                    {new Date(n.draftedAt).toLocaleDateString()}
                  </td>
                  <td className="py-4 px-4">
                    <span className="px-2 py-0.5 rounded font-mono font-bold text-[10px] uppercase bg-amber-100 text-amber-800 border border-amber-300">
                      {n.status.toUpperCase()}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* TAB 5: Repeat Offenders */}
      {activeTab === 'offenders' && (
        <div className="bg-white border border-zinc-200 rounded-xl shadow-xs overflow-x-auto">
          <table className="w-full min-w-[650px] text-left text-xs">
            <thead>
              <tr className="bg-zinc-50 border-b border-zinc-200 text-zinc-500 font-semibold uppercase">
                <th className="py-3 px-6">Brand Name</th>
                <th className="py-3 px-4">Total Scans</th>
                <th className="py-3 px-4">Violation Count</th>
                <th className="py-3 px-4">Risk Score</th>
                <th className="py-3 px-4">Top Recurring Defect</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-200 text-zinc-700">
              {offenders.map((off, idx) => (
                <tr key={idx} className="hover:bg-zinc-50 transition">
                  <td className="py-4 px-6">
                    <div className="font-bold text-zinc-900">{off.brand}</div>
                    <div className="text-[11px] text-zinc-500">{off.companyName}</div>
                  </td>
                  <td className="py-4 px-4 font-mono">{off.totalScans}</td>
                  <td className="py-4 px-4 font-mono font-bold text-rose-700">{off.violationCount}</td>
                  <td className="py-4 px-4 font-mono">
                    <span className="px-2 py-0.5 rounded font-bold bg-rose-100 text-rose-800">
                      {off.riskScore} / 100
                    </span>
                  </td>
                  <td className="py-4 px-4 text-zinc-700">{off.topViolationRule}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
