-- Supabase schema for the cloud admin/sync layer.
-- SQLite remains the local runtime database on the device.

create extension if not exists pgcrypto;

create table if not exists public.permit_holders (
    plate_number text primary key,
    lot_id text,
    expiration date not null,
    permit_type text default 'supabase',
    is_active boolean not null default true,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.scan_logs (
    id uuid primary key default gen_random_uuid(),
    plate_number text not null,
    scanned_at timestamptz not null,
    result text not null,
    lot_id text,
    created_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_scan_logs_scanned_at
    on public.scan_logs (scanned_at desc);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = timezone('utc', now());
    return new;
end;
$$;

drop trigger if exists set_permit_holders_updated_at on public.permit_holders;
create trigger set_permit_holders_updated_at
before update on public.permit_holders
for each row
execute function public.set_updated_at();
