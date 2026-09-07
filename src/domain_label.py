"""
ILSC — domain labeller (v2, cleaned).

Purpose: assign each service a coarse domain tag. Required by
  - the same-domain perturbation control (Exp. 2)
  - the domain-restricted null model (Sec. 6)

Design constraint: this labeller must stay INDEPENDENT of the metric it helps
validate. It therefore does deterministic keyword matching on the title and
provider only -- no embeddings, no language model. Its crudeness is the point:
agreement between a lexical labeller and a semantic metric carries evidential
weight precisely because the two are built on different principles.

v1 -> v2 changes (diagnosed on a 20-service manual sample, 60% accuracy):
  - removed generic keywords that matched almost everything:
      devtools: api, sdk, developer, cloud, server, test, code
      data:     data, ml, ai, report, search, index
      identity: user, account
    ("api" alone mislabelled all 39 apisetu.gov.in government services;
     "cloud" mislabelled Big Red Cloud, an accounting product.)
  - a label is assigned only when the winning domain STRICTLY beats the
    runner-up; ties become UNLABELLED.
  - provider-domain overrides for known hosts, applied before keywords.
  - UNLABELLED is a legitimate outcome: unlabelled services are excluded from
    the control condition and the domain-restricted null model, which is far
    safer than a confident wrong label.
"""

import csv
import re

# Provider-level overrides. A provider whose entire catalogue sits in one
# domain is more reliable evidence than any word in an individual title.
PROVIDER_DOMAIN = {
    "amazonaws.com": "devtools",
    "googleapis.com": "devtools",
    "azure.com": "devtools",
    "kubernetes.io": "devtools",
    "github.com": "devtools",
    "docker.com": "devtools",
    "gitlab.com": "devtools",
    "atlassian.com": "devtools",
    "apisetu.gov.in": "government",
    "parliament.uk": "government",
    "gov.bc.ca": "government",
    "twilio.com": "communication",
    "nexmo.com": "communication",
    "sendgrid.com": "communication",
    "mailchimp.com": "communication",
    "adyen.com": "finance",
    "stripe.com": "finance",
    "plaid.com": "finance",
    "vtex.local": "commerce",
    "shopify.com": "commerce",
    "ebay.com": "commerce",
    "sportsdata.io": "media",
    "spotify.com": "media",
}

# High-precision keywords only. Every entry here must be a word that would
# rarely appear in a service outside its domain.
DOMAIN_KEYWORDS = {
    "finance": ["bank", "banking", "payment", "invoice", "billing", "trading",
                "stock", "crypto", "currency", "tax", "accounting", "loan",
                "credit card", "wallet", "finance", "financial", "payroll",
                "insurance", "mortgage", "ledger", "checkout", "refund",
                "transaction", "exchange rate", "brokerage", "fintech"],
    "travel": ["flight", "airline", "airport", "hotel", "booking", "travel",
               "trip", "railway", "transit", "car rental", "cruise", "tourism",
               "itinerary", "lodging", "reservation", "destination"],
    "health": ["health", "medical", "clinic", "patient", "pharmacy", "pharma",
               "drug", "fhir", "hospital", "diagnosis", "genome", "covid",
               "fitness", "nutrition", "therapy", "dental", "vaccine"],
    "geo": ["map", "maps", "geocod", "geospatial", "location", "postcode",
            "zipcode", "weather", "forecast", "route", "navigation",
            "satellite", "climate", "coordinates", "elevation", "timezone"],
    "social": ["social network", "chat", "messaging", "twitter", "facebook",
               "instagram", "forum", "community", "follower", "feed", "post"],
    "commerce": ["shop", "shopping", "cart", "order", "product catalog",
                 "catalogue", "ecommerce", "e-commerce", "retail", "store",
                 "inventory", "shipping", "delivery", "merchant", "pricing",
                 "warehouse", "fulfillment", "coupon", "discount"],
    "devtools": ["kubernetes", "container", "deployment", "repository",
                 "continuous integration", "pipeline", "webhook", "monitoring",
                 "observability", "logging", "infrastructure", "provisioning",
                 "compute", "serverless", "devops", "firewall", "vpc",
                 "load balancer", "cluster", "runtime", "compiler", "debug"],
    "media": ["video", "audio", "music", "image", "photo", "streaming", "film",
              "movie", "podcast", "news", "book", "publishing", "broadcast",
              "sports", "game", "entertainment", "player", "playlist"],
    "identity": ["authentication", "authorization", "identity", "login",
                 "oauth", "sso", "single sign", "permission", "role",
                 "directory service", "credential", "password", "token"],
    "communication": ["email", "sms", "voice call", "telephony", "notification",
                      "push notification", "contact center", "conferencing",
                      "messaging service", "mms", "whatsapp"],
    "data": ["analytics", "statistic", "dashboard", "business intelligence",
             "data warehouse", "machine learning", "recommendation",
             "prediction", "dataset", "etl", "query engine", "metrics"],
    "government": ["government", "egovernance", "census", "public sector",
                   "legal", "court", "regulation", "election", "municipal",
                   "ministry", "parliament", "civic", "citizen"],
}


def label(title, provider, description=""):
    """Return (domain, evidence). evidence explains the decision for the audit
    trail -- every label must be defensible in one line."""
    prov = (provider or "").lower().strip()
    if prov in PROVIDER_DOMAIN:
        return PROVIDER_DOMAIN[prov], f"provider_override:{prov}"

    text = f"{title} {provider} {description[:300]}".lower()

    hits = {}
    for domain, kws in DOMAIN_KEYWORDS.items():
        matched = [kw for kw in kws if kw in text]
        if matched:
            hits[domain] = matched

    if not hits:
        return "UNLABELLED", "no_keyword_match"

    ranked = sorted(hits.items(), key=lambda kv: -len(kv[1]))
    top_domain, top_kws = ranked[0]

    # Strict win required: a tie means the evidence is genuinely ambiguous.
    if len(ranked) > 1 and len(ranked[1][1]) == len(top_kws):
        tied = ranked[0][0] + "/" + ranked[1][0]
        return "UNLABELLED", f"tie:{tied}"

    return top_domain, "keywords:" + ",".join(top_kws[:3])


def relabel_manifest(path_in, path_out):
    rows = list(csv.DictReader(open(path_in, encoding="utf-8")))
    for r in rows:
        dom, ev = label(r.get("title", ""), r.get("provider", ""))
        r["domain"] = dom
        r["domain_evidence"] = ev
    fields = list(rows[0].keys())
    with open(path_out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return rows


def main(argv=None):
    import argparse
    import collections
    import os
    import sys

    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, _root)
    import config                               # noqa: E402

    ap = argparse.ArgumentParser(
        description="ILSC coarse domain labeller (REJECTED, see DECISIONS.md D-03).")
    ap.add_argument("--manifest", default=os.path.join(config.RESULTS_DIR, "manifest.csv"))
    ap.add_argument("--out", default=os.path.join(config.RESULTS_DIR,
                                                  "manifest_labelled.csv"))
    args = ap.parse_args(argv)

    rows = relabel_manifest(args.manifest, args.out)
    c = collections.Counter(r["domain"] for r in rows)
    total = len(rows)
    for k, v in c.most_common():
        print("  %-15s %5d  (%5.1f%%)" % (k, v, v / total * 100))
    print("\nwritten: %s" % args.out)
    print("NOTE: these labels are inert. D-03 rejected them at 52%% agreement;")
    print("      the perturbation control uses provider proximity instead (D-05).")


if __name__ == "__main__":
    main()
