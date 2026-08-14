#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import re
from pathlib import Path


REQUIRED_TEMPLATE_FIELDS = {
    "id",
    "name",
    "issuer",
    "annualFee",
    "foreignTransactionFee",
    "sourceURL",
    "lastReviewedAt",
    "needsReview",
    "notes",
    "benefits",
    "recommendationRules",
}

REQUIRED_BENEFIT_FIELDS = {
    "id",
    "name",
    "category",
    "resetFrequency",
    "valueType",
    "totalValue",
    "rulesText",
}

REQUIRED_RULE_FIELDS = {
    "category",
    "multiplier",
    "estimatedPointValue",
    "reason",
    "hasProtection",
}

ALLOWED_CATEGORIES = {
    "Dining",
    "Grocery",
    "Gas",
    "Flights",
    "Hotels",
    "Travel",
    "Rideshare",
    "Transit",
    "Online",
    "Shopping",
    "Entertainment",
    "Rotating",
    "Rent",
    "Amazon",
    "Costco",
    "Drugstores",
    "International",
    "General",
}


def fail(message):
    print(f"catalog validation failed: {message}", file=sys.stderr)
    sys.exit(1)


def require_fields(label, item, fields):
    missing = sorted(fields - item.keys())
    if missing:
        fail(f"{label} missing required fields: {', '.join(missing)}")


def main():
    parser = argparse.ArgumentParser(description="Validate Smart Credit Cards catalog JSON.")
    parser.add_argument("path", nargs="?", default="SmartCreditCards/card_templates.json")
    parser.add_argument("--against", help="git ref whose catalog version must be lower")
    args = parser.parse_args()

    catalog_path = Path(args.path)
    if not catalog_path.exists():
        fail(f"{catalog_path} does not exist")

    with catalog_path.open() as file:
        catalog = json.load(file)

    if not isinstance(catalog.get("version"), int):
        fail("version must be an integer")
    min_app_version = catalog.get("minAppVersion")
    if min_app_version is not None and (
        not isinstance(min_app_version, str)
        or re.fullmatch(r"\d+\.\d+\.\d+", min_app_version) is None
    ):
        fail("minAppVersion must use semantic version format MAJOR.MINOR.PATCH")
    if not catalog.get("updatedAt"):
        fail("updatedAt is required")
    if args.against:
        try:
            blob = subprocess.run(
                ["git", "show", f"{args.against}:{catalog_path.as_posix()}"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            old_catalog = json.loads(blob)
            old_version = old_catalog.get("version")
            if isinstance(old_version, int) and catalog["version"] <= old_version:
                fail(f"version {catalog['version']} must be greater than {args.against} version {old_version}")
        except subprocess.CalledProcessError:
            print(f"note: {args.against} has no {catalog_path}; skipping version check", file=sys.stderr)

    templates = catalog.get("templates")
    if not isinstance(templates, list) or not templates:
        fail("templates must be a non-empty array")

    template_ids = set()
    for template in templates:
        require_fields("template", template, REQUIRED_TEMPLATE_FIELDS)
        template_id = template["id"]
        if template_id in template_ids:
            fail(f"duplicate template id: {template_id}")
        template_ids.add(template_id)

        benefit_ids = set()
        for benefit in template["benefits"]:
            require_fields(f"benefit in {template_id}", benefit, REQUIRED_BENEFIT_FIELDS)
            benefit_id = benefit["id"]
            category = benefit["category"]
            if category not in ALLOWED_CATEGORIES:
                fail(f"unknown benefit category in {template_id}: {category}")
            if benefit_id in benefit_ids:
                fail(f"duplicate benefit id in {template_id}: {benefit_id}")
            benefit_ids.add(benefit_id)
            for flag in ("showOnDashboard", "isActive"):
                if flag in benefit and not isinstance(benefit[flag], bool):
                    fail(f"{flag} must be boolean in benefit {benefit_id}")

        rule_categories = set()
        for rule in template["recommendationRules"]:
            require_fields(f"rule in {template_id}", rule, REQUIRED_RULE_FIELDS)
            category = rule["category"]
            if category not in ALLOWED_CATEGORIES:
                fail(f"unknown recommendation category in {template_id}: {category}")
            if category in rule_categories:
                fail(f"duplicate recommendation category in {template_id}: {category}")
            rule_categories.add(category)

    print(f"catalog ok: version {catalog['version']}, {len(templates)} templates")


if __name__ == "__main__":
    main()
