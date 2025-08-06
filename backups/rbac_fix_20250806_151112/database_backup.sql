--
-- PostgreSQL database dump
--

-- Dumped from database version 16.9 (Homebrew)
-- Dumped by pg_dump version 16.9 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: commissiontier; Type: TYPE; Schema: public; Owner: mariuszbudzisz
--

CREATE TYPE public.commissiontier AS ENUM (
    'TIER_1',
    'TIER_2',
    'TIER_3',
    'CUSTOM'
);


ALTER TYPE public.commissiontier OWNER TO mariuszbudzisz;

--
-- Name: cryptonetwork; Type: TYPE; Schema: public; Owner: mariuszbudzisz
--

CREATE TYPE public.cryptonetwork AS ENUM (
    'BITCOIN',
    'ETHEREUM',
    'BINANCE_SMART_CHAIN',
    'POLYGON',
    'TRON',
    'USDT_TRC20',
    'USDT_ERC20',
    'USDC'
);


ALTER TYPE public.cryptonetwork OWNER TO mariuszbudzisz;

--
-- Name: invoicestatus; Type: TYPE; Schema: public; Owner: mariuszbudzisz
--

CREATE TYPE public.invoicestatus AS ENUM (
    'DRAFT',
    'SENT',
    'PAID',
    'OVERDUE',
    'CANCELLED'
);


ALTER TYPE public.invoicestatus OWNER TO mariuszbudzisz;

--
-- Name: notificationtype; Type: TYPE; Schema: public; Owner: agencydark
--

CREATE TYPE public.notificationtype AS ENUM (
    'INFO',
    'WARNING',
    'ERROR',
    'SUCCESS'
);


ALTER TYPE public.notificationtype OWNER TO agencydark;

--
-- Name: payoutstatus; Type: TYPE; Schema: public; Owner: mariuszbudzisz
--

CREATE TYPE public.payoutstatus AS ENUM (
    'PENDING',
    'PROCESSING',
    'COMPLETED',
    'FAILED',
    'CANCELLED'
);


ALTER TYPE public.payoutstatus OWNER TO mariuszbudzisz;

--
-- Name: subscriptionstatus; Type: TYPE; Schema: public; Owner: agencydark
--

CREATE TYPE public.subscriptionstatus AS ENUM (
    'ACTIVE',
    'TRIALING',
    'CANCELED',
    'PAST_DUE',
    'INCOMPLETE'
);


ALTER TYPE public.subscriptionstatus OWNER TO agencydark;

--
-- Name: transactiontype; Type: TYPE; Schema: public; Owner: mariuszbudzisz
--

CREATE TYPE public.transactiontype AS ENUM (
    'REVENUE',
    'COMMISSION',
    'PAYOUT',
    'REFUND',
    'ADJUSTMENT'
);


ALTER TYPE public.transactiontype OWNER TO mariuszbudzisz;

--
-- Name: userrole; Type: TYPE; Schema: public; Owner: agencydark
--

CREATE TYPE public.userrole AS ENUM (
    'SUPER_ADMIN',
    'AGENCY_OWNER',
    'AGENCY_ADMIN',
    'AGENCY_MEMBER',
    'MODEL',
    'CHATTER'
);


ALTER TYPE public.userrole OWNER TO agencydark;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: agencies; Type: TABLE; Schema: public; Owner: agencydark
--

CREATE TABLE public.agencies (
    id uuid NOT NULL,
    name character varying(255) NOT NULL,
    slug character varying(255) NOT NULL,
    domain character varying(255),
    settings json,
    subscription_status public.subscriptionstatus,
    subscription_ends_at timestamp without time zone,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


ALTER TABLE public.agencies OWNER TO agencydark;

--
-- Name: agency_profiles; Type: TABLE; Schema: public; Owner: mariuszbudzisz
--

CREATE TABLE public.agency_profiles (
    id uuid NOT NULL,
    agency_id uuid NOT NULL,
    display_name character varying(100),
    tagline character varying(200),
    description text,
    support_email character varying(255),
    support_phone character varying(50),
    website_url character varying(500),
    social_links json,
    legal_name character varying(200),
    tax_id character varying(50),
    address json,
    brand_guidelines text,
    custom_domain character varying(255),
    custom_domain_verified boolean,
    from_email_name character varying(100),
    from_email_address character varying(255),
    reply_to_email character varying(255),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.agency_profiles OWNER TO mariuszbudzisz;

--
-- Name: analytics_cache; Type: TABLE; Schema: public; Owner: mariuszbudzisz
--

CREATE TABLE public.analytics_cache (
    id uuid NOT NULL,
    cache_type character varying(50) NOT NULL,
    entity_type character varying(50) NOT NULL,
    entity_id uuid NOT NULL,
    period_start timestamp with time zone NOT NULL,
    period_end timestamp with time zone NOT NULL,
    filters json,
    data json NOT NULL,
    computed_at timestamp with time zone DEFAULT now(),
    expires_at timestamp with time zone NOT NULL
);


ALTER TABLE public.analytics_cache OWNER TO mariuszbudzisz;

--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: agencydark
--

CREATE TABLE public.audit_logs (
    id uuid NOT NULL,
    agency_id uuid,
    user_id uuid,
    action character varying(255) NOT NULL,
    resource_type character varying(255),
    resource_id uuid,
    data json,
    ip_address inet,
    user_agent text,
    created_at timestamp without time zone
);


ALTER TABLE public.audit_logs OWNER TO agencydark;

--
-- Name: billing_cycles; Type: TABLE; Schema: public; Owner: mariuszbudzisz
--

CREATE TABLE public.billing_cycles (
    id uuid NOT NULL,
    agency_id uuid NOT NULL,
    cycle_start timestamp with time zone NOT NULL,
    cycle_end timestamp with time zone NOT NULL,
    gross_revenue numeric(12,2),
    total_commission numeric(12,2),
    net_revenue numeric(12,2),
    is_closed boolean,
    closed_at timestamp with time zone,
    closed_by uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.billing_cycles OWNER TO mariuszbudzisz;

--
-- Name: branding_assets; Type: TABLE; Schema: public; Owner: mariuszbudzisz
--

CREATE TABLE public.branding_assets (
    id uuid NOT NULL,
    agency_id uuid,
    model_id uuid,
    asset_type character varying(50) NOT NULL,
    file_name character varying(255) NOT NULL,
    file_url character varying(500) NOT NULL,
    file_size integer,
    mime_type character varying(100),
    width integer,
    height integer,
    is_active boolean,
    is_default boolean,
    uploaded_at timestamp with time zone DEFAULT now(),
    uploaded_by uuid
);


ALTER TABLE public.branding_assets OWNER TO mariuszbudzisz;

--
-- Name: category_performance; Type: TABLE; Schema: public; Owner: mariuszbudzisz
--

CREATE TABLE public.category_performance (
    id uuid NOT NULL,
    model_id uuid NOT NULL,
    category_name character varying(100) NOT NULL,
    period_start timestamp with time zone NOT NULL,
    period_end timestamp with time zone NOT NULL,
    content_count integer,
    total_views integer,
    total_likes integer,
    total_comments integer,
    total_revenue numeric(10,2),
    avg_revenue_per_content numeric(10,2),
    avg_engagement_rate numeric(5,2),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.category_performance OWNER TO mariuszbudzisz;

--
-- Name: chat_messages; Type: TABLE; Schema: public; Owner: mariuszbudzisz
--

CREATE TABLE public.chat_messages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    model_id uuid NOT NULL,
    fan_id character varying(255) NOT NULL,
    fan_username character varying(255),
    message text NOT NULL,
    is_from_fan boolean DEFAULT true,
    is_read boolean DEFAULT false,
    assigned_chatter_id uuid,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.chat_messages OWNER TO mariuszbudzisz;

--
-- Name: commission_rules; Type: TABLE; Schema: public; Owner: mariuszbudzisz
--

CREATE TABLE public.commission_rules (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    agency_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    tier character varying(50),
    rate numeric(5,2) NOT NULL,
    min_subscribers integer,
    max_subscribers integer,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.commission_rules OWNER TO mariuszbudzisz;

--
-- Name: content_performance; Type: TABLE; Schema: public; Owner: mariuszbudzisz
--

CREATE TABLE public.content_performance (
    id uuid NOT NULL,
    model_id uuid NOT NULL,
    content_type character varying(50) NOT NULL,
    content_id character varying(255) NOT NULL,
    title character varying(500),
    categories json,
    tags json,
    views integer,
    likes integer,
    comments integer,
    shares integer,
    total_revenue numeric(10,2),
    purchase_count integer,
    is_ppv boolean,
    ppv_price numeric(10,2),
    duration_seconds integer,
    published_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.content_performance OWNER TO mariuszbudzisz;

--
-- Name: crypto_wallets; Type: TABLE; Schema: public; Owner: mariuszbudzisz
--

CREATE TABLE public.crypto_wallets (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    network public.cryptonetwork NOT NULL,
    address character varying(255) NOT NULL,
    label character varying(100),
    is_verified boolean,
    verified_at timestamp with time zone,
    verification_signature character varying(500),
    is_active boolean,
    is_default boolean,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.crypto_wallets OWNER TO mariuszbudzisz;

--
-- Name: email_templates; Type: TABLE; Schema: public; Owner: mariuszbudzisz
--

CREATE TABLE public.email_templates (
    id uuid NOT NULL,
    agency_id uuid NOT NULL,
    template_type character varying(50) NOT NULL,
    language character varying(10),
    subject character varying(200) NOT NULL,
    html_body text NOT NULL,
    text_body text,
    variables json,
    is_active boolean,
    is_default boolean,
    test_data json,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone,
    updated_by uuid
);


ALTER TABLE public.email_templates OWNER TO mariuszbudzisz;

--
-- Name: fan_claims; Type: TABLE; Schema: public; Owner: agencydark
--

CREATE TABLE public.fan_claims (
    id uuid NOT NULL,
    fan_id uuid NOT NULL,
    model_id uuid NOT NULL,
    chatter_id uuid,
    claimed_by_model boolean,
    claimed_at timestamp without time zone,
    expires_at timestamp without time zone,
    is_active boolean,
    released_at timestamp without time zone,
    released_by_id uuid
);


ALTER TABLE public.fan_claims OWNER TO agencydark;

--
-- Name: fan_spending_history; Type: TABLE; Schema: public; Owner: mariuszbudzisz
--

CREATE TABLE public.fan_spending_history (
    id uuid NOT NULL,
    fan_id uuid NOT NULL,
    model_id uuid NOT NULL,
    period_start timestamp with time zone NOT NULL,
    period_end timestamp with time zone NOT NULL,
    subscription_amount numeric(10,2),
    tip_amount numeric(10,2),
    ppv_amount numeric(10,2),
    total_amount numeric(10,2),
    tip_count integer,
    ppv_purchase_count integer,
    messages_sent integer,
    messages_received integer,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.fan_spending_history OWNER TO mariuszbudzisz;

--
-- Name: fans; Type: TABLE; Schema: public; Owner: agencydark
--

CREATE TABLE public.fans (
    id uuid NOT NULL,
    model_id uuid NOT NULL,
    onlyfans_user_id character varying(255) NOT NULL,
    username character varying(255) NOT NULL,
    display_name character varying(255),
    avatar_url text,
    is_subscriber boolean,
    is_paying boolean,
    subscription_price numeric(10,2),
    subscribed_at timestamp without time zone,
    expires_at timestamp without time zone,
    total_spent numeric(12,2),
    message_count integer,
    tip_count integer,
    ppv_purchased_count integer,
    last_active_at timestamp without time zone,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


ALTER TABLE public.fans OWNER TO agencydark;

--
-- Name: financial_transactions; Type: TABLE; Schema: public; Owner: mariuszbudzisz
--

CREATE TABLE public.financial_transactions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    agency_id uuid NOT NULL,
    model_id uuid NOT NULL,
    transaction_type character varying(50) NOT NULL,
    amount numeric(10,2) NOT NULL,
    commission_amount numeric(10,2),
    status character varying(50) DEFAULT 'pending'::character varying,
    external_transaction_id character varying(255),
    processed_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.financial_transactions OWNER TO mariuszbudzisz;

--
-- Name: invoices; Type: TABLE; Schema: public; Owner: mariuszbudzisz
--

CREATE TABLE public.invoices (
    id uuid NOT NULL,
    invoice_number character varying(50) NOT NULL,
    billing_cycle_id uuid,
    agency_id uuid NOT NULL,
    model_id uuid,
    status public.invoicestatus,
    issue_date timestamp with time zone,
    due_date timestamp with time zone,
    paid_date timestamp with time zone,
    subtotal numeric(12,2) NOT NULL,
    tax_rate numeric(5,2),
    tax_amount numeric(12,2),
    total_amount numeric(12,2) NOT NULL,
    paid_amount numeric(12,2),
    line_items json,
    payment_method character varying(50),
    payment_reference character varying(255),
    notes character varying(1000),
    terms_conditions character varying(2000),
    pdf_url character varying(500),
    pdf_generated_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.invoices OWNER TO mariuszbudzisz;

--
-- Name: metric_snapshots; Type: TABLE; Schema: public; Owner: mariuszbudzisz
--

CREATE TABLE public.metric_snapshots (
    id uuid NOT NULL,
    model_id uuid NOT NULL,
    "timestamp" timestamp with time zone NOT NULL,
    total_subscribers integer,
    paying_subscribers integer,
    non_paying_fans integer,
    new_subscribers integer,
    lost_subscribers integer,
    total_revenue numeric(12,2),
    subscription_revenue numeric(12,2),
    tip_revenue numeric(12,2),
    ppv_revenue numeric(12,2),
    total_posts integer,
    total_messages_sent integer,
    total_messages_received integer,
    avg_fan_spend numeric(10,2),
    conversion_rate numeric(5,2),
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.metric_snapshots OWNER TO mariuszbudzisz;

--
-- Name: model_assignments; Type: TABLE; Schema: public; Owner: mariuszbudzisz
--

CREATE TABLE public.model_assignments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    chatter_id uuid NOT NULL,
    model_id uuid NOT NULL,
    agency_id uuid NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    assigned_at timestamp without time zone DEFAULT now() NOT NULL,
    assigned_by uuid NOT NULL,
    notes text,
    priority character varying(50) DEFAULT 'normal'::character varying
);


ALTER TABLE public.model_assignments OWNER TO mariuszbudzisz;

--
-- Name: model_branding; Type: TABLE; Schema: public; Owner: mariuszbudzisz
--

CREATE TABLE public.model_branding (
    id uuid NOT NULL,
    model_id uuid NOT NULL,
    display_name character varying(100),
    bio text,
    theme_override json,
    use_agency_theme boolean,
    content_tags json,
    links json,
    watermark_enabled boolean,
    watermark_text character varying(100),
    watermark_position character varying(20),
    watermark_opacity integer,
    auto_welcome_message text,
    tip_thank_you_message text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.model_branding OWNER TO mariuszbudzisz;

--
-- Name: model_chatters; Type: TABLE; Schema: public; Owner: agencydark
--

CREATE TABLE public.model_chatters (
    id uuid NOT NULL,
    model_id uuid NOT NULL,
    chatter_id uuid NOT NULL,
    is_active boolean,
    assigned_at timestamp without time zone
);


ALTER TABLE public.model_chatters OWNER TO agencydark;

--
-- Name: model_profiles; Type: TABLE; Schema: public; Owner: agencydark
--

CREATE TABLE public.model_profiles (
    id uuid NOT NULL,
    agency_id uuid NOT NULL,
    user_id uuid,
    onlyfans_username character varying(255) NOT NULL,
    onlyfans_user_id character varying(255),
    display_name character varying(255),
    bio text,
    profile_photo_url text,
    cover_photo_url text,
    inflow_api_key text,
    onlyfans_api_key text,
    subscriber_count integer,
    paying_subscriber_count integer,
    total_earnings numeric(12,2),
    commission_rate numeric(5,2),
    is_active boolean,
    last_sync_at timestamp without time zone,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


ALTER TABLE public.model_profiles OWNER TO agencydark;

--
-- Name: notifications; Type: TABLE; Schema: public; Owner: agencydark
--

CREATE TABLE public.notifications (
    id uuid NOT NULL,
    agency_id uuid,
    user_id uuid,
    type public.notificationtype NOT NULL,
    title character varying(255) NOT NULL,
    message text,
    data json,
    read boolean,
    created_at timestamp without time zone
);


ALTER TABLE public.notifications OWNER TO agencydark;

--
-- Name: payment_gateway_configs; Type: TABLE; Schema: public; Owner: mariuszbudzisz
--

CREATE TABLE public.payment_gateway_configs (
    id uuid NOT NULL,
    agency_id uuid,
    provider character varying(50) NOT NULL,
    is_active boolean,
    is_test_mode boolean,
    api_key character varying(500),
    api_secret character varying(500),
    webhook_secret character varying(500),
    merchant_id character varying(255),
    supported_currencies json,
    config json,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.payment_gateway_configs OWNER TO mariuszbudzisz;

--
-- Name: payouts; Type: TABLE; Schema: public; Owner: mariuszbudzisz
--

CREATE TABLE public.payouts (
    id uuid NOT NULL,
    billing_cycle_id uuid NOT NULL,
    recipient_id uuid NOT NULL,
    recipient_type character varying(20) NOT NULL,
    amount numeric(12,2) NOT NULL,
    currency character varying(10),
    status public.payoutstatus,
    payment_method character varying(50) NOT NULL,
    payment_details json,
    transaction_id character varying(255),
    transaction_hash character varying(255),
    scheduled_at timestamp with time zone,
    processed_at timestamp with time zone,
    completed_at timestamp with time zone,
    failure_reason character varying(500),
    retry_count integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.payouts OWNER TO mariuszbudzisz;

--
-- Name: revenue_transactions; Type: TABLE; Schema: public; Owner: mariuszbudzisz
--

CREATE TABLE public.revenue_transactions (
    id uuid NOT NULL,
    model_id uuid NOT NULL,
    fan_id uuid NOT NULL,
    transaction_type character varying(50) NOT NULL,
    amount numeric(10,2) NOT NULL,
    currency character varying(3),
    source character varying(20) NOT NULL,
    external_transaction_id character varying(255),
    content_type character varying(50),
    content_id character varying(255),
    transaction_date timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.revenue_transactions OWNER TO mariuszbudzisz;

--
-- Name: sessions; Type: TABLE; Schema: public; Owner: agencydark
--

CREATE TABLE public.sessions (
    id uuid NOT NULL,
    user_id uuid,
    refresh_token character varying(500) NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    is_active boolean,
    user_agent text,
    ip_address inet,
    refreshed_at timestamp without time zone,
    created_at timestamp without time zone
);


ALTER TABLE public.sessions OWNER TO agencydark;

--
-- Name: theme_configurations; Type: TABLE; Schema: public; Owner: mariuszbudzisz
--

CREATE TABLE public.theme_configurations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    agency_id uuid NOT NULL,
    default_mode character varying(10) DEFAULT 'light'::character varying,
    allow_user_preference boolean DEFAULT true,
    light_theme jsonb,
    dark_theme jsonb,
    custom_css text,
    font_family character varying(100),
    font_size_base character varying(10),
    layout_config jsonb,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    updated_by uuid
);


ALTER TABLE public.theme_configurations OWNER TO mariuszbudzisz;

--
-- Name: theme_presets; Type: TABLE; Schema: public; Owner: mariuszbudzisz
--

CREATE TABLE public.theme_presets (
    id uuid NOT NULL,
    name character varying(100) NOT NULL,
    description character varying(500),
    preview_url character varying(500),
    light_theme json NOT NULL,
    dark_theme json NOT NULL,
    category character varying(50),
    tags json,
    is_premium boolean,
    usage_count integer,
    is_active boolean,
    created_at timestamp with time zone DEFAULT now(),
    created_by uuid
);


ALTER TABLE public.theme_presets OWNER TO mariuszbudzisz;

--
-- Name: users; Type: TABLE; Schema: public; Owner: agencydark
--

CREATE TABLE public.users (
    id uuid NOT NULL,
    agency_id uuid,
    email character varying(255) NOT NULL,
    hashed_password character varying(255) NOT NULL,
    full_name character varying(255),
    role public.userrole NOT NULL,
    is_active boolean,
    is_verified boolean,
    email_verification_token character varying(255),
    password_reset_token character varying(255),
    password_reset_expires timestamp without time zone,
    last_login timestamp without time zone,
    verified_at timestamp without time zone,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


ALTER TABLE public.users OWNER TO agencydark;

--
-- Data for Name: agencies; Type: TABLE DATA; Schema: public; Owner: agencydark
--

COPY public.agencies (id, name, slug, domain, settings, subscription_status, subscription_ends_at, created_at, updated_at) FROM stdin;
11111111-1111-1111-1111-111111111111	Elite Models Agency	elite-models	\N	\N	\N	\N	2025-08-05 18:22:56.102924	2025-08-05 18:22:56.102924
22222222-2222-2222-2222-222222222222	Premium Talent Management	premium-talent	\N	\N	\N	\N	2025-08-05 18:22:56.102924	2025-08-05 18:22:56.102924
33333333-3333-3333-3333-333333333333	Rising Stars Agency	rising-stars	\N	\N	\N	\N	2025-08-05 18:22:56.102924	2025-08-05 18:22:56.102924
\.


--
-- Data for Name: agency_profiles; Type: TABLE DATA; Schema: public; Owner: mariuszbudzisz
--

COPY public.agency_profiles (id, agency_id, display_name, tagline, description, support_email, support_phone, website_url, social_links, legal_name, tax_id, address, brand_guidelines, custom_domain, custom_domain_verified, from_email_name, from_email_address, reply_to_email, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: analytics_cache; Type: TABLE DATA; Schema: public; Owner: mariuszbudzisz
--

COPY public.analytics_cache (id, cache_type, entity_type, entity_id, period_start, period_end, filters, data, computed_at, expires_at) FROM stdin;
\.


--
-- Data for Name: audit_logs; Type: TABLE DATA; Schema: public; Owner: agencydark
--

COPY public.audit_logs (id, agency_id, user_id, action, resource_type, resource_id, data, ip_address, user_agent, created_at) FROM stdin;
\.


--
-- Data for Name: billing_cycles; Type: TABLE DATA; Schema: public; Owner: mariuszbudzisz
--

COPY public.billing_cycles (id, agency_id, cycle_start, cycle_end, gross_revenue, total_commission, net_revenue, is_closed, closed_at, closed_by, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: branding_assets; Type: TABLE DATA; Schema: public; Owner: mariuszbudzisz
--

COPY public.branding_assets (id, agency_id, model_id, asset_type, file_name, file_url, file_size, mime_type, width, height, is_active, is_default, uploaded_at, uploaded_by) FROM stdin;
\.


--
-- Data for Name: category_performance; Type: TABLE DATA; Schema: public; Owner: mariuszbudzisz
--

COPY public.category_performance (id, model_id, category_name, period_start, period_end, content_count, total_views, total_likes, total_comments, total_revenue, avg_revenue_per_content, avg_engagement_rate, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: chat_messages; Type: TABLE DATA; Schema: public; Owner: mariuszbudzisz
--

COPY public.chat_messages (id, model_id, fan_id, fan_username, message, is_from_fan, is_read, assigned_chatter_id, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: commission_rules; Type: TABLE DATA; Schema: public; Owner: mariuszbudzisz
--

COPY public.commission_rules (id, agency_id, name, tier, rate, min_subscribers, max_subscribers, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: content_performance; Type: TABLE DATA; Schema: public; Owner: mariuszbudzisz
--

COPY public.content_performance (id, model_id, content_type, content_id, title, categories, tags, views, likes, comments, shares, total_revenue, purchase_count, is_ppv, ppv_price, duration_seconds, published_at, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: crypto_wallets; Type: TABLE DATA; Schema: public; Owner: mariuszbudzisz
--

COPY public.crypto_wallets (id, user_id, network, address, label, is_verified, verified_at, verification_signature, is_active, is_default, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: email_templates; Type: TABLE DATA; Schema: public; Owner: mariuszbudzisz
--

COPY public.email_templates (id, agency_id, template_type, language, subject, html_body, text_body, variables, is_active, is_default, test_data, created_at, updated_at, updated_by) FROM stdin;
\.


--
-- Data for Name: fan_claims; Type: TABLE DATA; Schema: public; Owner: agencydark
--

COPY public.fan_claims (id, fan_id, model_id, chatter_id, claimed_by_model, claimed_at, expires_at, is_active, released_at, released_by_id) FROM stdin;
\.


--
-- Data for Name: fan_spending_history; Type: TABLE DATA; Schema: public; Owner: mariuszbudzisz
--

COPY public.fan_spending_history (id, fan_id, model_id, period_start, period_end, subscription_amount, tip_amount, ppv_amount, total_amount, tip_count, ppv_purchase_count, messages_sent, messages_received, created_at) FROM stdin;
\.


--
-- Data for Name: fans; Type: TABLE DATA; Schema: public; Owner: agencydark
--

COPY public.fans (id, model_id, onlyfans_user_id, username, display_name, avatar_url, is_subscriber, is_paying, subscription_price, subscribed_at, expires_at, total_spent, message_count, tip_count, ppv_purchased_count, last_active_at, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: financial_transactions; Type: TABLE DATA; Schema: public; Owner: mariuszbudzisz
--

COPY public.financial_transactions (id, agency_id, model_id, transaction_type, amount, commission_amount, status, external_transaction_id, processed_at, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: invoices; Type: TABLE DATA; Schema: public; Owner: mariuszbudzisz
--

COPY public.invoices (id, invoice_number, billing_cycle_id, agency_id, model_id, status, issue_date, due_date, paid_date, subtotal, tax_rate, tax_amount, total_amount, paid_amount, line_items, payment_method, payment_reference, notes, terms_conditions, pdf_url, pdf_generated_at, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: metric_snapshots; Type: TABLE DATA; Schema: public; Owner: mariuszbudzisz
--

COPY public.metric_snapshots (id, model_id, "timestamp", total_subscribers, paying_subscribers, non_paying_fans, new_subscribers, lost_subscribers, total_revenue, subscription_revenue, tip_revenue, ppv_revenue, total_posts, total_messages_sent, total_messages_received, avg_fan_spend, conversion_rate, created_at) FROM stdin;
\.


--
-- Data for Name: model_assignments; Type: TABLE DATA; Schema: public; Owner: mariuszbudzisz
--

COPY public.model_assignments (id, chatter_id, model_id, agency_id, is_active, assigned_at, assigned_by, notes, priority) FROM stdin;
33d813ab-f419-4ae9-b8ca-21acf4929cf5	b6666666-6666-6666-6666-666666666666	b3333333-3333-3333-3333-333333333333	11111111-1111-1111-1111-111111111111	t	2025-08-05 20:25:03.21977	b2222222-2222-2222-2222-222222222222	Initial assignment for testing	normal
42bb53e8-2a0c-4d37-b18f-2f0c367b1f62	b6666666-6666-6666-6666-666666666666	b4444444-4444-4444-4444-444444444444	11111111-1111-1111-1111-111111111111	t	2025-08-05 20:25:03.21977	b2222222-2222-2222-2222-222222222222	Initial assignment for testing	normal
249f7af9-5319-4789-bd34-b11218a30bd2	b7777777-7777-7777-7777-777777777777	b5555555-5555-5555-5555-555555555555	11111111-1111-1111-1111-111111111111	t	2025-08-05 20:25:03.21977	b2222222-2222-2222-2222-222222222222	Initial assignment for testing	normal
1f18383f-740c-4654-b77f-f18882e1ec46	c4444444-4444-4444-4444-444444444444	c2222222-2222-2222-2222-222222222222	22222222-2222-2222-2222-222222222222	t	2025-08-05 20:25:03.21977	b2222222-2222-2222-2222-222222222222	Initial assignment for testing	normal
1218a20b-5a67-4924-bc72-aab4489d1e93	c4444444-4444-4444-4444-444444444444	c3333333-3333-3333-3333-333333333333	22222222-2222-2222-2222-222222222222	t	2025-08-05 20:25:03.21977	b2222222-2222-2222-2222-222222222222	Initial assignment for testing	normal
\.


--
-- Data for Name: model_branding; Type: TABLE DATA; Schema: public; Owner: mariuszbudzisz
--

COPY public.model_branding (id, model_id, display_name, bio, theme_override, use_agency_theme, content_tags, links, watermark_enabled, watermark_text, watermark_position, watermark_opacity, auto_welcome_message, tip_thank_you_message, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: model_chatters; Type: TABLE DATA; Schema: public; Owner: agencydark
--

COPY public.model_chatters (id, model_id, chatter_id, is_active, assigned_at) FROM stdin;
\.


--
-- Data for Name: model_profiles; Type: TABLE DATA; Schema: public; Owner: agencydark
--

COPY public.model_profiles (id, agency_id, user_id, onlyfans_username, onlyfans_user_id, display_name, bio, profile_photo_url, cover_photo_url, inflow_api_key, onlyfans_api_key, subscriber_count, paying_subscriber_count, total_earnings, commission_rate, is_active, last_sync_at, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: notifications; Type: TABLE DATA; Schema: public; Owner: agencydark
--

COPY public.notifications (id, agency_id, user_id, type, title, message, data, read, created_at) FROM stdin;
\.


--
-- Data for Name: payment_gateway_configs; Type: TABLE DATA; Schema: public; Owner: mariuszbudzisz
--

COPY public.payment_gateway_configs (id, agency_id, provider, is_active, is_test_mode, api_key, api_secret, webhook_secret, merchant_id, supported_currencies, config, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: payouts; Type: TABLE DATA; Schema: public; Owner: mariuszbudzisz
--

COPY public.payouts (id, billing_cycle_id, recipient_id, recipient_type, amount, currency, status, payment_method, payment_details, transaction_id, transaction_hash, scheduled_at, processed_at, completed_at, failure_reason, retry_count, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: revenue_transactions; Type: TABLE DATA; Schema: public; Owner: mariuszbudzisz
--

COPY public.revenue_transactions (id, model_id, fan_id, transaction_type, amount, currency, source, external_transaction_id, content_type, content_id, transaction_date, created_at) FROM stdin;
\.


--
-- Data for Name: sessions; Type: TABLE DATA; Schema: public; Owner: agencydark
--

COPY public.sessions (id, user_id, refresh_token, expires_at, is_active, user_agent, ip_address, refreshed_at, created_at) FROM stdin;
\.


--
-- Data for Name: theme_configurations; Type: TABLE DATA; Schema: public; Owner: mariuszbudzisz
--

COPY public.theme_configurations (id, agency_id, default_mode, allow_user_preference, light_theme, dark_theme, custom_css, font_family, font_size_base, layout_config, created_at, updated_at, updated_by) FROM stdin;
\.


--
-- Data for Name: theme_presets; Type: TABLE DATA; Schema: public; Owner: mariuszbudzisz
--

COPY public.theme_presets (id, name, description, preview_url, light_theme, dark_theme, category, tags, is_premium, usage_count, is_active, created_at, created_by) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: agencydark
--

COPY public.users (id, agency_id, email, hashed_password, full_name, role, is_active, is_verified, email_verification_token, password_reset_token, password_reset_expires, last_login, verified_at, created_at, updated_at) FROM stdin;
aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa	\N	admin@agency.com	$2b$12$oHrNzjdnw5FTurPrWMAYY.6ZOkWWgXfz.npxC9ks39gE2VvfFmbxe	Super Admin	SUPER_ADMIN	t	t	\N	\N	\N	\N	\N	2025-08-05 18:22:56.102924	2025-08-05 18:22:56.102924
b1111111-1111-1111-1111-111111111111	11111111-1111-1111-1111-111111111111	owner@elitemodels.com	$2b$12$M2j4P92Byn6fljgzl3q7TuuRxGFlBhCM/RMAf5wE1N7Cx6ptd3uWK	James Thompson	AGENCY_OWNER	t	t	\N	\N	\N	\N	\N	2025-08-05 18:22:56.102924	2025-08-05 18:22:56.102924
b2222222-2222-2222-2222-222222222222	11111111-1111-1111-1111-111111111111	admin@elitemodels.com	$2b$12$8j/YRy9PrH2/8jPvjzVcVeGiOZbpL43O6B3C4fbp6S.XVZV4pYlUO	Mary Johnson	AGENCY_ADMIN	t	t	\N	\N	\N	\N	\N	2025-08-05 18:22:56.102924	2025-08-05 18:22:56.102924
b3333333-3333-3333-3333-333333333333	11111111-1111-1111-1111-111111111111	sarah@elitemodels.com	$2b$12$vycGgTsruA5CytbQhkO5HeTDHhYKp5yU16qX2tz/iVJvgUG0qUxea	Sarah Johnson	MODEL	t	t	\N	\N	\N	\N	\N	2025-08-05 18:22:56.102924	2025-08-05 18:22:56.102924
b4444444-4444-4444-4444-444444444444	11111111-1111-1111-1111-111111111111	emma@elitemodels.com	$2b$12$dhKnw6HOwKeFk4rjtcNhDuAtWcGepLVYDNxiuJs7cv.grFydcLp0K	Emma Davis	MODEL	t	t	\N	\N	\N	\N	\N	2025-08-05 18:22:56.102924	2025-08-05 18:22:56.102924
b5555555-5555-5555-5555-555555555555	11111111-1111-1111-1111-111111111111	lisa@elitemodels.com	$2b$12$ZXyLO2QDE6uC9YnbamzLz.v3gqHt1p9SrjlbJGFT9DrZm5Ukdi2B6	Lisa Brown	MODEL	t	t	\N	\N	\N	\N	\N	2025-08-05 18:22:56.102924	2025-08-05 18:22:56.102924
b6666666-6666-6666-6666-666666666666	11111111-1111-1111-1111-111111111111	john@elitemodels.com	$2b$12$BC3VyoJTPSYT4V2ppPD4..75Pp0FHCdK0kPe.GDSOgEAb.x2vm9Si	John Smith	CHATTER	t	t	\N	\N	\N	\N	\N	2025-08-05 18:22:56.102924	2025-08-05 18:22:56.102924
b7777777-7777-7777-7777-777777777777	11111111-1111-1111-1111-111111111111	mike@elitemodels.com	$2b$12$MpFnj8QQslyacbDjPBOMxutE665bVim/jLUNTesVqbGelMZyKkPPe	Mike Wilson	CHATTER	t	t	\N	\N	\N	\N	\N	2025-08-05 18:22:56.102924	2025-08-05 18:22:56.102924
b8888888-8888-8888-8888-888888888888	11111111-1111-1111-1111-111111111111	support@elitemodels.com	$2b$12$3Lpy895IyzsJkwUajmhFQuwSDtwU.p56ETBmrtKsf/uJvqxC/hIRW	Support Staff	AGENCY_MEMBER	t	t	\N	\N	\N	\N	\N	2025-08-05 18:22:56.102924	2025-08-05 18:22:56.102924
c1111111-1111-1111-1111-111111111111	22222222-2222-2222-2222-222222222222	owner@premiumtalent.com	$2b$12$/3JgOOGlJv9quV5kTxl.KOZa5Q2fdMPWw31RpQRE5/7rkNTrugXL6	Robert Martinez	AGENCY_OWNER	t	t	\N	\N	\N	\N	\N	2025-08-05 18:22:56.102924	2025-08-05 18:22:56.102924
c2222222-2222-2222-2222-222222222222	22222222-2222-2222-2222-222222222222	jessica@premiumtalent.com	$2b$12$7NU.ADk7ltj4WS5Z0SZEjeDAQllcT5SuoCadSgUcUOBuxy/LWQ2Eu	Jessica White	MODEL	t	t	\N	\N	\N	\N	\N	2025-08-05 18:22:56.102924	2025-08-05 18:22:56.102924
c3333333-3333-3333-3333-333333333333	22222222-2222-2222-2222-222222222222	ashley@premiumtalent.com	$2b$12$nqk02QJWLOsypPA1/WOKqOngPslyE5U40ViKSMjkUeBj.w20OMO2a	Ashley Green	MODEL	t	t	\N	\N	\N	\N	\N	2025-08-05 18:22:56.102924	2025-08-05 18:22:56.102924
c4444444-4444-4444-4444-444444444444	22222222-2222-2222-2222-222222222222	alex@premiumtalent.com	$2b$12$dV51AWZV4LX7jZ8uWXbo0.qatdU5Tm3u5dGkl14J2Ob4kc5kDEELe	Alex Turner	CHATTER	t	t	\N	\N	\N	\N	\N	2025-08-05 18:22:56.102924	2025-08-05 18:22:56.102924
d1111111-1111-1111-1111-111111111111	33333333-3333-3333-3333-333333333333	owner@risingstars.com	$2b$12$EogC3bYZwjlkZHzHAOWO1eWUpkQ4F1J5u/tS4w17Yy5.df1DYf2Ly	Linda Chen	AGENCY_OWNER	t	t	\N	\N	\N	\N	\N	2025-08-05 18:22:56.102924	2025-08-05 18:22:56.102924
d2222222-2222-2222-2222-222222222222	33333333-3333-3333-3333-333333333333	sophia@risingstars.com	$2b$12$GguQJVO.zVn5f2xTBx5N8eLHRRlSPWwnPQgh0.2HuxYl9MwLguFUi	Sophia Rodriguez	MODEL	t	t	\N	\N	\N	\N	\N	2025-08-05 18:22:56.102924	2025-08-05 18:22:56.102924
\.


--
-- Name: chat_messages chat_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_pkey PRIMARY KEY (id);


--
-- Name: commission_rules commission_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.commission_rules
    ADD CONSTRAINT commission_rules_pkey PRIMARY KEY (id);


--
-- Name: financial_transactions financial_transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.financial_transactions
    ADD CONSTRAINT financial_transactions_pkey PRIMARY KEY (id);


--
-- Name: model_assignments model_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.model_assignments
    ADD CONSTRAINT model_assignments_pkey PRIMARY KEY (id);


--
-- Name: agencies pk_agencies; Type: CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.agencies
    ADD CONSTRAINT pk_agencies PRIMARY KEY (id);


--
-- Name: agency_profiles pk_agency_profiles; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.agency_profiles
    ADD CONSTRAINT pk_agency_profiles PRIMARY KEY (id);


--
-- Name: analytics_cache pk_analytics_cache; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.analytics_cache
    ADD CONSTRAINT pk_analytics_cache PRIMARY KEY (id);


--
-- Name: audit_logs pk_audit_logs; Type: CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT pk_audit_logs PRIMARY KEY (id);


--
-- Name: billing_cycles pk_billing_cycles; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.billing_cycles
    ADD CONSTRAINT pk_billing_cycles PRIMARY KEY (id);


--
-- Name: branding_assets pk_branding_assets; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.branding_assets
    ADD CONSTRAINT pk_branding_assets PRIMARY KEY (id);


--
-- Name: category_performance pk_category_performance; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.category_performance
    ADD CONSTRAINT pk_category_performance PRIMARY KEY (id);


--
-- Name: content_performance pk_content_performance; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.content_performance
    ADD CONSTRAINT pk_content_performance PRIMARY KEY (id);


--
-- Name: crypto_wallets pk_crypto_wallets; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.crypto_wallets
    ADD CONSTRAINT pk_crypto_wallets PRIMARY KEY (id);


--
-- Name: email_templates pk_email_templates; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.email_templates
    ADD CONSTRAINT pk_email_templates PRIMARY KEY (id);


--
-- Name: fan_claims pk_fan_claims; Type: CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.fan_claims
    ADD CONSTRAINT pk_fan_claims PRIMARY KEY (id);


--
-- Name: fan_spending_history pk_fan_spending_history; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.fan_spending_history
    ADD CONSTRAINT pk_fan_spending_history PRIMARY KEY (id);


--
-- Name: fans pk_fans; Type: CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.fans
    ADD CONSTRAINT pk_fans PRIMARY KEY (id);


--
-- Name: invoices pk_invoices; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT pk_invoices PRIMARY KEY (id);


--
-- Name: metric_snapshots pk_metric_snapshots; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.metric_snapshots
    ADD CONSTRAINT pk_metric_snapshots PRIMARY KEY (id);


--
-- Name: model_branding pk_model_branding; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.model_branding
    ADD CONSTRAINT pk_model_branding PRIMARY KEY (id);


--
-- Name: model_chatters pk_model_chatters; Type: CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.model_chatters
    ADD CONSTRAINT pk_model_chatters PRIMARY KEY (id);


--
-- Name: model_profiles pk_model_profiles; Type: CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.model_profiles
    ADD CONSTRAINT pk_model_profiles PRIMARY KEY (id);


--
-- Name: notifications pk_notifications; Type: CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT pk_notifications PRIMARY KEY (id);


--
-- Name: payment_gateway_configs pk_payment_gateway_configs; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.payment_gateway_configs
    ADD CONSTRAINT pk_payment_gateway_configs PRIMARY KEY (id);


--
-- Name: payouts pk_payouts; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.payouts
    ADD CONSTRAINT pk_payouts PRIMARY KEY (id);


--
-- Name: revenue_transactions pk_revenue_transactions; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.revenue_transactions
    ADD CONSTRAINT pk_revenue_transactions PRIMARY KEY (id);


--
-- Name: sessions pk_sessions; Type: CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT pk_sessions PRIMARY KEY (id);


--
-- Name: theme_presets pk_theme_presets; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.theme_presets
    ADD CONSTRAINT pk_theme_presets PRIMARY KEY (id);


--
-- Name: users pk_users; Type: CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT pk_users PRIMARY KEY (id);


--
-- Name: theme_configurations theme_configurations_agency_id_key; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.theme_configurations
    ADD CONSTRAINT theme_configurations_agency_id_key UNIQUE (agency_id);


--
-- Name: theme_configurations theme_configurations_pkey; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.theme_configurations
    ADD CONSTRAINT theme_configurations_pkey PRIMARY KEY (id);


--
-- Name: model_assignments unique_chatter_model_assignment; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.model_assignments
    ADD CONSTRAINT unique_chatter_model_assignment UNIQUE (chatter_id, model_id);


--
-- Name: agencies uq_agencies_slug; Type: CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.agencies
    ADD CONSTRAINT uq_agencies_slug UNIQUE (slug);


--
-- Name: agency_profiles uq_agency_profiles_agency_id; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.agency_profiles
    ADD CONSTRAINT uq_agency_profiles_agency_id UNIQUE (agency_id);


--
-- Name: invoices uq_invoices_invoice_number; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT uq_invoices_invoice_number UNIQUE (invoice_number);


--
-- Name: model_branding uq_model_branding_model_id; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.model_branding
    ADD CONSTRAINT uq_model_branding_model_id UNIQUE (model_id);


--
-- Name: model_chatters uq_model_chatter; Type: CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.model_chatters
    ADD CONSTRAINT uq_model_chatter UNIQUE (model_id, chatter_id);


--
-- Name: fans uq_model_fan; Type: CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.fans
    ADD CONSTRAINT uq_model_fan UNIQUE (model_id, onlyfans_user_id);


--
-- Name: model_profiles uq_model_profiles_onlyfans_user_id; Type: CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.model_profiles
    ADD CONSTRAINT uq_model_profiles_onlyfans_user_id UNIQUE (onlyfans_user_id);


--
-- Name: model_profiles uq_model_profiles_onlyfans_username; Type: CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.model_profiles
    ADD CONSTRAINT uq_model_profiles_onlyfans_username UNIQUE (onlyfans_username);


--
-- Name: sessions uq_sessions_refresh_token; Type: CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT uq_sessions_refresh_token UNIQUE (refresh_token);


--
-- Name: theme_presets uq_theme_presets_name; Type: CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.theme_presets
    ADD CONSTRAINT uq_theme_presets_name UNIQUE (name);


--
-- Name: idx_active_fan_claim; Type: INDEX; Schema: public; Owner: agencydark
--

CREATE UNIQUE INDEX idx_active_fan_claim ON public.fan_claims USING btree (fan_id, is_active) WHERE (is_active = true);


--
-- Name: idx_agency_profile_agency; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_agency_profile_agency ON public.agency_profiles USING btree (agency_id);


--
-- Name: idx_analytics_cache_expires; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_analytics_cache_expires ON public.analytics_cache USING btree (expires_at);


--
-- Name: idx_analytics_cache_lookup; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_analytics_cache_lookup ON public.analytics_cache USING btree (cache_type, entity_type, entity_id, period_start, period_end);


--
-- Name: idx_billing_cycle_agency; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_billing_cycle_agency ON public.billing_cycles USING btree (agency_id);


--
-- Name: idx_billing_cycle_period; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_billing_cycle_period ON public.billing_cycles USING btree (cycle_start, cycle_end);


--
-- Name: idx_branding_asset_agency; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_branding_asset_agency ON public.branding_assets USING btree (agency_id);


--
-- Name: idx_branding_asset_model; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_branding_asset_model ON public.branding_assets USING btree (model_id);


--
-- Name: idx_branding_asset_type; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_branding_asset_type ON public.branding_assets USING btree (asset_type);


--
-- Name: idx_branding_asset_unique_active; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE UNIQUE INDEX idx_branding_asset_unique_active ON public.branding_assets USING btree (agency_id, model_id, asset_type, is_active) WHERE (is_active = true);


--
-- Name: idx_category_performance_category; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_category_performance_category ON public.category_performance USING btree (category_name);


--
-- Name: idx_category_performance_model; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_category_performance_model ON public.category_performance USING btree (model_id, period_start);


--
-- Name: idx_chat_messages_created; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_chat_messages_created ON public.chat_messages USING btree (created_at);


--
-- Name: idx_chat_messages_fan; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_chat_messages_fan ON public.chat_messages USING btree (fan_id);


--
-- Name: idx_chat_messages_model; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_chat_messages_model ON public.chat_messages USING btree (model_id);


--
-- Name: idx_commission_rules_agency; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_commission_rules_agency ON public.commission_rules USING btree (agency_id);


--
-- Name: idx_content_performance_model; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_content_performance_model ON public.content_performance USING btree (model_id);


--
-- Name: idx_content_performance_published; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_content_performance_published ON public.content_performance USING btree (published_at);


--
-- Name: idx_content_performance_type; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_content_performance_type ON public.content_performance USING btree (content_type);


--
-- Name: idx_crypto_wallet_default; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE UNIQUE INDEX idx_crypto_wallet_default ON public.crypto_wallets USING btree (user_id, network, is_default) WHERE (is_default = true);


--
-- Name: idx_crypto_wallet_network; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_crypto_wallet_network ON public.crypto_wallets USING btree (network);


--
-- Name: idx_crypto_wallet_user; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_crypto_wallet_user ON public.crypto_wallets USING btree (user_id);


--
-- Name: idx_email_template_agency; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_email_template_agency ON public.email_templates USING btree (agency_id);


--
-- Name: idx_email_template_language; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_email_template_language ON public.email_templates USING btree (language);


--
-- Name: idx_email_template_type; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_email_template_type ON public.email_templates USING btree (template_type);


--
-- Name: idx_email_template_unique_active; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE UNIQUE INDEX idx_email_template_unique_active ON public.email_templates USING btree (agency_id, template_type, language, is_active) WHERE (is_active = true);


--
-- Name: idx_fan_spending_history_fan; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_fan_spending_history_fan ON public.fan_spending_history USING btree (fan_id, period_start);


--
-- Name: idx_fan_spending_history_model; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_fan_spending_history_model ON public.fan_spending_history USING btree (model_id, period_start);


--
-- Name: idx_financial_transactions_agency; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_financial_transactions_agency ON public.financial_transactions USING btree (agency_id);


--
-- Name: idx_financial_transactions_created; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_financial_transactions_created ON public.financial_transactions USING btree (created_at);


--
-- Name: idx_financial_transactions_model; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_financial_transactions_model ON public.financial_transactions USING btree (model_id);


--
-- Name: idx_invoice_agency; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_invoice_agency ON public.invoices USING btree (agency_id);


--
-- Name: idx_invoice_due_date; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_invoice_due_date ON public.invoices USING btree (due_date);


--
-- Name: idx_invoice_model; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_invoice_model ON public.invoices USING btree (model_id);


--
-- Name: idx_invoice_status; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_invoice_status ON public.invoices USING btree (status);


--
-- Name: idx_metric_snapshot_model_timestamp; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_metric_snapshot_model_timestamp ON public.metric_snapshots USING btree (model_id, "timestamp");


--
-- Name: idx_model_assignments_active; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_model_assignments_active ON public.model_assignments USING btree (is_active);


--
-- Name: idx_model_assignments_agency; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_model_assignments_agency ON public.model_assignments USING btree (agency_id);


--
-- Name: idx_model_assignments_chatter; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_model_assignments_chatter ON public.model_assignments USING btree (chatter_id);


--
-- Name: idx_model_assignments_model; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_model_assignments_model ON public.model_assignments USING btree (model_id);


--
-- Name: idx_model_branding_model; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_model_branding_model ON public.model_branding USING btree (model_id);


--
-- Name: idx_payment_gateway_config_agency; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_payment_gateway_config_agency ON public.payment_gateway_configs USING btree (agency_id);


--
-- Name: idx_payment_gateway_config_provider; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_payment_gateway_config_provider ON public.payment_gateway_configs USING btree (provider);


--
-- Name: idx_payout_cycle; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_payout_cycle ON public.payouts USING btree (billing_cycle_id);


--
-- Name: idx_payout_recipient; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_payout_recipient ON public.payouts USING btree (recipient_id);


--
-- Name: idx_payout_status; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_payout_status ON public.payouts USING btree (status);


--
-- Name: idx_revenue_transaction_fan; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_revenue_transaction_fan ON public.revenue_transactions USING btree (fan_id, transaction_date);


--
-- Name: idx_revenue_transaction_model_date; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_revenue_transaction_model_date ON public.revenue_transactions USING btree (model_id, transaction_date);


--
-- Name: idx_theme_preset_category; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_theme_preset_category ON public.theme_presets USING btree (category);


--
-- Name: idx_theme_preset_name; Type: INDEX; Schema: public; Owner: mariuszbudzisz
--

CREATE INDEX idx_theme_preset_name ON public.theme_presets USING btree (name);


--
-- Name: ix_audit_logs_agency_id; Type: INDEX; Schema: public; Owner: agencydark
--

CREATE INDEX ix_audit_logs_agency_id ON public.audit_logs USING btree (agency_id);


--
-- Name: ix_audit_logs_created_at; Type: INDEX; Schema: public; Owner: agencydark
--

CREATE INDEX ix_audit_logs_created_at ON public.audit_logs USING btree (created_at);


--
-- Name: ix_audit_logs_user_id; Type: INDEX; Schema: public; Owner: agencydark
--

CREATE INDEX ix_audit_logs_user_id ON public.audit_logs USING btree (user_id);


--
-- Name: ix_fans_model_id; Type: INDEX; Schema: public; Owner: agencydark
--

CREATE INDEX ix_fans_model_id ON public.fans USING btree (model_id);


--
-- Name: ix_model_profiles_agency_id; Type: INDEX; Schema: public; Owner: agencydark
--

CREATE INDEX ix_model_profiles_agency_id ON public.model_profiles USING btree (agency_id);


--
-- Name: ix_notifications_agency_id; Type: INDEX; Schema: public; Owner: agencydark
--

CREATE INDEX ix_notifications_agency_id ON public.notifications USING btree (agency_id);


--
-- Name: ix_notifications_user_id; Type: INDEX; Schema: public; Owner: agencydark
--

CREATE INDEX ix_notifications_user_id ON public.notifications USING btree (user_id);


--
-- Name: ix_sessions_user_id; Type: INDEX; Schema: public; Owner: agencydark
--

CREATE INDEX ix_sessions_user_id ON public.sessions USING btree (user_id);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: agencydark
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: chat_messages chat_messages_assigned_chatter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_assigned_chatter_id_fkey FOREIGN KEY (assigned_chatter_id) REFERENCES public.users(id);


--
-- Name: chat_messages chat_messages_model_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_model_id_fkey FOREIGN KEY (model_id) REFERENCES public.model_profiles(id) ON DELETE CASCADE;


--
-- Name: commission_rules commission_rules_agency_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.commission_rules
    ADD CONSTRAINT commission_rules_agency_id_fkey FOREIGN KEY (agency_id) REFERENCES public.agencies(id) ON DELETE CASCADE;


--
-- Name: financial_transactions financial_transactions_agency_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.financial_transactions
    ADD CONSTRAINT financial_transactions_agency_id_fkey FOREIGN KEY (agency_id) REFERENCES public.agencies(id) ON DELETE CASCADE;


--
-- Name: financial_transactions financial_transactions_model_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.financial_transactions
    ADD CONSTRAINT financial_transactions_model_id_fkey FOREIGN KEY (model_id) REFERENCES public.model_profiles(id) ON DELETE CASCADE;


--
-- Name: agency_profiles fk_agency_profiles_agency_id_agencies; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.agency_profiles
    ADD CONSTRAINT fk_agency_profiles_agency_id_agencies FOREIGN KEY (agency_id) REFERENCES public.agencies(id);


--
-- Name: audit_logs fk_audit_logs_agency_id_agencies; Type: FK CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT fk_audit_logs_agency_id_agencies FOREIGN KEY (agency_id) REFERENCES public.agencies(id) ON DELETE CASCADE;


--
-- Name: audit_logs fk_audit_logs_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT fk_audit_logs_user_id_users FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: billing_cycles fk_billing_cycles_agency_id_agencies; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.billing_cycles
    ADD CONSTRAINT fk_billing_cycles_agency_id_agencies FOREIGN KEY (agency_id) REFERENCES public.agencies(id);


--
-- Name: billing_cycles fk_billing_cycles_closed_by_users; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.billing_cycles
    ADD CONSTRAINT fk_billing_cycles_closed_by_users FOREIGN KEY (closed_by) REFERENCES public.users(id);


--
-- Name: branding_assets fk_branding_assets_agency_id_agencies; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.branding_assets
    ADD CONSTRAINT fk_branding_assets_agency_id_agencies FOREIGN KEY (agency_id) REFERENCES public.agencies(id);


--
-- Name: branding_assets fk_branding_assets_model_id_model_profiles; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.branding_assets
    ADD CONSTRAINT fk_branding_assets_model_id_model_profiles FOREIGN KEY (model_id) REFERENCES public.model_profiles(id);


--
-- Name: branding_assets fk_branding_assets_uploaded_by_users; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.branding_assets
    ADD CONSTRAINT fk_branding_assets_uploaded_by_users FOREIGN KEY (uploaded_by) REFERENCES public.users(id);


--
-- Name: category_performance fk_category_performance_model_id_model_profiles; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.category_performance
    ADD CONSTRAINT fk_category_performance_model_id_model_profiles FOREIGN KEY (model_id) REFERENCES public.model_profiles(id);


--
-- Name: content_performance fk_content_performance_model_id_model_profiles; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.content_performance
    ADD CONSTRAINT fk_content_performance_model_id_model_profiles FOREIGN KEY (model_id) REFERENCES public.model_profiles(id);


--
-- Name: crypto_wallets fk_crypto_wallets_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.crypto_wallets
    ADD CONSTRAINT fk_crypto_wallets_user_id_users FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: email_templates fk_email_templates_agency_id_agencies; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.email_templates
    ADD CONSTRAINT fk_email_templates_agency_id_agencies FOREIGN KEY (agency_id) REFERENCES public.agencies(id);


--
-- Name: email_templates fk_email_templates_updated_by_users; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.email_templates
    ADD CONSTRAINT fk_email_templates_updated_by_users FOREIGN KEY (updated_by) REFERENCES public.users(id);


--
-- Name: fan_claims fk_fan_claims_chatter_id_users; Type: FK CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.fan_claims
    ADD CONSTRAINT fk_fan_claims_chatter_id_users FOREIGN KEY (chatter_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: fan_claims fk_fan_claims_fan_id_fans; Type: FK CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.fan_claims
    ADD CONSTRAINT fk_fan_claims_fan_id_fans FOREIGN KEY (fan_id) REFERENCES public.fans(id) ON DELETE CASCADE;


--
-- Name: fan_claims fk_fan_claims_model_id_model_profiles; Type: FK CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.fan_claims
    ADD CONSTRAINT fk_fan_claims_model_id_model_profiles FOREIGN KEY (model_id) REFERENCES public.model_profiles(id) ON DELETE CASCADE;


--
-- Name: fan_claims fk_fan_claims_released_by_id_users; Type: FK CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.fan_claims
    ADD CONSTRAINT fk_fan_claims_released_by_id_users FOREIGN KEY (released_by_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: fan_spending_history fk_fan_spending_history_fan_id_fans; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.fan_spending_history
    ADD CONSTRAINT fk_fan_spending_history_fan_id_fans FOREIGN KEY (fan_id) REFERENCES public.fans(id);


--
-- Name: fan_spending_history fk_fan_spending_history_model_id_model_profiles; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.fan_spending_history
    ADD CONSTRAINT fk_fan_spending_history_model_id_model_profiles FOREIGN KEY (model_id) REFERENCES public.model_profiles(id);


--
-- Name: fans fk_fans_model_id_model_profiles; Type: FK CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.fans
    ADD CONSTRAINT fk_fans_model_id_model_profiles FOREIGN KEY (model_id) REFERENCES public.model_profiles(id) ON DELETE CASCADE;


--
-- Name: invoices fk_invoices_agency_id_agencies; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT fk_invoices_agency_id_agencies FOREIGN KEY (agency_id) REFERENCES public.agencies(id);


--
-- Name: invoices fk_invoices_billing_cycle_id_billing_cycles; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT fk_invoices_billing_cycle_id_billing_cycles FOREIGN KEY (billing_cycle_id) REFERENCES public.billing_cycles(id);


--
-- Name: invoices fk_invoices_model_id_model_profiles; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT fk_invoices_model_id_model_profiles FOREIGN KEY (model_id) REFERENCES public.model_profiles(id);


--
-- Name: metric_snapshots fk_metric_snapshots_model_id_model_profiles; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.metric_snapshots
    ADD CONSTRAINT fk_metric_snapshots_model_id_model_profiles FOREIGN KEY (model_id) REFERENCES public.model_profiles(id);


--
-- Name: model_branding fk_model_branding_model_id_model_profiles; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.model_branding
    ADD CONSTRAINT fk_model_branding_model_id_model_profiles FOREIGN KEY (model_id) REFERENCES public.model_profiles(id);


--
-- Name: model_chatters fk_model_chatters_chatter_id_users; Type: FK CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.model_chatters
    ADD CONSTRAINT fk_model_chatters_chatter_id_users FOREIGN KEY (chatter_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: model_chatters fk_model_chatters_model_id_model_profiles; Type: FK CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.model_chatters
    ADD CONSTRAINT fk_model_chatters_model_id_model_profiles FOREIGN KEY (model_id) REFERENCES public.model_profiles(id) ON DELETE CASCADE;


--
-- Name: model_profiles fk_model_profiles_agency_id_agencies; Type: FK CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.model_profiles
    ADD CONSTRAINT fk_model_profiles_agency_id_agencies FOREIGN KEY (agency_id) REFERENCES public.agencies(id) ON DELETE CASCADE;


--
-- Name: model_profiles fk_model_profiles_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.model_profiles
    ADD CONSTRAINT fk_model_profiles_user_id_users FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: notifications fk_notifications_agency_id_agencies; Type: FK CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT fk_notifications_agency_id_agencies FOREIGN KEY (agency_id) REFERENCES public.agencies(id) ON DELETE CASCADE;


--
-- Name: notifications fk_notifications_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT fk_notifications_user_id_users FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: payment_gateway_configs fk_payment_gateway_configs_agency_id_agencies; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.payment_gateway_configs
    ADD CONSTRAINT fk_payment_gateway_configs_agency_id_agencies FOREIGN KEY (agency_id) REFERENCES public.agencies(id);


--
-- Name: payouts fk_payouts_billing_cycle_id_billing_cycles; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.payouts
    ADD CONSTRAINT fk_payouts_billing_cycle_id_billing_cycles FOREIGN KEY (billing_cycle_id) REFERENCES public.billing_cycles(id);


--
-- Name: payouts fk_payouts_recipient_id_users; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.payouts
    ADD CONSTRAINT fk_payouts_recipient_id_users FOREIGN KEY (recipient_id) REFERENCES public.users(id);


--
-- Name: revenue_transactions fk_revenue_transactions_fan_id_fans; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.revenue_transactions
    ADD CONSTRAINT fk_revenue_transactions_fan_id_fans FOREIGN KEY (fan_id) REFERENCES public.fans(id);


--
-- Name: revenue_transactions fk_revenue_transactions_model_id_model_profiles; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.revenue_transactions
    ADD CONSTRAINT fk_revenue_transactions_model_id_model_profiles FOREIGN KEY (model_id) REFERENCES public.model_profiles(id);


--
-- Name: sessions fk_sessions_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT fk_sessions_user_id_users FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: theme_presets fk_theme_presets_created_by_users; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.theme_presets
    ADD CONSTRAINT fk_theme_presets_created_by_users FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: users fk_users_agency_id_agencies; Type: FK CONSTRAINT; Schema: public; Owner: agencydark
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT fk_users_agency_id_agencies FOREIGN KEY (agency_id) REFERENCES public.agencies(id) ON DELETE CASCADE;


--
-- Name: model_assignments model_assignments_agency_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.model_assignments
    ADD CONSTRAINT model_assignments_agency_id_fkey FOREIGN KEY (agency_id) REFERENCES public.agencies(id);


--
-- Name: model_assignments model_assignments_assigned_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.model_assignments
    ADD CONSTRAINT model_assignments_assigned_by_fkey FOREIGN KEY (assigned_by) REFERENCES public.users(id);


--
-- Name: model_assignments model_assignments_chatter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.model_assignments
    ADD CONSTRAINT model_assignments_chatter_id_fkey FOREIGN KEY (chatter_id) REFERENCES public.users(id);


--
-- Name: model_assignments model_assignments_model_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.model_assignments
    ADD CONSTRAINT model_assignments_model_id_fkey FOREIGN KEY (model_id) REFERENCES public.users(id);


--
-- Name: theme_configurations theme_configurations_agency_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.theme_configurations
    ADD CONSTRAINT theme_configurations_agency_id_fkey FOREIGN KEY (agency_id) REFERENCES public.agencies(id) ON DELETE CASCADE;


--
-- Name: theme_configurations theme_configurations_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: mariuszbudzisz
--

ALTER TABLE ONLY public.theme_configurations
    ADD CONSTRAINT theme_configurations_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.users(id);


--
-- PostgreSQL database dump complete
--

