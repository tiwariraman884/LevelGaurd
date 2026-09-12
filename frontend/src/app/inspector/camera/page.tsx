'use client';

import React, { useState, useRef, useEffect, useCallback, Suspense } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  Camera,
  X,
  Zap,
  ZapOff,
  RotateCcw,
  ScanLine,
  Upload,
  CheckCircle,
  AlertCircle,
  Crosshair,
  Loader2,
  ImageIcon,
} from 'lucide-react';
import { ApiClient } from '@/lib/api-client';

type CameraState = 'requesting' | 'active' | 'denied' | 'captured' | 'uploading' | 'error';

function InspectorCameraContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialInspectionId = searchParams.get('inspectionId');

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [cameraState, setCameraState] = useState<CameraState>('requesting');
  const [capturedImage, setCapturedImage] = useState<string | null>(null);
  const [capturedBlob, setCapturedBlob] = useState<Blob | null>(null);
  const [torchOn, setTorchOn] = useState(false);
  const [torchSupported, setTorchSupported] = useState(false);
  const [facingMode, setFacingMode] = useState<'environment' | 'user'>('environment');
  const [errorMessage, setErrorMessage] = useState('');
  const [processingStep, setProcessingStep] = useState<string>('Initializing Inspection Record...');

  const startCamera = useCallback(async () => {
    setCameraState('requesting');
    setCapturedImage(null);
    setCapturedBlob(null);

    // Stop any existing stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: facingMode,
          width: { ideal: 1920 },
          height: { ideal: 1080 },
          aspectRatio: { ideal: 4 / 3 },
        },
        audio: false,
      });

      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        try {
          await videoRef.current.play();
        } catch (playErr: unknown) {
          if (playErr instanceof DOMException && playErr.name === 'AbortError') {
            // Ignored: User agent or component state interrupted media playback request
          } else {
            console.warn('Video play warning:', playErr);
          }
        }
      }

      // Check if torch/flashlight is supported
      const track = stream.getVideoTracks()[0];
      if (track) {
        const capabilities = track.getCapabilities?.() as MediaTrackCapabilities & { torch?: boolean };
        if (capabilities && capabilities.torch) {
          setTorchSupported(true);
        } else {
          setTorchSupported(false);
        }
      }

      setCameraState('active');
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        return;
      }
      console.error('Camera access error:', err);
      if (err instanceof DOMException) {
        if (err.name === 'NotAllowedError') {
          setCameraState('denied');
          setErrorMessage('Camera access was denied. Please grant camera permission in your browser settings and reload.');
        } else if (err.name === 'NotFoundError') {
          setCameraState('error');
          setErrorMessage('No camera found on this device.');
        } else if (err.name === 'NotReadableError') {
          setCameraState('error');
          setErrorMessage('Camera is already in use by another application.');
        } else {
          setCameraState('error');
          setErrorMessage(`Camera error: ${err.message}`);
        }
      } else {
        setCameraState('error');
        setErrorMessage('An unexpected error occurred while accessing the camera.');
      }
    }
  }, [facingMode]);

  useEffect(() => {
    startCamera();

    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, [startCamera]);

  const toggleTorch = async () => {
    if (!streamRef.current) return;
    const track = streamRef.current.getVideoTracks()[0];
    try {
      await track.applyConstraints({
        advanced: [{ torch: !torchOn } as MediaTrackConstraintSet & { torch: boolean }],
      });
      setTorchOn(!torchOn);
    } catch (err) {
      console.error('Torch toggle failed:', err);
    }
  };

  const switchCamera = () => {
    setFacingMode((prev) => (prev === 'environment' ? 'user' : 'environment'));
  };

  const capturePhoto = () => {
    if (!videoRef.current || !canvasRef.current) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL('image/jpeg', 0.92);
    setCapturedImage(dataUrl);

    canvas.toBlob(
      (blob) => {
        if (blob) setCapturedBlob(blob);
      },
      'image/jpeg',
      0.92
    );

    setCameraState('captured');

    // Stop camera stream after capture
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
  };

  const retake = () => {
    setCapturedImage(null);
    setCapturedBlob(null);
    startCamera();
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setCapturedBlob(file);
      const reader = new FileReader();
      reader.onload = (event) => {
        if (event.target?.result) {
          setCapturedImage(event.target.result as string);
          setCameraState('captured');
        }
      };
      reader.readAsDataURL(file);
    }
  };

  /** Real Backend Processing & Analysis Pipeline */
  const handleUpload = async () => {
    setCameraState('uploading');
    setErrorMessage('');

    try {
      let targetId = initialInspectionId;

      setProcessingStep('1/3 Connecting to Backend Pipeline...');
      const isBackendAlive = await ApiClient.checkBackend();

      if (isBackendAlive) {
        // Step 1: Ensure we have an active inspection record
        if (!targetId) {
          const newInspection = await ApiClient.createInspection({
            location_source: 'Field Inspector Mobile Camera',
          });
          targetId = String(newInspection.id);
        }

        // Step 2: Upload high-res evidence photo to /api/v1/inspections/{id}/images
        setProcessingStep('1/3 Uploading High-Res Evidence Photo...');
        let uploadBlob: Blob;
        if (capturedBlob) {
          uploadBlob = capturedBlob;
        } else if (capturedImage) {
          const res = await fetch(capturedImage);
          uploadBlob = await res.blob();
        } else {
          throw new Error('No image captured to process.');
        }

        await ApiClient.uploadImage(targetId, uploadBlob);

        // Step 3: Run OCR & Layout Analysis via /api/v1/inspections/{id}/analyze
        setProcessingStep('2/3 Running Multilingual OCR & Layout Analysis...');
        await ApiClient.analyzeInspection(targetId);

        // Step 4: Evaluate Legal Metrology Rules via /api/v1/inspections/{id}/evaluate
        setProcessingStep('3/3 Evaluating Legal Metrology Compliance Rules...');
        await ApiClient.evaluateInspection(targetId);

        // Transition seamlessly to official inspection verdict page
        router.push(`/scan/${targetId}`);
      } else {
        // Demo / Fallback pipeline simulation
        setProcessingStep('1/3 Simulating Evidence Upload...');
        await new Promise((r) => setTimeout(r, 600));

        setProcessingStep('2/3 Simulating OCR & Layout Analysis...');
        await new Promise((r) => setTimeout(r, 600));

        setProcessingStep('3/3 Evaluating Legal Metrology Compliance Rules...');
        await new Promise((r) => setTimeout(r, 600));

        const fallbackId = targetId || 'INSP-2026-001';
        router.push(`/scan/${fallbackId}`);
      }
    } catch (err: unknown) {
      console.error('Inspection process failed:', err);
      setCameraState('error');
      const msg = err instanceof Error ? err.message : 'Failed to process inspection photo.';
      setErrorMessage(msg);
    }
  };

  return (
    <div className="fixed inset-0 bg-black flex flex-col z-50">
      {/* Hidden canvas for capture */}
      <canvas ref={canvasRef} className="hidden" />

      {/* Top Bar */}
      <div className="relative z-10 flex items-center justify-between px-4 py-3 bg-gradient-to-b from-black/80 to-transparent">
        <Link
          href="/inspector/scans"
          className="w-10 h-10 rounded-full bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center text-white transition-all active:scale-90 hover:bg-white/20"
        >
          <X className="w-5 h-5" />
        </Link>

        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-white text-xs font-bold tracking-widest uppercase">
            Inspector Scanner
          </span>
        </div>

        <div className="flex items-center gap-2">
          {torchSupported && cameraState === 'active' && (
            <button
              onClick={toggleTorch}
              className={`w-10 h-10 rounded-full flex items-center justify-center transition-all active:scale-90 ${
                torchOn
                  ? 'bg-amber-400 text-black shadow-[0_0_20px_rgba(251,191,36,0.5)]'
                  : 'bg-white/10 backdrop-blur-md border border-white/20 text-white hover:bg-white/20'
              }`}
            >
              {torchOn ? <Zap className="w-5 h-5" /> : <ZapOff className="w-5 h-5" />}
            </button>
          )}
        </div>
      </div>

      {/* Camera View / States */}
      <div className="flex-1 relative overflow-hidden">
        {/* Requesting Permission */}
        {cameraState === 'requesting' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-white space-y-4 bg-zinc-950">
            <div className="w-20 h-20 rounded-full bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-[0_0_40px_rgba(16,185,129,0.3)] animate-pulse">
              <Camera className="w-10 h-10" />
            </div>
            <div className="text-center space-y-2 px-8">
              <p className="text-lg font-bold">Camera Access Required</p>
              <p className="text-sm text-zinc-400 leading-relaxed">
                Please allow camera access to scan product packaging for compliance inspection.
              </p>
            </div>
            <div className="flex items-center gap-2 mt-2">
              <Loader2 className="w-4 h-4 text-emerald-400 animate-spin" />
              <span className="text-xs text-zinc-500">Waiting for permission...</span>
            </div>
          </div>
        )}

        {/* Permission Denied or Insecure HTTP Origin */}
        {(cameraState === 'denied' || cameraState === 'error') && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-white space-y-4 bg-zinc-950 px-6 text-center">
            <div className="w-16 h-16 rounded-full bg-rose-500/20 border border-rose-500/30 flex items-center justify-center text-rose-400">
              <AlertCircle className="w-8 h-8" />
            </div>

            <div className="space-y-2 max-w-sm">
              <p className="text-lg font-bold text-white">Camera Unavailable</p>
              <p className="text-xs text-zinc-400 leading-relaxed">{errorMessage}</p>
            </div>

            {/* Insecure HTTP / IP Address Warning Note */}
            <div className="mt-2 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 text-[11px] max-w-sm text-left space-y-1">
              <p className="font-bold flex items-center gap-1">
                <span>💡 Note on Mobile/LAN Testing:</span>
              </p>
              <p className="text-zinc-400 leading-normal">
                Browsers block live WebRTC camera access on HTTP IP addresses. Use <code className="text-white">localhost</code>, HTTPS, or upload an image directly below.
              </p>
            </div>

            {/* Native Mobile File Selection Fallback */}
            <div className="pt-4 flex flex-col items-center gap-3">
              <label className="px-6 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold tracking-wide flex items-center gap-2 shadow-lg cursor-pointer transition active:scale-95">
                <ImageIcon className="w-4 h-4" />
                <span>Upload Package Photo from Device</span>
                <input
                  type="file"
                  accept="image/*"
                  capture="environment"
                  className="hidden"
                  onChange={handleFileSelect}
                />
              </label>

              <button
                onClick={startCamera}
                className="mt-2 text-xs text-zinc-500 underline hover:text-zinc-300"
              >
                Try live video stream again
              </button>
            </div>
          </div>
        )}

        {/* Live Camera Feed */}
        {(cameraState === 'active' || cameraState === 'requesting') && (
          <>
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="absolute inset-0 w-full h-full object-cover"
            />

            {/* Scanner Overlay */}
            {cameraState === 'active' && (
              <div className="absolute inset-0 pointer-events-none">
                {/* Dark vignette edges */}
                <div className="absolute inset-0 bg-gradient-to-b from-black/40 via-transparent to-black/60" />

                {/* Scanner frame - centered */}
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="relative w-[75%] max-w-[320px] aspect-[3/4]">
                    {/* Corner brackets */}
                    <div className="absolute top-0 left-0 w-8 h-8 border-t-[3px] border-l-[3px] border-emerald-400 rounded-tl-lg" />
                    <div className="absolute top-0 right-0 w-8 h-8 border-t-[3px] border-r-[3px] border-emerald-400 rounded-tr-lg" />
                    <div className="absolute bottom-0 left-0 w-8 h-8 border-b-[3px] border-l-[3px] border-emerald-400 rounded-bl-lg" />
                    <div className="absolute bottom-0 right-0 w-8 h-8 border-b-[3px] border-r-[3px] border-emerald-400 rounded-br-lg" />

                    {/* Scanning line animation */}
                    <div className="absolute left-2 right-2 h-[2px] bg-gradient-to-r from-transparent via-emerald-400 to-transparent opacity-80 animate-[scan_2.5s_ease-in-out_infinite]" />

                    {/* Center crosshair */}
                    <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
                      <Crosshair className="w-6 h-6 text-white/40" />
                    </div>

                    {/* Instruction text */}
                    <div className="absolute -bottom-10 left-0 right-0 text-center">
                      <p className="text-white/80 text-xs font-medium tracking-wide bg-black/50 backdrop-blur-sm rounded-full px-4 py-1.5 inline-block">
                        Align product label within frame
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {/* Captured Image Preview */}
        {cameraState === 'captured' && capturedImage && (
          <div className="absolute inset-0 bg-black">
            <img
              src={capturedImage}
              alt="Captured packaging"
              className="w-full h-full object-contain"
            />
            {/* Success badge */}
            <div className="absolute top-4 left-1/2 -translate-x-1/2 flex items-center gap-2 bg-emerald-500/90 backdrop-blur-md text-white px-4 py-2 rounded-full shadow-lg">
              <CheckCircle className="w-4 h-4" />
              <span className="text-xs font-bold tracking-wide">Photo Captured — Ready for Inspection</span>
            </div>
          </div>
        )}

        {/* Uploading & Backend AI Pipeline Processing State */}
        {cameraState === 'uploading' && capturedImage && (
          <div className="absolute inset-0 bg-black">
            <img
              src={capturedImage}
              alt="Processing..."
              className="w-full h-full object-contain opacity-35 blur-[2px]"
            />
            <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center space-y-4">
              <div className="relative">
                <div className="w-20 h-20 rounded-full border-4 border-emerald-500/30 border-t-emerald-400 animate-spin" />
                <div className="absolute inset-0 flex items-center justify-center">
                  <ScanLine className="w-8 h-8 text-emerald-400 animate-pulse" />
                </div>
              </div>
              <div className="space-y-2 max-w-sm">
                <p className="text-white text-base font-extrabold tracking-tight">AI Compliance Pipeline Active</p>
                <p className="text-emerald-400 text-xs font-mono font-semibold bg-emerald-950/80 border border-emerald-800/80 px-3 py-1.5 rounded-full inline-block">
                  {processingStep}
                </p>
              </div>
              <p className="text-zinc-400 text-xs max-w-xs">
                Extracting Legal Metrology declarations, measuring font heights, and detecting statutory violations...
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Bottom Controls */}
      <div className="relative z-10 bg-gradient-to-t from-black/90 to-transparent pt-6 px-6 pb-safe" style={{ paddingBottom: 'max(2rem, env(safe-area-inset-bottom, 2rem))' }}>
        {cameraState === 'active' && (
          <div className="flex items-center justify-between">
            {/* Native Mobile Gallery / Camera Fallback */}
            <label className="w-12 h-12 rounded-xl bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center text-white hover:bg-white/20 transition-all active:scale-90 cursor-pointer" title="Upload from Device">
              <ImageIcon className="w-5 h-5" />
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleFileSelect}
              />
            </label>

            {/* Capture Button */}
            <button
              onClick={capturePhoto}
              className="w-[72px] h-[72px] rounded-full bg-white border-[4px] border-white/30 shadow-[0_0_30px_rgba(255,255,255,0.2)] flex items-center justify-center transition-all active:scale-90 hover:shadow-[0_0_40px_rgba(255,255,255,0.4)]"
            >
              <div className="w-[60px] h-[60px] rounded-full bg-white hover:bg-zinc-100 transition-colors flex items-center justify-center">
                <ScanLine className="w-6 h-6 text-zinc-800" />
              </div>
            </button>

            {/* Switch Camera */}
            <button
              onClick={switchCamera}
              className="w-12 h-12 rounded-xl bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center text-white hover:bg-white/20 transition-all active:scale-90"
            >
              <RotateCcw className="w-5 h-5" />
            </button>
          </div>
        )}

        {cameraState === 'captured' && (
          <div className="flex items-center gap-3">
            <button
              onClick={retake}
              className="flex-1 py-3.5 bg-white/10 backdrop-blur-md border border-white/20 text-white font-semibold rounded-xl text-sm flex items-center justify-center gap-2 hover:bg-white/20 transition-all active:scale-[0.98]"
            >
              <RotateCcw className="w-4 h-4" />
              Retake
            </button>
            <button
              onClick={handleUpload}
              className="flex-[2] py-3.5 bg-gradient-to-r from-emerald-500 to-teal-500 text-white font-bold rounded-xl text-sm flex items-center justify-center gap-2 shadow-[0_0_20px_rgba(16,185,129,0.3)] hover:shadow-[0_0_30px_rgba(16,185,129,0.5)] transition-all active:scale-[0.98]"
            >
              <Upload className="w-4 h-4" />
              Send to AI Analysis Pipeline
            </button>
          </div>
        )}

        {(cameraState === 'denied' || cameraState === 'error') && (
          <div className="text-center">
            <Link
              href="/inspector/scans"
              className="inline-flex items-center gap-2 text-zinc-400 hover:text-white text-sm font-medium transition-colors"
            >
              ← Back to Inspections
            </Link>
          </div>
        )}
      </div>

      {/* Custom scanning line animation */}
      <style jsx>{`
        @keyframes scan {
          0%, 100% {
            top: 8%;
          }
          50% {
            top: 88%;
          }
        }
      `}</style>
    </div>
  );
}

export default function InspectorCameraPage() {
  return (
    <Suspense fallback={
      <div className="fixed inset-0 bg-black flex items-center justify-center text-white">
        <Loader2 className="w-8 h-8 text-emerald-400 animate-spin" />
      </div>
    }>
      <InspectorCameraContent />
    </Suspense>
  );
}
