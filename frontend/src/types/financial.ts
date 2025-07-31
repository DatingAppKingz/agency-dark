export interface Transaction {
  id: string;
  type: 'credit' | 'debit' | 'payout' | 'commission';
  amount: number;
  currency: string;
  description: string;
  status: 'pending' | 'completed' | 'failed' | 'cancelled';
  created_at: string;
  updated_at: string;
  user_id: string;
  agency_id?: string;
  model_id?: string;
  reference_id?: string;
  metadata?: Record<string, any>;
}

export interface Payout {
  id: string;
  amount: number;
  currency: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  method: 'bank_transfer' | 'paypal' | 'crypto' | 'other';
  requested_at: string;
  processed_at?: string;
  user_id: string;
  model_id?: string;
  agency_id?: string;
  transactions: Transaction[];
  bank_details?: BankDetails;
  failure_reason?: string;
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
  id: string;
  type: 'bank_account' | 'paypal' | 'crypto_wallet';
  is_default: boolean;
  details: BankDetails | PayPalDetails | CryptoWalletDetails;
  created_at: string;
  updated_at: string;
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
