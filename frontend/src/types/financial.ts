export enum TransactionType {
  TIP = 'tip',
  PPV = 'ppv',
  SUBSCRIPTION = 'subscription',
  MESSAGE = 'message',
  REFERRAL = 'referral',
  ADJUSTMENT = 'adjustment',
  CHARGEBACK = 'chargeback',
  REFUND = 'refund',
}

export enum TransactionStatus {
  PENDING = 'pending',
  COMPLETED = 'completed',
  FAILED = 'failed',
  REFUNDED = 'refunded',
  DISPUTED = 'disputed',
}

export enum PayoutStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

export enum PaymentMethodType {
  BANK_TRANSFER = 'bank_transfer',
  PAYPAL = 'paypal',
  CRYPTO = 'crypto',
  CHECK = 'check',
  WIRE = 'wire',
}

export interface Transaction {
  id: number;
  agency_id: number;
  model_id: number;
  type: TransactionType;
  status: TransactionStatus;
  platform_transaction_id?: string;
  conversation_id?: number;
  message_id?: number;
  gross_amount: number;
  platform_fee: number;
  agency_commission: number;
  net_amount: number;
  currency: string;
  fan_id: string;
  fan_username: string;
  transaction_date: string;
  processed_at?: string;
  description?: string;
  metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface Earning {
  id: number;
  model_id: number;
  transaction_id: number;
  period_year: number;
  period_month: number;
  period_week: number;
  gross_amount: number;
  commission_amount: number;
  net_amount: number;
  is_paid: boolean;
  payout_id?: number;
  paid_date?: string;
  created_at: string;
  updated_at: string;
}

export interface Payout {
  id: number;
  agency_id: number;
  model_id: number;
  payout_number: string;
  status: PayoutStatus;
  period_start: string;
  period_end: string;
  gross_earnings: number;
  commission_amount: number;
  adjustments: number;
  net_amount: number;
  currency: string;
  payment_method: PaymentMethodType;
  payment_details: Record<string, any>;
  scheduled_date: string;
  processed_date?: string;
  completed_date?: string;
  transaction_reference?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface BankDetails {
  account_holder: string;
  account_number: string;
  routing_number?: string;
  bank_name: string;
  swift_code?: string;
  iban?: string;
}

export interface PaymentMethod {
  id: number;
  model_id?: number;
  agency_id?: number;
  method_type: PaymentMethodType;
  is_primary: boolean;
  is_active: boolean;
  nickname?: string;
  
  // Bank transfer
  bank_name?: string;
  account_holder_name?: string;
  account_number?: string; // Masked in responses
  routing_number?: string; // Masked in responses
  swift_code?: string;
  iban?: string; // Masked in responses
  
  // PayPal
  paypal_email?: string;
  
  // Crypto
  crypto_currency?: string;
  crypto_address?: string; // Partially masked in responses
  crypto_network?: string;
  
  // Wire
  wire_instructions?: Record<string, any>;
  
  // Verification
  is_verified: boolean;
  verified_at?: string;
  verification_notes?: string;
  
  // Settings
  minimum_payout: number;
  processing_days: number;
  
  // Metadata
  last_used_at?: string;
  usage_count: number;
  created_at: string;
  updated_at: string;
  
  // Computed property for display
  display_name?: string;
}

export interface PayPalDetails {
  email: string;
}

export interface CryptoWalletDetails {
  currency: string;
  address: string;
  network?: string;
}

export interface Revenue {
  period: 'daily' | 'weekly' | 'monthly' | 'yearly';
  start_date: string;
  end_date: string;
  gross_revenue: number;
  net_revenue: number;
  commission: number;
  currency: string;
  breakdown: RevenueBreakdown[];
}

export interface RevenueBreakdown {
  source: 'subscriptions' | 'tips' | 'messages' | 'content_sales' | 'other';
  amount: number;
  count: number;
  percentage: number;
}

export interface Commission {
  rate: number;
  tiers?: CommissionTier[];
  model_id?: string;
  agency_id?: string;
  effective_date: string;
}

export interface CommissionTier {
  min_revenue: number;
  max_revenue?: number;
  rate: number;
}

export interface Invoice {
  id: string;
  invoice_number: string;
  date: string;
  due_date: string;
  status: 'draft' | 'sent' | 'paid' | 'overdue' | 'cancelled';
  total: number;
  subtotal: number;
  tax: number;
  currency: string;
  items: InvoiceItem[];
  from: InvoiceParty;
  to: InvoiceParty;
  payment_terms?: string;
  notes?: string;
}

export interface InvoiceItem {
  description: string;
  quantity: number;
  unit_price: number;
  total: number;
}

export interface InvoiceParty {
  name: string;
  address?: string;
  email?: string;
  phone?: string;
  tax_id?: string;
}

export interface FinancialReportData {
  earnings?: Record<string, number>;
  deductions?: Record<string, number>;
  taxes?: Record<string, number>;
  commissions?: Record<string, number>;
  summary?: Record<string, string | number>;
}

export interface FinancialReport {
  id: string;
  type: 'earnings_statement' | 'tax_document' | 'commission_report';
  period_start: string;
  period_end: string;
  generated_at: string;
  file_url?: string;
  data: FinancialReportData;
}

export interface FinancialSummary {
  total_revenue: number;
  total_payouts: number;
  pending_payouts: number;
  available_balance: number;
  currency: string;
  last_payout?: Payout;
  next_payout_date?: string;
}
