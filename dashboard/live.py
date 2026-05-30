"""
live.py — Rich terminal live dashboard.

Polls the Intelligence API every 5 seconds and renders a live table showing:
  - Unique visitors today
  - Conversion rate
  - Current queue depth
  - Top zone by dwell time
  - Active anomaly count + severity

Usage:
    python dashboard/live.py --store-id STORE_BLR_001 --api-url http://localhost:8000

Requires:
    pip install rich httpx
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from typing import Optional

import httpx
from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

SEVERITY_STYLES = {
    "INFO": "blue",
    "WARN": "yellow bold",
    "CRITICAL": "red bold",
}

POLL_INTERVAL = 5  # seconds


# ---------------------------------------------------------------------------
# API fetchers
# ---------------------------------------------------------------------------

def fetch_metrics(api_url: str, store_id: str, date: Optional[str] = None) -> Optional[dict]:
    try:
        params = {"date": date} if date else {}
        resp = httpx.get(f"{api_url}/stores/{store_id}/metrics", params=params, timeout=5.0)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def fetch_anomalies(api_url: str, store_id: str) -> Optional[dict]:
    try:
        resp = httpx.get(f"{api_url}/stores/{store_id}/anomalies", timeout=5.0)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def fetch_funnel(api_url: str, store_id: str, date: Optional[str] = None) -> Optional[dict]:
    try:
        params = {"date": date} if date else {}
        resp = httpx.get(f"{api_url}/stores/{store_id}/funnel", params=params, timeout=5.0)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _build_metrics_table(metrics: Optional[dict], anomalies: Optional[dict]) -> Panel:
    table = Table(show_header=True, header_style="bold cyan", expand=True)
    table.add_column("Metric", style="dim", width=28)
    table.add_column("Value", justify="right")

    if metrics is not None:
        conf_flag = "[green]High[/green]" if metrics.get("data_confidence") else "[yellow]Low[/yellow]"
        table.add_row("Unique Visitors", str(metrics.get("unique_visitors", 0)))
        table.add_row("Conversion Rate", f"{metrics.get('conversion_rate', 0.0):.1%}")
        table.add_row("Abandonment Rate", f"{metrics.get('abandonment_rate', 0.0):.1%}")
        table.add_row("Queue Depth", str(metrics.get("current_queue_depth", 0)))
        table.add_row("Data Confidence", conf_flag)
        zone_dwells = metrics.get("avg_dwell_ms_by_zone") or []
        if zone_dwells:
            top_zone = zone_dwells[0]
            dwell_sec = (top_zone.get("avg_dwell_ms") or 0) / 1000
            table.add_row("Top Zone (Dwell)", f"{top_zone['zone_id']} ({dwell_sec:.0f}s)")
    else:
        table.add_row("[red]API Unreachable[/red]", "—")

    anomaly_count = len(anomalies.get("anomalies", [])) if anomalies else 0
    critical_count = sum(
        1 for a in (anomalies or {}).get("anomalies", []) if a.get("severity") == "CRITICAL"
    )
    anomaly_style = "red bold" if critical_count > 0 else ("yellow" if anomaly_count > 0 else "green")
    table.add_row(
        "Active Anomalies",
        f"[{anomaly_style}]{anomaly_count} ({critical_count} CRITICAL)[/{anomaly_style}]",
    )

    return Panel(table, title="[bold cyan]Store Metrics[/bold cyan]", border_style="cyan")


def _build_funnel_panel(funnel: Optional[dict]) -> Panel:
    table = Table(show_header=True, header_style="bold magenta", expand=True)
    table.add_column("Stage", style="dim")
    table.add_column("Count", justify="right")
    table.add_column("Drop-off", justify="right")

    if funnel is not None:
        for stage in (funnel.get("stages") or []):
            drop = stage.get("drop_off_pct", 0)
            drop_style = "red" if drop > 50 else ("yellow" if drop > 25 else "green")
            table.add_row(
                stage.get("stage", ""),
                str(stage.get("count", 0)),
                f"[{drop_style}]{drop:.1f}%[/{drop_style}]",
            )
        if not funnel.get("stages"):
            table.add_row("[dim]No data[/dim]", "—", "—")
    else:
        table.add_row("[red]Unavailable[/red]", "—", "—")

    return Panel(table, title="[bold magenta]Conversion Funnel[/bold magenta]", border_style="magenta")


def _build_anomalies_panel(anomalies: Optional[dict]) -> Panel:
    table = Table(show_header=True, header_style="bold red", expand=True)
    table.add_column("Type", style="dim", no_wrap=True)
    table.add_column("Sev", width=8)
    table.add_column("Description", no_wrap=False)

    if anomalies:
        for a in anomalies.get("anomalies", [])[:5]:
            sev = a.get("severity", "INFO")
            style = SEVERITY_STYLES.get(sev, "white")
            desc = a.get("description", "")[:60]
            table.add_row(
                a.get("anomaly_type", ""),
                f"[{style}]{sev}[/{style}]",
                desc,
            )
        if not anomalies.get("anomalies"):
            table.add_row("[green]No active anomalies[/green]", "", "")
    else:
        table.add_row("[red]Unavailable[/red]", "", "")

    return Panel(table, title="[bold red]Anomalies[/bold red]", border_style="red")


def _build_header(store_id: str, last_updated: str, connected: bool, date: Optional[str] = None) -> Panel:
    status = "[green]CONNECTED[/green]" if connected else "[red]DISCONNECTED[/red]"
    date_label = f"  ·  Date: [cyan]{date}[/cyan]" if date else ""
    text = Text.assemble(
        ("Store Intelligence Dashboard  ·  ", "bold"),
        (store_id, "bold cyan"),
        ("  ·  ", "dim"),
        Text.from_markup(f"API: {status}{date_label}"),
        ("  ·  Updated: ", "dim"),
        (last_updated, "dim"),
    )
    return Panel(text, border_style="dim")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_dashboard(store_id: str, api_url: str, poll_interval: int = POLL_INTERVAL, date: Optional[str] = None) -> None:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="anomalies", size=10),
    )
    layout["body"].split_row(
        Layout(name="metrics"),
        Layout(name="funnel"),
    )

    with Live(layout, console=console, refresh_per_second=1, screen=True):
        while True:
            metrics = fetch_metrics(api_url, store_id, date)
            anomalies = fetch_anomalies(api_url, store_id)
            funnel = fetch_funnel(api_url, store_id, date)

            now = datetime.now(tz=timezone.utc).strftime("%H:%M:%S UTC")
            connected = metrics is not None

            layout["header"].update(_build_header(store_id, now, connected, date))
            layout["metrics"].update(_build_metrics_table(metrics, anomalies))
            layout["funnel"].update(_build_funnel_panel(funnel))
            layout["anomalies"].update(_build_anomalies_panel(anomalies))

            time.sleep(poll_interval)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Store Intelligence live dashboard")
    parser.add_argument("--store-id", default="STORE_BLR_001", help="Store ID to monitor")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--interval", type=int, default=POLL_INTERVAL, help="Poll interval (seconds)")
    parser.add_argument("--date", default=None, help="Date to query (YYYY-MM-DD). Defaults to today.")
    args = parser.parse_args()

    console.print(f"\n[bold cyan]Starting dashboard for {args.store_id}...[/bold cyan]")
    console.print(f"API: [dim]{args.api_url}[/dim]  |  Press [bold]Ctrl+C[/bold] to exit\n")
    time.sleep(1)

    try:
        run_dashboard(args.store_id, args.api_url, args.interval, args.date)
    except KeyboardInterrupt:
        console.print("\n[dim]Dashboard stopped.[/dim]")
