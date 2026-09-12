import {
  BackendEscalation,
  BackendImage,
  BackendInspection,
  BackendNotification,
  BackendProduct,
  BackendRule,
  BackendUser,
  BulkScanResult,
  CodifiedRule,
  ComplianceCertificate,
  DeclarationField,
  InspectionRecord,
  RepeatOffender,
  Section36Notice,
  SeverityLevel,
  ViolationItem,
} from './types';
import {
  SAMPLE_INSPECTIONS,
  SAMPLE_RULES,
  SAMPLE_NOTICES,
  SAMPLE_REPEAT_OFFENDERS,
  SAMPLE_CERTIFICATE,
} from './sample-data';

export const getApiBase = (): string => {
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }
  if (typeof window !== 'undefined' && window.location?.hostname) {
    const protocol = window.location.protocol || 'http:';
    const host = window.location.hostname;
    return `${protocol}//${host}:8000/api/v1`;
  }
  return 'http://localhost:8000/api/v1';
};

const TOKEN_STORAGE_KEY = 'labelguard_access_token';

export function getStoredToken(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setStoredToken(token: string | null): void {
  if (typeof window === 'undefined') return;
  try {
    if (token) {
      localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  } catch {}
}

export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const apiBase = getApiBase();
  const url = endpoint.startsWith('http') ? endpoint : `${apiBase}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;

  const headers = new Headers(options.headers || {});

  const token = getStoredToken();
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  if (!(options.body instanceof FormData) && !headers.has('Content-Type') && options.body) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    setStoredToken(null);
    if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
      window.location.href = '/login';
    }
    throw new Error('Unauthorized or session expired. Please log in again.');
  }

  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) {
        if (typeof errJson.detail === 'string') {
          errorDetail = errJson.detail;
        } else if (Array.isArray(errJson.detail)) {
          errorDetail = errJson.detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join(', ');
        } else {
          errorDetail = JSON.stringify(errJson.detail);
        }
      }
    } catch {
      // response is not JSON
    }
    throw new Error(errorDetail);
  }

  // Handle blob or empty response
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return response.json() as Promise<T>;
  }

  return response as unknown as T;
}

// Transform backend inspection to frontend InspectionRecord
export function mapBackendInspectionToRecord(item: BackendInspection): InspectionRecord {
  const complianceStatusMap: Record<string, 'COMPLIANT' | 'NON_COMPLIANT' | 'REVIEW' | 'PENDING'> = {
    compliant: 'COMPLIANT',
    non_compliant: 'NON_COMPLIANT',
    review: 'REVIEW',
    pending: 'PENDING',
  };

  const status = complianceStatusMap[item.compliance_status?.toLowerCase()] || 'PENDING';

  // Declarations mapping
  const declarations: DeclarationField[] = (item.declarations || []).map((d) => ({
    fieldName: d.field_name,
    label: formatFieldLabel(d.field_name),
    value: d.extracted_value || null,
    rawValue: d.normalized_value || d.extracted_value || null,
    confidence: d.confidence ?? 0.95,
    status: d.is_present ? 'extracted' : 'not_found',
    ruleCode: mapFieldToRuleCode(d.field_name),
  }));

  // Violations mapping
  const violations: ViolationItem[] = (item.violations || []).map((v) => ({
    id: String(v.id),
    ruleCode: `LG-${v.field_name.toUpperCase().replace(/_/g, '-')}`,
    ruleTitle: `Rule 6 Violation — ${formatFieldLabel(v.field_name)}`,
    legalCitation: 'Rule 6(1), Legal Metrology (Packaged Commodities) Rules, 2011',
    fieldName: v.field_name,
    severity: (v.severity as SeverityLevel) || 'major',
    status: (v.status as 'open' | 'review' | 'resolved') || 'open',
    message: v.message,
    detectedValue: v.detected_value || null,
    expectedValue: v.expected_value || null,
    confidence: v.confidence ?? 0.9,
    fixSuggestion: `Provide clear, legible ${formatFieldLabel(v.field_name)} declaration in the prescribed format.`,
  }));

  // Compliance score calculation
  const totalChecks = Math.max(1, (declarations.length || 8));
  const violationsCount = violations.length;
  const complianceScore = status === 'COMPLIANT' ? 100 : Math.max(0, Math.round(100 - (violationsCount / totalChecks) * 100));

  // Determine image URL
  let imageUrl = '/placeholder-package.png';
  if (item.images && item.images.length > 0) {
    const firstImg = item.images[0];
    imageUrl = `${getApiBase()}/inspections/${item.id}/images/${firstImg.id}/file`;
  }

  // Extract location/GPS if present
  const gpsCoords = item.latitude && item.longitude ? { lat: item.latitude, lng: item.longitude } : undefined;

  return {
    id: item.id,
    productName: item.product?.product_name || `Package #${item.reference_number}`,
    brand: item.product?.brand_name || 'Standard Commodity',
    sku: item.product?.category || item.reference_number,
    category: item.product?.category || 'Packaged Commodity',
    barcode: undefined,
    declaredMrp: getDeclaredMrpValue(declarations),
    netQuantity: getDeclarationValue(declarations, 'net_quantity') || 'Declared',
    mfgMonthYear: getDeclarationValue(declarations, 'manufacturing_date') || getDeclarationValue(declarations, 'packing_date') || 'Declared',
    storeName: item.location_source || 'Inspection Point',
    location: item.location_source || 'Field Scan',
    gpsCoords,
    status,
    complianceScore,
    createdAt: item.created_at,
    imageUrl,
    declarations,
    violations,
    tamperDetected: false,
    tamperReason: undefined,
    noticeStatus: violations.length > 0 ? 'draft' : 'none',
    noticeId: violations.length > 0 ? `SEC36-${item.reference_number}` : undefined,
    scanSource: 'field_inspector',
  };
}

function formatFieldLabel(name: string): string {
  return name
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function mapFieldToRuleCode(field: string): string {
  const map: Record<string, string> = {
    mrp: 'LG-MRP',
    net_quantity: 'LG-QTY',
    manufacturer: 'LG-MFR',
    consumer_care: 'LG-CARE',
    manufacturing_date: 'LG-DATE',
    packing_date: 'LG-DATE',
    expiry_date: 'LG-BBE',
    best_before: 'LG-BBE',
    country_of_origin: 'LG-COO',
    batch_number: 'LG-BATCH',
    unit_sale_price: 'LG-USP',
    unit_symbol: 'LG-UNIT-SYMBOL',
  };
  return map[field.toLowerCase()] || 'LG-GEN';
}

function getDeclarationValue(declarations: DeclarationField[], fieldName: string): string | null {
  const found = declarations.find((d) => d.fieldName.toLowerCase() === fieldName.toLowerCase());
  return found?.value || null;
}

function getDeclaredMrpValue(declarations: DeclarationField[]): number {
  const val = getDeclarationValue(declarations, 'mrp');
  if (!val) return 0;
  const num = parseFloat(val.replace(/[^0-9.]/g, ''));
  return isNaN(num) ? 0 : num;
}

export class ApiClient {
  static async checkBackend(): Promise<boolean> {
    try {
      const apiBase = getApiBase();
      const res = await fetch(`${apiBase}/health`, { method: 'GET', signal: AbortSignal.timeout(2000) });
      return res.ok;
    } catch {
      return false;
    }
  }

  // Auth
  static async login(email: string, password: string): Promise<{ access_token: string; token_type: string }> {
    const data = await apiFetch<{ access_token: string; token_type: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    setStoredToken(data.access_token);
    return data;
  }

  static async getCurrentUser(): Promise<BackendUser> {
    return apiFetch<BackendUser>('/auth/me');
  }

  static logout(): void {
    setStoredToken(null);
  }

  // Products
  static async getProducts(): Promise<BackendProduct[]> {
    return apiFetch<BackendProduct[]>('/products');
  }

  static async createProduct(data: Partial<BackendProduct>): Promise<BackendProduct> {
    return apiFetch<BackendProduct>('/products', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // Inspections
  static async createInspection(payload: {
    product_id?: number | null;
    latitude?: number | null;
    longitude?: number | null;
    location_accuracy_m?: number | null;
    location_captured_at?: string | null;
    location_source?: string | null;
  }): Promise<BackendInspection> {
    return apiFetch<BackendInspection>('/inspections', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  static async getInspections(): Promise<InspectionRecord[]> {
    try {
      const items = await apiFetch<BackendInspection[]>('/inspections');
      if (items && Array.isArray(items)) {
        return items.map(mapBackendInspectionToRecord);
      }
      return [];
    } catch (err) {
      console.error('Failed to fetch real inspections from backend:', err);
      throw err;
    }
  }

  static async getInspectionById(id: string | number): Promise<InspectionRecord> {
    const item = await apiFetch<BackendInspection>(`/inspections/${id}`);
    return mapBackendInspectionToRecord(item);
  }

  // Images
  static async uploadInspectionImage(
    inspectionId: number | string,
    file: File | Blob,
    imageType: string = 'front'
  ): Promise<BackendImage> {
    const formData = new FormData();
    formData.append('image_type', imageType);
    formData.append('file', file, file instanceof File ? file.name : `${imageType}.jpg`);

    return apiFetch<BackendImage>(`/inspections/${inspectionId}/images`, {
      method: 'POST',
      body: formData,
    });
  }

  static async getInspectionImages(inspectionId: number | string): Promise<BackendImage[]> {
    return apiFetch<BackendImage[]>(`/inspections/${inspectionId}/images`);
  }

  static getInspectionImageUrl(inspectionId: number | string, imageId: number | string): string {
    return `${getApiBase()}/inspections/${inspectionId}/images/${imageId}/file`;
  }

  // Analysis & Compliance
  static async analyzeInspection(inspectionId: number | string): Promise<BulkScanResult> {
    return apiFetch<BulkScanResult>(`/inspections/${inspectionId}/analyze`, {
      method: 'POST',
    });
  }

  static async evaluateInspection(inspectionId: number | string): Promise<Record<string, unknown>> {
    return apiFetch<Record<string, unknown>>(`/inspections/${inspectionId}/evaluate`, {
      method: 'POST',
    });
  }

  static async submitFinalDecision(
    inspectionId: number | string,
    decision: 'APPROVED' | 'REJECTED' | 'REVIEW_REQUIRED',
    remarks?: string
  ): Promise<Record<string, unknown>> {
    return apiFetch<Record<string, unknown>>(`/inspections/${inspectionId}/decision`, {
      method: 'POST',
      body: JSON.stringify({ decision, remarks }),
    });
  }

  // Escalations
  static async getEscalations(params?: {
    level?: string;
    status?: string;
    product_id?: number;
  }): Promise<BackendEscalation[]> {
    const query = new URLSearchParams();
    if (params?.level) query.set('level', params.level);
    if (params?.status) query.set('status', params.status);
    if (params?.product_id) query.set('product_id', String(params.product_id));

    const qs = query.toString();
    return apiFetch<BackendEscalation[]>(`/escalations${qs ? `?${qs}` : ''}`);
  }

  static async getEscalation(id: number | string): Promise<BackendEscalation> {
    return apiFetch<BackendEscalation>(`/escalations/${id}`);
  }

  static async performEscalationAction(
    id: number | string,
    action: 'acknowledge' | 'resolve' | 'refer_state' | 'refer_national',
    notes?: string
  ): Promise<Record<string, unknown>> {
    return apiFetch<Record<string, unknown>>(`/escalations/${id}/action`, {
      method: 'POST',
      body: JSON.stringify({ action, notes }),
    });
  }

  // Notifications
  static async getNotifications(params?: {
    escalation_id?: number;
    status?: string;
  }): Promise<BackendNotification[]> {
    const query = new URLSearchParams();
    if (params?.escalation_id) query.set('escalation_id', String(params.escalation_id));
    if (params?.status) query.set('status', params.status);

    const qs = query.toString();
    return apiFetch<BackendNotification[]>(`/notifications${qs ? `?${qs}` : ''}`);
  }

  // Rules
  static async getRules(): Promise<CodifiedRule[]> {
    try {
      const backendRules = await apiFetch<BackendRule[]>('/rules');
      if (backendRules && Array.isArray(backendRules)) {
        return backendRules.map((r) => ({
          id: r.id,
          ruleCode: r.rule_code,
          ruleNumber: r.rule_number,
          title: r.title,
          requirement: r.requirement,
          severity: (r.checks?.[0]?.severity as SeverityLevel) || 'major',
          version: r.version,
          effectiveFrom: r.effective_from,
          status: (r.status === 'draft' || r.status === 'superseded' ? r.status : 'active') as 'active' | 'draft' | 'superseded',
          jurisdiction: 'India (LM Act 2009)',
          checksCount: r.checks_count || (r.checks?.length ?? 1),
        }));
      }
    } catch {
      // fallback
    }
    return SAMPLE_RULES;
  }

  // Reports
  static async downloadReport(inspectionId: number | string, format: 'pdf' | 'docx' = 'pdf'): Promise<void> {
    const apiBase = getApiBase();
    const token = getStoredToken();
    const url = `${apiBase}/reports/${inspectionId}/${format}`;

    const res = await fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });

    if (!res.ok) {
      throw new Error(`Failed to download ${format.toUpperCase()} report (HTTP ${res.status})`);
    }

    const blob = await res.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = `Inspection_${inspectionId}_Report.${format}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(downloadUrl);
  }

  // Legacy / Sample helpers
  static getNotices(): Section36Notice[] {
    return SAMPLE_NOTICES;
  }

  static getRepeatOffenders(): RepeatOffender[] {
    return SAMPLE_REPEAT_OFFENDERS;
  }

  static getCertificate(): ComplianceCertificate {
    return SAMPLE_CERTIFICATE;
  }

  static updateNoticeStatus(noticeId: string, status: 'approved' | 'issued' | 'rejected'): boolean {
    const notice = SAMPLE_NOTICES.find((n) => n.id === noticeId);
    if (notice) {
      notice.status = status;
      return true;
    }
    return false;
  }

  static getSampleInspections(): InspectionRecord[] {
    return SAMPLE_INSPECTIONS;
  }

  static simulateAudit(payload: {
    productName: string;
    brand: string;
    sku: string;
    declaredMrp: number;
    category: string;
    file?: File | null;
  }): Promise<InspectionRecord> {
    return new Promise((resolve) => {
      setTimeout(() => {
        if (payload.productName.toLowerCase().includes('biscuit') || payload.productName.toLowerCase().includes('digestive')) {
          resolve({
            ...SAMPLE_INSPECTIONS[0],
            productName: payload.productName,
            brand: payload.brand,
            sku: payload.sku || 'SKU-NEW-01',
            declaredMrp: payload.declaredMrp || 145,
          });
        } else if (payload.productName.toLowerCase().includes('chip') || payload.productName.toLowerCase().includes('tamper')) {
          resolve({
            ...SAMPLE_INSPECTIONS[2],
            productName: payload.productName,
            brand: payload.brand,
            sku: payload.sku || 'SKU-NEW-02',
            declaredMrp: payload.declaredMrp || 50,
          });
        } else {
          resolve({
            ...SAMPLE_INSPECTIONS[1],
            productName: payload.productName,
            brand: payload.brand,
            sku: payload.sku || 'SKU-NEW-03',
            declaredMrp: payload.declaredMrp || 180,
          });
        }
      }, 1000);
    });
  }
}

