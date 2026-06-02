"""
utils/report.py — Port of buildHtmlReport / buildJsonApiReport from utils/report.js
"""

import json
from datetime import datetime, timezone


def build_html_report(site_info: dict, step_results: list, api_responses: list) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_pass = sum(s.get("passed", 0) for s in step_results)
    total_fail = sum(s.get("failed", 0) for s in step_results)
    total_warn = sum(s.get("warned", 0) for s in step_results)

    icon  = {"pass": "✓", "fail": "✗", "warn": "⚠", "info": "•"}
    color = {"pass": "#22c55e", "fail": "#ef4444", "warn": "#f59e0b", "info": "#3b82f6"}

    def esc(s):
        return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def badge(status):
        c = color.get(status, "#6b7280")
        i = icon.get(status, "•")
        return f'<span style="display:inline-block;min-width:20px;padding:1px 6px;border-radius:4px;background:{c};color:#fff;font-size:11px;font-weight:600;">{i}</span>'

    step_html_parts = []
    for step in step_results:
        rows = "".join(
            f'<tr><td style="width:30px;padding:4px 8px;">{badge(d.get("status","info"))}</td>'
            f'<td style="padding:4px 8px;font-weight:600;color:#374151;">{esc(d.get("title",""))}</td>'
            f'<td style="padding:4px 8px;color:#6b7280;font-size:12px;">{esc(d.get("detail",""))}</td>'
            f'<td style="padding:4px 8px;color:#9ca3af;font-size:11px;white-space:nowrap;">{d.get("timestamp","")}</td></tr>'
            for d in (step.get("details") or [])
        )
        sc = "#ef4444" if step.get("failed", 0) > 0 else "#f59e0b" if step.get("warned", 0) > 0 else "#22c55e"
        step_html_parts.append(
            f'<div style="margin-bottom:20px;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">'
            f'<div style="padding:10px 16px;background:#f9fafb;border-bottom:1px solid #e5e7eb;display:flex;justify-content:space-between;align-items:center;">'
            f'<strong style="color:#111827;">{esc(step.get("name",""))}</strong>'
            f'<span style="font-size:12px;color:{sc};font-weight:600;">✓ {step.get("passed",0)} &nbsp;✗ {step.get("failed",0)} &nbsp;⚠ {step.get("warned",0)}</span>'
            f'</div><table style="width:100%;border-collapse:collapse;font-size:13px;"><tbody>{rows}</tbody></table></div>'
        )

    step_html = "".join(step_html_parts)

    api_html = ""
    if api_responses:
        api_rows = "".join(
            f'<div style="margin-bottom:12px;padding:10px;background:#f3f4f6;border-radius:6px;font-size:12px;">'
            f'<div style="font-weight:600;margin-bottom:4px;">{esc(r.get("action",""))} — {esc(r.get("pms_name",""))}</div>'
            f'<div style="color:#6b7280;margin-bottom:4px;">{r.get("timestamp","")}</div>'
            f'<pre style="margin:0;overflow:auto;font-size:11px;">{esc(json.dumps(r.get("response",""), indent=2))}</pre>'
            f'</div>'
            for r in api_responses
        )
        api_html = (
            f'<div style="margin-bottom:20px;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">'
            f'<div style="padding:10px 16px;background:#f9fafb;border-bottom:1px solid #e5e7eb;">'
            f'<strong>API Responses (Sync Calls)</strong></div>'
            f'<div style="padding:12px 16px;">{api_rows}</div></div>'
        )

    ver_map = {"3.5": "#6366f1", "3.0": "#0ea5e9", "2.0": "#f59e0b", "Light": "#6b7280"}
    ver = site_info.get("site_version", "Unknown")
    active_pms = site_info.get("active_pms", [])
    pms_badge = (
        f'<div style="margin-bottom:20px;padding:12px 16px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;font-size:13px;">'
        f'<strong>Active PMS:</strong> {esc(", ".join(active_pms))}</div>'
    ) if active_pms else ""

    bc_ver = site_info.get("boostly_connect_version", "")
    bc_ver_html = f'<div style="font-size:11px;color:#6b7280;margin-top:4px;">Boostly Connect {esc(bc_ver)}</div>' if bc_ver else ""
    duration_str = f" | Duration: {site_info.get('duration', '')}" if site_info.get("duration") else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Boostly QA — {esc(site_info.get("domain",""))}</title>
<style>*{{box-sizing:border-box}}body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:0;padding:24px;background:#f9fafb;color:#111827}}.page{{max-width:960px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;box-shadow:0 1px 4px rgba(0,0,0,.08)}}@media print{{body{{background:#fff;padding:0}}.page{{box-shadow:none;padding:0}}}}</style>
</head>
<body><div class="page">
<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:28px;padding-bottom:20px;border-bottom:2px solid #e5e7eb;">
  <div>
    <h1 style="margin:0 0 4px;font-size:22px;">Boostly API Support Engineer — QA Report</h1>
    <div style="color:#6b7280;font-size:13px;">{esc(site_info.get("url",""))}</div>
    <div style="color:#9ca3af;font-size:12px;margin-top:2px;">Generated: {now}{duration_str}</div>
  </div>
  <div style="text-align:right;">
    <span style="display:inline-block;padding:4px 12px;border-radius:20px;background:{ver_map.get(ver,'#6b7280')};color:#fff;font-size:12px;font-weight:700;">v{esc(ver)} Site</span>
    {bc_ver_html}
  </div>
</div>
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:28px;">
  <div style="padding:16px;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;text-align:center;"><div style="font-size:28px;font-weight:700;color:#16a34a;">{total_pass}</div><div style="font-size:13px;color:#15803d;font-weight:600;">Passed</div></div>
  <div style="padding:16px;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;text-align:center;"><div style="font-size:28px;font-weight:700;color:#dc2626;">{total_fail}</div><div style="font-size:13px;color:#b91c1c;font-weight:600;">Failed</div></div>
  <div style="padding:16px;background:#fffbeb;border:1px solid #fde68a;border-radius:8px;text-align:center;"><div style="font-size:28px;font-weight:700;color:#d97706;">{total_warn}</div><div style="font-size:13px;color:#b45309;font-weight:600;">Warnings</div></div>
</div>
{pms_badge}
{step_html}
{api_html}
<div style="margin-top:24px;padding-top:16px;border-top:1px solid #e5e7eb;font-size:11px;color:#9ca3af;text-align:center;">Boostly API Support Engineer v1.0.0 | Python Agent</div>
</div></body></html>"""


def build_json_report(site_info: dict, step_results: list, api_responses: list) -> dict:
    return {
        "generated":    datetime.now(timezone.utc).isoformat(),
        "site":         site_info.get("url"),
        "domain":       site_info.get("domain"),
        "site_version": site_info.get("site_version"),
        "active_pms":   site_info.get("active_pms", []),
        "duration":     site_info.get("duration"),
        "summary": {
            "passed":   sum(s.get("passed", 0) for s in step_results),
            "failed":   sum(s.get("failed", 0) for s in step_results),
            "warnings": sum(s.get("warned", 0) for s in step_results),
            "total":    sum(s.get("passed", 0) + s.get("failed", 0) + s.get("warned", 0) for s in step_results),
        },
        "step_results":   step_results,
        "api_responses":  api_responses,
    }
