"""
CTT Criar Lojas Online — Intercom Data Fetcher
Runs as a GitHub Action. Outputs data.json to project root.

Requires: INTERCOM_TOKEN env var (set as GitHub Secret)
"""

import os, json, time, sys
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError

TOKEN = os.environ.get("INTERCOM_TOKEN", "")
if not TOKEN:
    print("ERROR: INTERCOM_TOKEN not set", file=sys.stderr)
    sys.exit(1)

BASE = "https://api.intercom.io"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}


def get(path, params=None):
    url = BASE + path
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url += "?" + qs
    req = Request(url, headers=HEADERS)
    for attempt in range(3):
        try:
            with urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except URLError as e:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def post(path, body):
    data = json.dumps(body).encode()
    req = Request(BASE + path, data=data, headers=HEADERS, method="POST")
    for attempt in range(3):
        try:
            with urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except URLError as e:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def ts(year, month=1, day=1):
    return int(datetime(year, month, day, tzinfo=timezone.utc).timestamp())


def yr(unix_ts):
    if not unix_ts:
        return None
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc).year


print("Fetching funnel counts...")
total_res  = get("/companies", {"per_page": 1})
total      = total_res.get("total_count", 0)

active_res = get("/companies", {"per_page": 1, "tag_id": "8129912"})
active     = active_res.get("total_count", 0)

payment_res = get("/companies", {"per_page": 1, "tag_id": "9122059"})
first_pay   = payment_res.get("total_count", 0)

print(f"  Total: {total}, Active: {active}, FirstPayment: {first_pay}")

print("Fetching conversation counts by year...")

def conv_year(year):
    body = {
        "query": {
            "operator": "AND",
            "value": [
                {"field": "created_at", "operator": ">", "value": ts(year)},
                {"field": "created_at", "operator": "<", "value": ts(year + 1)},
            ]
        },
        "pagination": {"per_page": 1}
    }
    r = post("/conversations/search", body)
    return r.get("total_count", 0)


def conv_range(year, month_start, month_end_year, month_end):
    body = {
        "query": {
            "operator": "AND",
            "value": [
                {"field": "created_at", "operator": ">",  "value": ts(year, month_start)},
                {"field": "created_at", "operator": "<",  "value": ts(month_end_year, month_end)},
            ]
        },
        "pagination": {"per_page": 1}
    }
    r = post("/conversations/search", body)
    return r.get("total_count", 0)


def open_convs():
    body = {
        "query": {"field": "open", "operator": "=", "value": True},
        "pagination": {"per_page": 20}
    }
    r = post("/conversations/search", body)
    items = r.get("conversations", [])
    previews = []
    for c in items[:8]:
        parts = c.get("conversation_parts", {}).get("conversation_parts", [])
        first_body = ""
        if c.get("source", {}).get("body"):
            import re
            first_body = re.sub(r"<[^>]+>", "", c["source"]["body"])[:120].strip()
        author = c.get("source", {}).get("author", {})
        author_name = author.get("name") or author.get("email") or "—"
        previews.append({
            "id": str(c.get("id", "")),
            "state": "open" if c.get("open") else "snoozed",
            "author": author_name,
            "preview": first_body,
        })
    return r.get("total_count", 0), previews


print("  Counting by year (2020–2026)...")
conv_by_year = {}
for y in range(2020, 2027):
    try:
        conv_by_year[y] = conv_year(y)
        print(f"    {y}: {conv_by_year[y]}")
        time.sleep(0.3)
    except Exception as e:
        print(f"    {y}: ERROR {e}")
        conv_by_year[y] = None

print("  Q1 comparisons...")
q1 = {}
for y in [2024, 2025, 2026]:
    try:
        q1[y] = conv_range(y, 1, y, 4)
        print(f"    Q1 {y}: {q1[y]}")
        time.sleep(0.3)
    except Exception as e:
        print(f"    Q1 {y}: ERROR {e}")
        q1[y] = None

print("  Open conversations...")
open_count, open_list = open_convs()
print(f"  Open: {open_count}")

print("Fetching company samples for cohort analysis...")

def fetch_companies_page(page, per_page=60):
    r = get("/companies", {"page": page, "per_page": per_page})
    return r.get("data", [])

all_companies = []
for page in [1, 10, 20, 30, 40, 50, 66]:
    try:
        cos = fetch_companies_page(page, 60)
        all_companies.extend(cos)
        print(f"  Page {page}: {len(cos)} companies")
        time.sleep(0.4)
    except Exception as e:
        print(f"  Page {page}: ERROR {e}")

# Deduplicate
seen = set()
unique = []
for c in all_companies:
    cid = c.get("company_id")
    if cid and cid not in seen:
        seen.add(cid)
        unique.append(c)
print(f"  Total unique: {len(unique)}")

# Aggregate by registration cohort year
cohorts = {}
plan_counts = {}
industry_counts = {}
top_stores = []

for c in unique:
    ca   = c.get("custom_attributes", {})
    plan = (c.get("plan") or {}).get("name", "Unknown")
    rat  = c.get("remote_created_at", 0)
    ry   = yr(rat)
    if not ry:
        continue

    if ry not in cohorts:
        cohorts[ry] = {
            "count": 0, "gmv": 0, "shipments": 0,
            "monthly_spend": 0, "annual": 0, "trial": 0,
            "custom_domain": 0, "days_to_fp": [],
            "revenue_ctt": 0, "first_payments": 0,
        }
    co = cohorts[ry]
    co["count"]        += 1
    co["gmv"]          += float(ca.get("company_total_paid_orders_revenue") or 0)
    co["shipments"]    += int(ca.get("company_num_shipments") or 0)
    co["monthly_spend"]+= int(c.get("monthly_spend") or 0)
    co["revenue_ctt"]  += float(ca.get("company_lifetime_revenue") or 0)
    if ca.get("company_has_annual_payments"): co["annual"] += 1
    if ca.get("company_is_trial"):            co["trial"]  += 1
    if ca.get("company_custom_domain"):       co["custom_domain"] += 1
    d2p = ca.get("company_days_to_first_payment")
    if d2p and float(d2p) > 0:
        co["days_to_fp"].append(float(d2p))
    if ca.get("company_first_payment_at"):
        co["first_payments"] += 1

    plan_counts[plan]  = plan_counts.get(plan, 0) + 1
    ind = ca.get("company_business") or c.get("industry") or "Outros"
    industry_counts[ind] = industry_counts.get(ind, 0) + 1

    top_stores.append({
        "name":       ca.get("company_store_name") or c.get("name", ""),
        "cohort":     ry,
        "industry":   ind,
        "plan":       plan,
        "revenue_ctt": round(float(ca.get("company_lifetime_revenue") or 0), 2),
        "gmv":        round(float(ca.get("company_total_paid_orders_revenue") or 0), 2),
        "shipments":  int(ca.get("company_num_shipments") or 0),
        "paid_orders":int(ca.get("company_total_paid_orders") or 0),
        "is_annual":  bool(ca.get("company_has_annual_payments")),
        "monthly_spend": int(c.get("monthly_spend") or 0),
    })

# Compute averages and sort
cohort_out = {}
for ry, co in cohorts.items():
    n = co["count"] or 1
    cohort_out[ry] = {
        "count":           co["count"],
        "gmv":             round(co["gmv"], 0),
        "gmv_avg":         round(co["gmv"] / n, 0),
        "shipments":       co["shipments"],
        "monthly_spend_total": co["monthly_spend"],
        "monthly_spend_avg":   round(co["monthly_spend"] / n, 0),
        "revenue_ctt":         round(co["revenue_ctt"], 0),
        "revenue_ctt_avg":     round(co["revenue_ctt"] / n, 0),
        "annual":          co["annual"],
        "annual_rate":     round(co["annual"] / n * 100, 1),
        "custom_domain":   co["custom_domain"],
        "custom_domain_rate": round(co["custom_domain"] / n * 100, 1),
        "first_payments":  co["first_payments"],
        "conversion_rate": round(co["first_payments"] / n * 100, 1),
        "avg_days_to_fp":  round(sum(co["days_to_fp"]) / len(co["days_to_fp"]), 0) if co["days_to_fp"] else None,
    }

top_stores.sort(key=lambda x: x["revenue_ctt"], reverse=True)

# Payment methods (from sample page 1 only — the 60-company set)
pay = {"Cartão Crédito": 0, "MB Way": 0, "Multibanco": 0, "Transferência": 0}
for c in unique[:60]:
    ca = c.get("custom_attributes", {})
    if ca.get("company_payment_method_credit_card_stripe") or ca.get("company_payment_method_credit_card_payshop"):
        pay["Cartão Crédito"] += 1
    if any(ca.get(k) for k in ["company_payment_method_mbway_payshop", "company_payment_method_mbway_easypay", "company_payment_method_mbway_ifthenpay"]):
        pay["MB Way"] += 1
    if any(ca.get(k) for k in ["company_payment_method_multibanco_stripe", "company_payment_method_multibanco_payshop", "company_payment_method_multibanco_easypay", "company_payment_method_multibanco_ifthenpay"]):
        pay["Multibanco"] += 1
    if ca.get("company_payment_method_manual_bank_transfer"):
        pay["Transferência"] += 1

top_industries = dict(sorted(industry_counts.items(), key=lambda x: -x[1])[:10])

now = datetime.now(tz=timezone.utc).isoformat()

output = {
    "generated_at": now,
    "funnel": {
        "total":       total,
        "first_payment": first_pay,
        "active":      active,
        "open_conversations": open_count,
    },
    "open_conversations_list": open_list,
    "conv_by_year": {str(k): v for k, v in conv_by_year.items()},
    "q1_by_year":   {str(k): v for k, v in q1.items()},
    "cohorts":      {str(k): v for k, v in cohort_out.items()},
    "plan_counts":  plan_counts,
    "top_industries": top_industries,
    "payment_methods": pay,
    "top_stores":   top_stores[:15],
    "sample_size":  len(unique),
}

out_path = os.path.join(os.path.dirname(__file__), "..", "data.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\ndata.json written — {len(json.dumps(output))} bytes")
print(f"Generated at: {now}")
