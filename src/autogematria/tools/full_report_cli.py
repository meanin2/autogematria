"""CLI for generating comprehensive name analysis reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from autogematria.research.html_export import prepare_showcase_payload
from autogematria.research.html_report import render_full_report_html
from autogematria.research.name_report import build_name_report
from autogematria.tools.tool_functions import showcase_name


def generate_full_report(
    query: str,
    *,
    output_dir: str = "/tmp/autogematria_report",
) -> dict:
    """Generate a comprehensive name analysis report.

    Combines:
      - Structured name parsing
      - Per-component kabbalistic analysis
      - Cross-comparison gematria table
      - Torah text/ELS/acrostic findings
    """
    report = build_name_report(query)

    showcase_raw = showcase_name(report["full_hebrew_name"])
    prepared = prepare_showcase_payload(showcase_raw)
    showcase = prepared.get("showcase", {})

    html = render_full_report_html(report, showcase=showcase)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    html_path = out / "index.html"
    html_path.write_text(html, encoding="utf-8")
    json_path = out / "report.json"
    json_path.write_text(
        json.dumps({
            "report": {k: v for k, v in report.items()
                       if k != "kabbalistic_per_component"},
            "showcase_verdict": showcase.get("verdict_label"),
        }, ensure_ascii=False, default=str, indent=2),
        encoding="utf-8",
    )

    return {
        "html_path": str(html_path),
        "json_path": str(json_path),
        "html_size": html_path.stat().st_size,
        "full_hebrew_name": report["full_hebrew_name"],
        "full_name_gematria": report["full_name_gematria"],
        "components": len(report["hebrew_components"]),
        "cross_matches": report["cross_comparison"]["summary"]["total_cross_matches"],
        "verdict": showcase.get("verdict_label", ""),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ag-full-report",
        description="Generate a comprehensive name analysis report",
    )
    parser.add_argument("query", help="Name in Hebrew or English (e.g. 'moshe ben yitzchak gindi')")
    parser.add_argument("--output", default="/tmp/autogematria_report", help="Output directory")
    parser.add_argument("--publish", action="store_true", help="Publish to here.now")
    parser.add_argument("--json", action="store_true", help="Output JSON result")
    args = parser.parse_args()

    result = generate_full_report(args.query, output_dir=args.output)

    if args.publish:
        try:
            from autogematria.publish.herenow import publish_directory
            pub = publish_directory(
                args.output,
                viewer_title=f"{result['full_hebrew_name']} · Name Analysis",
                viewer_description="AutoGematria comprehensive name analysis report",
            )
            result["url"] = pub.get("site_url")
        except Exception as e:
            result["publish_error"] = str(e)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Name: {result['full_hebrew_name']}")
        print(f"Gematria: {result['full_name_gematria']}")
        print(f"Components: {result['components']}")
        print(f"Cross-matches: {result['cross_matches']}")
        print(f"Torah verdict: {result['verdict']}")
        print(f"\nReport: {result['html_path']} ({result['html_size']:,} bytes)")
        if result.get("url"):
            print(f"Published: {result['url']}")


if __name__ == "__main__":
    main()
