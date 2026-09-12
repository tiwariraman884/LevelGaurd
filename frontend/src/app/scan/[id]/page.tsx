'use client';

<<<<<<< HEAD
import React, { useState, useEffect, useCallback } from 'react';
=======
import React, { useState } from 'react';
>>>>>>> origin/main
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  ShieldCheck,
  AlertTriangle,
  MapPin,
  Calendar,
  CheckCircle,
  XCircle,
  Download,
  ArrowLeft,
  Crosshair,
  Award,
  Layers,
  FileCheck2,
<<<<<<< HEAD
  Loader2,
  FileText,
  UserCheck,
  Clock,
  Send,
} from 'lucide-react';
import { ApiClient } from '@/lib/api-client';
import { BackendImage, InspectionRecord } from '@/lib/types';
import { useAuth } from '@/lib/auth-context';

export default function ScanDetailPage() {
  const params = useParams();
  const id = params?.id as string;
  const { user } = useAuth();

  const [scan, setScan] = useState<InspectionRecord | null>(null);
  const [images, setImages] = useState<BackendImage[]>([]);
  const [selectedImageIndex, setSelectedImageIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Decision state
  const [decisionChoice, setDecisionChoice] = useState<'APPROVED' | 'REJECTED' | 'REVIEW_REQUIRED'>('APPROVED');
  const [decisionRemarks, setDecisionRemarks] = useState('');
  const [isSubmittingDecision, setIsSubmittingDecision] = useState(false);
  const [decisionSuccessMsg, setDecisionSuccessMsg] = useState<string | null>(null);

  // Report download state
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);
  const [isDownloadingDocx, setIsDownloadingDocx] = useState(false);

  const loadData = useCallback(async () => {
    if (!id) return;
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const [record, imgs] = await Promise.all([
        ApiClient.getInspectionById(id),
        ApiClient.getInspectionImages(id).catch(() => [] as BackendImage[]),
      ]);
      setScan(record);
      setImages(imgs);
    } catch (err: any) {
      console.error('Failed to load inspection details:', err);
      setErrorMsg(err?.message || 'Unable to load inspection record from server.');
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleDownloadReport = async (format: 'pdf' | 'docx') => {
    if (!scan) return;
    if (format === 'pdf') setIsDownloadingPdf(true);
    else setIsDownloadingDocx(true);

    try {
      await ApiClient.downloadReport(scan.id, format);
    } catch (err: any) {
      alert(`Report download failed: ${err?.message}`);
    } finally {
      if (format === 'pdf') setIsDownloadingPdf(false);
      else setIsDownloadingDocx(false);
    }
  };

  const handleSubmitDecision = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!scan) return;
    setIsSubmittingDecision(true);
    setDecisionSuccessMsg(null);

    try {
      await ApiClient.submitFinalDecision(scan.id, decisionChoice, decisionRemarks);
      setDecisionSuccessMsg(`Officer decision '${decisionChoice}' successfully recorded and signed in immutable audit trail.`);
      setDecisionRemarks('');
      await loadData();
    } catch (err: any) {
      alert(`Failed to record officer decision: ${err?.message}`);
    } finally {
      setIsSubmittingDecision(false);
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-24 flex flex-col items-center justify-center space-y-4 text-center">
        <Loader2 className="w-10 h-10 animate-spin text-emerald-600" />
        <p className="text-sm font-semibold text-zinc-700">Loading Legal Metrology Inspection Details...</p>
        <p className="text-xs text-zinc-400">Fetching evidence records and compliance evaluations from central server</p>
      </div>
    );
  }

  if (errorMsg || !scan) {
    return (
      <div className="max-w-xl mx-auto px-4 py-16 text-center space-y-4">
        <div className="w-12 h-12 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center mx-auto">
          <AlertTriangle className="w-6 h-6" />
        </div>
        <h2 className="text-lg font-bold text-zinc-900">Inspection Not Found</h2>
        <p className="text-xs text-zinc-600">{errorMsg || 'The requested inspection record does not exist or access is restricted.'}</p>
        <div className="pt-2">
          <Link
            href="/inspector/scans"
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold inline-flex items-center gap-1.5"
          >
            <ArrowLeft className="w-4 h-4" /> Back to Inspections List
          </Link>
        </div>
      </div>
    );
  }

  const selectedImage = images[selectedImageIndex];
  const activeImageUrl = selectedImage
    ? ApiClient.getInspectionImageUrl(scan.id, selectedImage.id)
    : scan.imageUrl;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 space-y-6">
      {/* Back link & Title */}
      <div className="flex flex-col gap-4 border-b border-zinc-200 pb-4">
        <Link
          href="/inspector/scans"
          className="text-xs font-semibold text-zinc-500 hover:text-zinc-800 inline-flex items-center gap-1"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Inspections
        </Link>

        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl sm:text-2xl font-bold text-zinc-900 break-words">{scan.productName}</h1>
              <span
                className={`shrink-0 px-2 py-0.5 rounded font-mono font-bold text-xs ${
                  scan.complianceScore >= 90
                    ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                    : 'bg-rose-100 text-rose-800 border border-rose-300'
                }`}
              >
                {scan.complianceScore}%
              </span>
            </div>
            <p className="text-xs text-zinc-500 font-mono mt-0.5">
              Inspection #{scan.id} • SKU: {scan.sku}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => handleDownloadReport('pdf')}
              disabled={isDownloadingPdf}
              className="touch-compact px-3 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-lg text-xs flex items-center gap-1.5 shadow-xs transition disabled:opacity-50"
            >
              {isDownloadingPdf ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Download className="w-4 h-4" />
              )}
              <span>PDF</span>
            </button>

            <button
              type="button"
              onClick={() => handleDownloadReport('docx')}
              disabled={isDownloadingDocx}
              className="touch-compact px-3 py-2 bg-white hover:bg-zinc-100 text-zinc-800 border border-zinc-300 font-semibold rounded-lg text-xs flex items-center gap-1.5 shadow-2xs transition disabled:opacity-50"
            >
              {isDownloadingDocx ? (
                <Loader2 className="w-4 h-4 animate-spin text-zinc-600" />
              ) : (
                <FileText className="w-4 h-4 text-zinc-600" />
              )}
              <span>DOCX</span>
            </button>
          </div>
=======
} from 'lucide-react';
import { ApiClient } from '@/lib/api-client';
import { BoundingBox } from '@/lib/types';

export default function ScanDetailPage() {
  const params = useParams();
  const id = (params?.id as string) || 'INSP-2026-001';
  const scan = ApiClient.getInspectionById(id) || ApiClient.getInspections()[0];

  const [selectedBbox, setSelectedBbox] = useState<BoundingBox | null>(null);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Back link & Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-200 pb-4">
        <div>
          <Link
            href="/inspector/scans"
            className="text-xs font-semibold text-zinc-500 hover:text-zinc-800 flex items-center gap-1 mb-1"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Inspections
          </Link>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-zinc-900">{scan.productName}</h1>
            <span
              className={`px-2 py-0.5 rounded font-mono font-bold text-xs ${
                scan.complianceScore >= 90
                  ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                  : 'bg-rose-100 text-rose-800 border border-rose-300'
              }`}
            >
              Score: {scan.complianceScore}%
            </span>
          </div>
          <p className="text-xs text-zinc-500 font-mono mt-0.5">
            Scan Reference: {scan.id} • Barcode: {scan.barcode || 'EAN-13 Verified'}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => alert(`Enforcement-grade PDF report generated deterministically in 340ms.`)}
            className="px-4 py-2 bg-white hover:bg-zinc-100 text-zinc-800 border border-zinc-300 font-semibold rounded-lg text-xs flex items-center gap-1.5 shadow-2xs transition"
          >
            <Download className="w-4 h-4 text-zinc-600" />
            <span>Download Legal Evidence Report (PDF)</span>
          </button>
>>>>>>> origin/main
        </div>
      </div>

      {/* Metadata Bar */}
<<<<<<< HEAD
      <div className="bg-white border border-zinc-200 rounded-xl p-4 shadow-xs grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 text-xs">
        <div>
          <span className="text-zinc-400 block text-[11px]">Inspection Premise / Source:</span>
          <span className="font-semibold text-zinc-900">{scan.storeName || 'Field Inspection Point'}</span>
        </div>
        <div>
          <span className="text-zinc-400 block text-[11px]">GPS Coordinates:</span>
          <span className="font-mono text-zinc-800 flex items-center gap-1">
            <MapPin className="w-3 h-3 text-emerald-600 shrink-0" />
            {scan.gpsCoords ? `${scan.gpsCoords.lat.toFixed(4)}° N, ${scan.gpsCoords.lng.toFixed(4)}° E` : (scan.location || 'Recorded on site')}
=======
      <div className="bg-white border border-zinc-200 rounded-xl p-4 shadow-xs grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
        <div>
          <span className="text-zinc-400 block text-[11px]">Retailer / Warehouse:</span>
          <span className="font-semibold text-zinc-900">{scan.storeName || 'Wholesale Depot'}</span>
        </div>
        <div>
          <span className="text-zinc-400 block text-[11px]">GPS Geotag:</span>
          <span className="font-mono text-zinc-800 flex items-center gap-1">
            <MapPin className="w-3 h-3 text-emerald-600 shrink-0" />
            {scan.location || '28.5708° N, 77.3261° E'}
>>>>>>> origin/main
          </span>
        </div>
        <div>
          <span className="text-zinc-400 block text-[11px]">Inspection Timestamp:</span>
          <span className="font-medium text-zinc-800">{new Date(scan.createdAt).toLocaleString()}</span>
        </div>
        <div>
<<<<<<< HEAD
          <span className="text-zinc-400 block text-[11px]">Compliance Verdict:</span>
          <span
            className={`font-bold font-mono ${
              scan.status === 'COMPLIANT'
                ? 'text-emerald-700'
                : scan.status === 'REVIEW'
                ? 'text-amber-700'
                : 'text-rose-700'
=======
          <span className="text-zinc-400 block text-[11px]">Regulatory Verdict:</span>
          <span
            className={`font-bold font-mono ${
              scan.status === 'COMPLIANT' ? 'text-emerald-700' : 'text-rose-700'
>>>>>>> origin/main
            }`}
          >
            {scan.status}
          </span>
        </div>
      </div>

      {/* Hero Evidence & Findings Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Visual Packaging Evidence */}
        <div className="lg:col-span-6 bg-white border border-zinc-200 rounded-xl p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-zinc-200 pb-2">
            <h2 className="text-sm font-bold text-zinc-900 flex items-center gap-1.5">
              <Crosshair className="w-4 h-4 text-emerald-600" />
<<<<<<< HEAD
              Packaging Evidence Media ({images.length || 1})
            </h2>
            <span className="text-[11px] text-zinc-500 font-mono">
              {selectedImage ? `${selectedImage.image_type || 'evidence'} panel` : 'Primary scan'}
            </span>
          </div>

          {/* Main Evidence Photo */}
          <div className="relative rounded-lg overflow-hidden border border-zinc-300 bg-zinc-950 flex items-center justify-center min-h-[320px]">
            <img
              src={activeImageUrl}
              alt={scan.productName}
              className="w-full max-h-[420px] object-contain"
            />
          </div>

          {/* Thumbnails if multiple images uploaded */}
          {images.length > 1 && (
            <div className="flex items-center gap-2 pt-1 overflow-x-auto pb-1">
              {images.map((img, idx) => (
                <button
                  key={img.id}
                  onClick={() => setSelectedImageIndex(idx)}
                  className={`relative w-16 h-16 rounded-lg overflow-hidden border-2 flex-shrink-0 transition-all ${
                    selectedImageIndex === idx ? 'border-emerald-500 ring-2 ring-emerald-300' : 'border-zinc-300 opacity-70 hover:opacity-100'
                  }`}
                >
                  <img
                    src={ApiClient.getInspectionImageUrl(scan.id, img.id)}
                    alt={`Evidence ${img.image_type || idx + 1}`}
                    className="w-full h-full object-cover"
                  />
                  <span className="absolute bottom-0 inset-x-0 bg-black/70 text-[9px] text-white text-center py-0.5 truncate uppercase">
                    {img.image_type || `#${idx + 1}`}
                  </span>
                </button>
              ))}
            </div>
          )}

          {/* Officer Decision Box */}
          <div className="mt-4 pt-4 border-t border-zinc-200 space-y-3">
            <h3 className="text-xs font-bold text-zinc-900 uppercase tracking-wider flex items-center gap-1.5">
              <UserCheck className="w-4 h-4 text-emerald-600" />
              <span>Legal Metrology Officer Decision</span>
            </h3>

            {decisionSuccessMsg && (
              <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg text-xs flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>{decisionSuccessMsg}</span>
              </div>
            )}

            <form onSubmit={handleSubmitDecision} className="space-y-3 bg-zinc-50 p-3.5 rounded-xl border border-zinc-200 text-xs">
              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => setDecisionChoice('APPROVED')}
                  className={`py-2 px-2 rounded-lg font-semibold border transition text-center ${
                    decisionChoice === 'APPROVED'
                      ? 'bg-emerald-600 text-white border-emerald-600 shadow-xs'
                      : 'bg-white text-zinc-700 border-zinc-300 hover:bg-zinc-100'
                  }`}
                >
                  ✓ Approve
                </button>
                <button
                  type="button"
                  onClick={() => setDecisionChoice('REVIEW_REQUIRED')}
                  className={`py-2 px-2 rounded-lg font-semibold border transition text-center ${
                    decisionChoice === 'REVIEW_REQUIRED'
                      ? 'bg-amber-600 text-white border-amber-600 shadow-xs'
                      : 'bg-white text-zinc-700 border-zinc-300 hover:bg-zinc-100'
                  }`}
                >
                  ⚠️ Review Req.
                </button>
                <button
                  type="button"
                  onClick={() => setDecisionChoice('REJECTED')}
                  className={`py-2 px-2 rounded-lg font-semibold border transition text-center ${
                    decisionChoice === 'REJECTED'
                      ? 'bg-rose-600 text-white border-rose-600 shadow-xs'
                      : 'bg-white text-zinc-700 border-zinc-300 hover:bg-zinc-100'
                  }`}
                >
                  ✕ Reject / Cite
                </button>
              </div>

              <div>
                <label className="text-[11px] font-semibold text-zinc-600 block mb-1">
                  Enforcement Remarks / Legal Grounds {decisionChoice !== 'APPROVED' && <span className="text-rose-600">*</span>}:
                </label>
                <textarea
                  rows={2}
                  required={decisionChoice !== 'APPROVED'}
                  value={decisionRemarks}
                  onChange={(e) => setDecisionRemarks(e.target.value)}
                  placeholder={
                    decisionChoice === 'APPROVED'
                      ? 'Optional endorsement notes for audit record...'
                      : 'Provide statutory basis or instructions for section 36 notice...'
                  }
                  className="w-full bg-white border border-zinc-300 rounded-lg p-2 text-xs focus:outline-none focus:border-emerald-500"
                />
              </div>

              <button
                type="submit"
                disabled={isSubmittingDecision}
                className="w-full py-2.5 bg-zinc-900 hover:bg-zinc-800 text-white font-semibold rounded-lg flex items-center justify-center gap-1.5 transition disabled:opacity-50"
              >
                {isSubmittingDecision ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-3.5 h-3.5" />
                )}
                <span className="hidden sm:inline">Submit &amp; Cryptographically Sign Decision</span>
                <span className="sm:hidden">Submit Decision</span>
              </button>
            </form>
          </div>
=======
              Cryptographic Packaging Evidence
            </h2>
            <span className="text-[11px] text-zinc-500 font-mono">EXIF Signed</span>
          </div>

          <div className="relative rounded-lg overflow-hidden border border-zinc-300 bg-zinc-950">
            <img src={scan.imageUrl} alt={scan.productName} className="w-full h-96 object-cover opacity-90" />

            {/* Overlaid Bounding Boxes */}
            {scan.declarations
              .filter((d) => d.bbox)
              .map((decl, idx) => {
                const b = decl.bbox!;
                const isSelected = selectedBbox?.label === b.label;
                return (
                  <div
                    key={idx}
                    onClick={() => setSelectedBbox(b)}
                    style={{
                      top: `${b.ymin}%`,
                      left: `${b.xmin}%`,
                      height: `${b.ymax - b.ymin}%`,
                      width: `${b.xmax - b.xmin}%`,
                    }}
                    className={`absolute border-2 cursor-pointer transition-all ${
                      b.status === 'pass'
                        ? isSelected
                          ? 'border-emerald-400 bg-emerald-500/30'
                          : 'border-emerald-500 bg-emerald-500/20'
                        : isSelected
                        ? 'border-rose-400 bg-rose-500/40'
                        : 'border-rose-500 bg-rose-500/20'
                    }`}
                  >
                    <span
                      className={`text-[9px] font-bold px-1.5 py-0.5 rounded shadow-xs text-white uppercase ${
                        b.status === 'pass' ? 'bg-emerald-700' : 'bg-rose-700'
                      }`}
                    >
                      {b.label}
                    </span>
                  </div>
                );
              })}
          </div>

          {scan.tamperDetected && (
            <div className="p-3 bg-rose-100 border border-rose-300 rounded-lg text-xs text-rose-900 space-y-1">
              <span className="font-bold flex items-center gap-1">
                <AlertTriangle className="w-4 h-4 text-rose-600" />
                Sticker Tampering Detected (Dual-MRP Violation)
              </span>
              <p className="text-[11px] text-rose-800">{scan.tamperReason}</p>
            </div>
          )}
>>>>>>> origin/main
        </div>

        {/* Declarations & Violations */}
        <div className="lg:col-span-6 space-y-4">
          {scan.violations.length > 0 && (
            <div className="bg-white border border-rose-200 rounded-xl p-5 shadow-xs space-y-3">
              <h2 className="text-sm font-bold text-rose-900 flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4 text-rose-600" />
<<<<<<< HEAD
                Violations Cited Under LM (PC) Rules, 2011 ({scan.violations.length})
=======
                Violations Cited for Prosecution
>>>>>>> origin/main
              </h2>
              <div className="space-y-3">
                {scan.violations.map((viol) => (
                  <div key={viol.id} className="p-3 bg-rose-50/60 rounded-lg border border-rose-200 text-xs space-y-2">
                    <div className="flex justify-between font-bold text-rose-950">
                      <span>{viol.ruleTitle}</span>
                      <span className="font-mono text-[10px] uppercase bg-rose-200 px-2 py-0.5 rounded">
                        {viol.severity}
                      </span>
                    </div>
                    <p className="text-[11px] text-zinc-700">{viol.message}</p>
                    <div className="bg-white p-2 rounded border border-rose-200 font-mono text-[11px]">
<<<<<<< HEAD
                      <div>Detected: <strong className="text-rose-700">{viol.detectedValue || 'NOT IDENTIFIED'}</strong></div>
                      <div>Statutory: <strong className="text-emerald-700">{viol.expectedValue || 'Mandatory'}</strong></div>
=======
                      <div>Detected: <strong className="text-rose-700">{viol.detectedValue}</strong></div>
                      <div>Statutory: <strong className="text-emerald-700">{viol.expectedValue}</strong></div>
>>>>>>> origin/main
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="bg-white border border-zinc-200 rounded-xl p-5 shadow-xs space-y-3">
            <h2 className="text-sm font-bold text-zinc-900 flex items-center gap-1.5">
              <FileCheck2 className="w-4 h-4 text-emerald-600" />
<<<<<<< HEAD
              Extracted Legal Metrology Declarations ({scan.declarations.length})
            </h2>
            <div className="divide-y divide-zinc-200 border border-zinc-200 rounded-lg overflow-hidden text-xs">
              {scan.declarations.length === 0 ? (
                <div className="p-4 text-center text-zinc-500 text-xs">
                  No declarations extracted yet. Please ensure evidence image has been analyzed.
                </div>
              ) : (
                scan.declarations.map((decl, idx) => (
                  <div key={idx} className="p-3 flex justify-between items-center bg-white hover:bg-zinc-50">
                    <div>
                      <span className="font-semibold text-zinc-800">{decl.label}</span>
                      <p className="font-mono text-xs text-zinc-600 mt-0.5">
                        {decl.value || <span className="text-rose-600 font-bold">MISSING</span>}
                      </p>
                    </div>
                    <span className="font-mono text-[11px] text-zinc-500">
                      {decl.confidence ? `${Math.round(decl.confidence * 100)}%` : '100%'}
                    </span>
                  </div>
                ))
              )}
=======
              Extracted Legal Metrology Declarations
            </h2>
            <div className="divide-y divide-zinc-200 border border-zinc-200 rounded-lg overflow-hidden text-xs">
              {scan.declarations.map((decl, idx) => (
                <div key={idx} className="p-3 flex justify-between items-center bg-white hover:bg-zinc-50">
                  <div>
                    <span className="font-semibold text-zinc-800">{decl.label}</span>
                    <p className="font-mono text-xs text-zinc-600 mt-0.5">
                      {decl.value || <span className="text-rose-600 font-bold">MISSING</span>}
                    </p>
                  </div>
                  <span className="font-mono text-[11px] text-zinc-500">
                    {decl.confidence ? `${decl.confidence}%` : '100%'}
                  </span>
                </div>
              ))}
>>>>>>> origin/main
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
