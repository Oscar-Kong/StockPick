"""HTML and plain-text templates for morning scan email."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape
from typing import Any

from services.scan_email_comparison import ScanComparison


@dataclass
class BucketEmailSection:
    bucket: str
    label: str
    results: list[dict[str, Any]]
    completed_at: datetime | None
    strategy_version: str | None
    is_stale: bool
    age_label: str
    missing: bool
    warnings: list[str]
    comparison: ScanComparison
    strongest: dict[str, Any] | None


@dataclass
class MorningScanEmailContent:
    subject: str
    html: str
    text: str


def _fmt_score(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "—"


def _fmt_price(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _company_name(row: dict[str, Any]) -> str:
    metrics = row.get("metrics") or {}
    for key in ("company_name", "name", "short_name"):
        val = metrics.get(key)
        if val:
            return str(val)
    return row.get("symbol") or "—"


def _top_signals(row: dict[str, Any], limit: int = 3) -> list[str]:
    signals = row.get("signals") or []
    out: list[str] = []
    for sig in signals[:limit]:
        if isinstance(sig, dict):
            name = sig.get("name") or sig.get("description") or ""
            if name:
                out.append(str(name))
    return out


def _risk_label(row: dict[str, Any]) -> str:
    rl = row.get("risk_level")
    if isinstance(rl, dict):
        return str(rl.get("value") or rl.get("name") or "—")
    return str(rl or "—")


def _rank_change(row: dict[str, Any], prev_ranks: dict[str, int]) -> str:
    sym = str(row.get("symbol") or "").upper()
    metrics = row.get("metrics") or {}
    cur = metrics.get("final_rank")
    prev = prev_ranks.get(sym)
    if cur is None or prev is None:
        return "—"
    delta = prev - int(cur)
    if delta > 0:
        return f"▲{delta}"
    if delta < 0:
        return f"▼{abs(delta)}"
    return "—"


def build_email_subject(
    *,
    market_date_label: str,
    is_stale: bool,
    unavailable: bool,
) -> str:
    if unavailable:
        return f"[Scan Unavailable] StockPick Morning Update — {market_date_label}"
    if is_stale:
        return f"[STALE] StockPick Morning Scan — {market_date_label}"
    return f"StockPick Morning Scan — {market_date_label}"


def build_morning_scan_email(
    *,
    market_date_label: str,
    generated_at_et: str,
    latest_completion_et: str | None,
    freshness_label: str,
    strategy_version: str,
    sections: list[BucketEmailSection],
    public_url: str,
    unavailable: bool,
    partial: bool,
    global_is_stale: bool,
) -> MorningScanEmailContent:
    subject = build_email_subject(
        market_date_label=market_date_label,
        is_stale=global_is_stale,
        unavailable=unavailable,
    )

    scan_url = f"{public_url}/scan"
    penny_url = f"{public_url}/scan?bucket=penny"
    compounder_url = f"{public_url}/scan?bucket=compounder"
    quant_lab_url = f"{public_url}/quant-lab"

    text_lines = [
        "StockPick Morning Scan",
        f"Market date: {market_date_label}",
        f"Generated: {generated_at_et} ET",
        f"Latest scan completed: {latest_completion_et or '—'} ET",
        f"Freshness: {freshness_label}",
        f"Strategy: {strategy_version}",
        "",
        "Research only — not financial advice.",
        "",
        "Executive summary",
    ]

    if unavailable:
        text_lines.append("No completed scan results were available at send time.")
    else:
        for sec in sections:
            if sec.missing:
                text_lines.append(f"- {sec.label}: no results")
                continue
            strongest = sec.strongest or {}
            text_lines.append(
                f"- {sec.label}: {len(sec.results)} candidates"
                f"{' (STALE)' if sec.is_stale else ''}"
                f" — top: {strongest.get('symbol', '—')}"
            )
            for w in sec.warnings:
                text_lines.append(f"  ! {w}")

    text_lines.extend(["", "Top candidates", ""])
    for sec in sections:
        if sec.missing:
            continue
        text_lines.append(f"## {sec.label}")
        prev_ranks = {}
        if sec.comparison and sec.results:
            from services.scan_email_comparison import _rank_map

            prev_ranks = {}  # rank change computed via comparison metadata only in HTML
        for idx, row in enumerate(sec.results):
            sym = row.get("symbol") or "—"
            text_lines.append(
                f"{idx + 1}. {sym} {_company_name(row)} | "
                f"Score {_fmt_score(row.get('score'))} | "
                f"Price {_fmt_price(row.get('price'))} | "
                f"Conf {_fmt_score(row.get('confidence_score'))} | "
                f"Trade {_fmt_score(row.get('tradability_score'))}"
            )
            sigs = _top_signals(row)
            if sigs:
                text_lines.append(f"   Signals: {', '.join(sigs)}")
        text_lines.append("")

    text_lines.extend(
        [
            "Links",
            f"- Open Scan: {scan_url}",
            f"- Penny: {penny_url}",
            f"- Compounder: {compounder_url}",
            f"- Quant Lab: {quant_lab_url}",
            "",
            "StockPick is a research and educational tool. This email is not financial advice.",
        ]
    )

    html_parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        "<style>",
        "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;"
        "background:#0a0a0a;color:#e4e4e7;margin:0;padding:16px;line-height:1.5;}",
        ".card{max-width:640px;margin:0 auto;background:#18181b;border:1px solid #3f3f46;"
        "border-radius:12px;padding:20px;}",
        "h1{font-size:22px;margin:0 0 8px;color:#fafafa;}",
        "h2{font-size:16px;margin:24px 0 8px;color:#a1a1aa;text-transform:uppercase;letter-spacing:.05em;}",
        ".meta{font-size:13px;color:#a1a1aa;}",
        ".badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:600;}",
        ".badge-ok{background:#052e16;color:#4ade80;}",
        ".badge-warn{background:#422006;color:#fbbf24;}",
        ".badge-err{background:#450a0a;color:#f87171;}",
        "table{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px;}",
        "th,td{padding:8px 6px;border-bottom:1px solid #27272a;text-align:left;}",
        "th{color:#71717a;font-weight:600;font-size:11px;text-transform:uppercase;}",
        ".num{text-align:right;font-variant-numeric:tabular-nums;}",
        "a{color:#00c805;text-decoration:none;}",
        ".links a{display:block;margin:4px 0;}",
        ".footer{margin-top:24px;font-size:12px;color:#71717a;}",
        ".warn-box{background:#422006;border:1px solid #78350f;border-radius:8px;padding:12px;margin:12px 0;}",
        "</style></head><body><div class='card'>",
        f"<h1>StockPick Morning Scan</h1>",
        f"<p class='meta'>Market date: {escape(market_date_label)} · Generated {escape(generated_at_et)} ET</p>",
        f"<p class='meta'>Latest completion: {escape(latest_completion_et or '—')} ET</p>",
        f"<p class='meta'>Freshness: <span class='badge {'badge-warn' if global_is_stale else 'badge-ok'}'>"
        f"{escape(freshness_label)}</span> · Strategy {escape(strategy_version)}</p>",
        "<p class='meta'><em>Research only — not financial advice.</em></p>",
    ]

    if unavailable:
        html_parts.append(
            "<div class='warn-box'>No completed scan results were available at send time. "
            "Check scan jobs in StockPick Ops.</div>"
        )
    elif partial:
        html_parts.append(
            "<div class='warn-box'>Partial results — one or more buckets had no completed scan.</div>"
        )

    html_parts.append("<h2>Executive summary</h2><ul>")
    for sec in sections:
        if sec.missing:
            html_parts.append(f"<li><strong>{escape(sec.label)}</strong>: no results</li>")
            continue
        top_sym = (sec.strongest or {}).get("symbol") or "—"
        stale_tag = " <span class='badge badge-warn'>STALE</span>" if sec.is_stale else ""
        html_parts.append(
            f"<li><strong>{escape(sec.label)}</strong>: {len(sec.results)} candidates{stale_tag} "
            f"— strongest <strong>{escape(str(top_sym))}</strong> (age {escape(sec.age_label)})</li>"
        )
        for w in sec.warnings:
            html_parts.append(f"<li class='meta'>⚠ {escape(w)}</li>")
    html_parts.append("</ul>")

    for sec in sections:
        if sec.missing:
            continue
        html_parts.append(f"<h2>{escape(sec.label)} — top picks</h2>")
        html_parts.append(
            "<table><thead><tr>"
            "<th>#</th><th>Ticker</th><th>Score</th><th class='num'>Price</th>"
            "<th>Conf</th><th>Trade</th><th>Risk</th><th>Signals</th>"
            "</tr></thead><tbody>"
        )
        for idx, row in enumerate(sec.results):
            sigs = ", ".join(_top_signals(row, 2)) or "—"
            html_parts.append(
                "<tr>"
                f"<td>{idx + 1}</td>"
                f"<td><strong>{escape(str(row.get('symbol') or '—'))}</strong><br>"
                f"<span class='meta'>{escape(_company_name(row))}</span></td>"
                f"<td class='num'>{escape(_fmt_score(row.get('score')))}</td>"
                f"<td class='num'>{escape(_fmt_price(row.get('price')))}</td>"
                f"<td class='num'>{escape(_fmt_score(row.get('confidence_score')))}</td>"
                f"<td class='num'>{escape(_fmt_score(row.get('tradability_score')))}</td>"
                f"<td>{escape(_risk_label(row))}</td>"
                f"<td class='meta'>{escape(sigs)}</td>"
                "</tr>"
            )
        html_parts.append("</tbody></table>")

        comp = sec.comparison
        if comp.new_entries or comp.dropped or comp.rank_improvements:
            html_parts.append("<h2>Changes since previous scan</h2><ul>")
            if comp.new_entries:
                html_parts.append(f"<li>New: {escape(', '.join(comp.new_entries[:8]))}</li>")
            if comp.dropped:
                html_parts.append(f"<li>Dropped: {escape(', '.join(comp.dropped[:8]))}</li>")
            for item in comp.rank_improvements[:5]:
                html_parts.append(
                    f"<li>{escape(item['symbol'])} rank {item['from_rank']} → {item['to_rank']} "
                    f"(+{item['delta']})</li>"
                )
            for item in comp.rank_declines[:5]:
                html_parts.append(
                    f"<li>{escape(item['symbol'])} rank {item['from_rank']} → {item['to_rank']} "
                    f"({item['delta']})</li>"
                )
            html_parts.append("</ul>")

    html_parts.extend(
        [
            "<h2>Links</h2><div class='links'>",
            f"<a href='{escape(scan_url)}'>Open Scan</a>",
            f"<a href='{escape(penny_url)}'>Open Penny Results</a>",
            f"<a href='{escape(compounder_url)}'>Open Compounder Results</a>",
            f"<a href='{escape(quant_lab_url)}'>Open Quant Lab</a>",
            "</div>",
            "<p class='footer'>StockPick is a research and educational tool. "
            "This email is not financial advice.</p>",
            "</div></body></html>",
        ]
    )

    return MorningScanEmailContent(subject=subject, html="".join(html_parts), text="\n".join(text_lines))
