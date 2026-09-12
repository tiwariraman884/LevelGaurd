export type UserRole = 'vendor' | 'inspector' | 'controller' | 'admin' | 'auditor';

export interface UserProfile {
  id: number;
  email: string;
  fullName: string;
  role: UserRole;
  designation: string;
  department?: string;
  district?: string;
  state?: string;
  companyName?: string;
  gstNumber?: string;
  lutNumber?: string;
}

export type SeverityLevel = 'minor' | 'major' | 'critical';
export type ComplianceStatus = 'COMPLIANT' | 'NON_COMPLIANT' | 'REVIEW' | 'PENDING';

export interface BoundingBox {
  ymin: number; // 0-100 percentage
  xmin: number; // 0-100 percentage
  ymax: number;
  xmax: number;
  label: string;
  status: 'pass' | 'fail' | 'review';
  field_name: string;
}

export interface DeclarationField {
  fieldName: string;
  label: string;
  value: string | null;
  rawValue?: string | null;
  confidence: number;
  status: 'extracted' | 'review' | 'not_found';
  ruleCode: string;
  bbox?: BoundingBox;
}

export interface ViolationItem {
  id: string;
  ruleCode: string;
  ruleTitle: string;
  legalCitation: string;
  fieldName: string;
  severity: SeverityLevel;
  status: 'open' | 'review' | 'resolved';
  message: string;
  detectedValue: string | null;
  expectedValue: string | null;
  confidence?: number;
  fixSuggestion: string;
  bbox?: BoundingBox;
}

export interface InspectionRecord {
  id: number | string;
  productName: string;
  brand: string;
  sku: string;
  category: string;
  barcode?: string;
  declaredMrp: number;
  netQuantity: string;
  mfgMonthYear: string;
  storeName?: string;
  location?: string;
  gpsCoords?: { lat: number; lng: number };
  status: ComplianceStatus;
  complianceScore: number; // 0 to 100
  createdAt: string;
  imageUrl: string;
  declarations: DeclarationField[];
  violations: ViolationItem[];
  tamperDetected: boolean;
  tamperReason?: string;
  noticeStatus?: 'none' | 'draft' | 'approved' | 'issued';
  noticeId?: string;
  scanSource: 'vendor_self_audit' | 'field_inspector' | 'ecomm_listing';
}

export interface CodifiedRule {
  id: number;
  ruleCode: string;
  ruleNumber: string;
  title: string;
  requirement: string;
  severity: SeverityLevel;
  version: number;
  effectiveFrom: string;
  status: 'active' | 'draft' | 'superseded';
  jurisdiction: string;
  checksCount: number;
}

export interface Section36Notice {
  id: string;
  noticeNumber: string;
  inspectionId: number | string;
  productName: string;
  brand: string;
  companyName: string;
  companyAddress: string;
  gstNumber?: string;
  violations: {
    rule: string;
    section: string;
    description: string;
    severity: SeverityLevel;
  }[];
  draftedAt: string;
  status: 'draft' | 'approved' | 'issued' | 'rejected';
  issuingOfficer: string;
  designation: string;
  digitalSignatureHash: string;
  penaltyClause: string;
  responseDeadlineDays: number;
}

export interface ComplianceCertificate {
  certificateNumber: string;
  productName: string;
  brand: string;
  sku: string;
  manufacturer: string;
  gstin: string;
  complianceScore: number;
  evaluatedRules: string[];
  issuedAt: string;
  validUntil: string;
  qrVerificationCode: string;
  authority: string;
  status: 'VALID' | 'REVOKED';
}

export interface RepeatOffender {
  brand: string;
  companyName: string;
  totalScans: number;
  violationCount: number;
  criticalCount: number;
  riskScore: number; // 0 - 100
  topViolationRule: string;
  lastViolationDate: string;
  priorityQueueStatus: 'active' | 'assigned' | 'resolved';
}

// Backend API Entities
export interface BackendUser {
  id: number;
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
}

export interface BackendProduct {
  id: number;
  brand_name?: string | null;
  product_name?: string | null;
  category?: string | null;
  package_type?: string | null;
  manufacturer_name?: string | null;
  manufacturer_address?: string | null;
}

export interface BackendImage {
  id: number;
  inspection_id: number;
  file_name: string;
  file_path: string;
  image_type?: string | null;
  file_size?: number | null;
  mime_type?: string | null;
  created_at: string;
}

export interface BackendDeclaration {
  id: number;
  inspection_id: number;
  field_name: string;
  extracted_value?: string | null;
  normalized_value?: string | null;
  is_present: boolean;
  confidence?: number | null;
  created_at: string;
}

export interface BackendViolation {
  id: number;
  inspection_id: number;
  rule_version_id: number;
  field_name: string;
  severity: string;
  status: string;
  message: string;
  detected_value?: string | null;
  expected_value?: string | null;
  confidence?: number | null;
  evidence?: string | null;
  created_at: string;
  updated_at: string;
}

export interface BackendEscalation {
  id: number;
  product_id: number;
  trigger_inspection_id: number;
  failed_inspection_count: number;
  level: string;
  status: string;
  reason: string;
  created_at: string;
  updated_at: string;
  resolved_at?: string | null;
  acknowledged_by?: number | null;
  acknowledged_at?: string | null;
  resolved_by?: number | null;
  resolution_notes?: string | null;
  referred_by?: number | null;
  referred_at?: string | null;
}

export interface BackendNotification {
  id: number;
  escalation_id?: number | null;
  recipient_role: string;
  recipient_name?: string | null;
  recipient_email?: string | null;
  channel: string;
  subject: string;
  message: string;
  status: string;
  error_message?: string | null;
  created_at: string;
  sent_at?: string | null;
}

export interface BackendRuleCheck {
  id: number;
  field_name: string;
  operator: string;
  expected_value?: string | null;
  expected_unit?: string | null;
  severity: string;
  failure_message: string;
}

export interface BackendRule {
  id: number;
  rule_code: string;
  rule_number: string;
  version: number;
  title: string;
  requirement: string;
  effective_from: string;
  effective_to?: string | null;
  status: string;
  approval_status: string;
  created_at: string;
  updated_at: string;
  checks_count: number;
  checks?: BackendRuleCheck[];
}

export interface BackendInspection {
  id: number;
  inspector_id: number;
  product_id?: number | null;
  reference_number: string;
  status: string;
  compliance_status: string;
  created_at: string;
  completed_at?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  location_accuracy_m?: number | null;
  location_captured_at?: string | null;
  location_source?: string | null;
  scan_started_at?: string | null;
  scan_completed_at?: string | null;
  final_decision?: string | null;
  final_decision_by?: number | null;
  final_decision_at?: string | null;
  officer_remarks?: string | null;
  product?: BackendProduct | null;
  images?: BackendImage[];
  declarations?: BackendDeclaration[];
  violations?: BackendViolation[];
  mrp_findings?: Record<string, unknown>[];
  escalation?: BackendEscalation | null;
}

export interface BulkScanResult {
  inspection_id: number;
  reference_number: string;
  total_images: number;
  successfully_processed: number;
  failed_images: Array<string | Record<string, unknown>>;
  overall_status: string;
  compliance_status: string;
  processing_duration_seconds: number;
  images: Array<string | Record<string, unknown>>;
  declarations: Record<string, unknown>;
  compliance_results: Array<Record<string, unknown>>;
  violations: BackendViolation[];
  escalation?: BackendEscalation | null;
}


