"""
Chart Generator — produces a beautiful Plotly horizontal bar chart
of the weekly market keyword demand and saves it as a self-contained HTML file.
"""
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_trends_chart(ranked_keywords: list[tuple[str, int]], window_days: int = 7) -> str | None:
    """
    Generates an interactive Plotly horizontal bar chart from (keyword, count) pairs.
    Saves it as a standalone HTML file in data/reports/.
    Returns the path to the HTML file, or None on error.
    """
    if not ranked_keywords:
        logger.warning("No keyword data to chart.")
        return None

    try:
        import plotly.graph_objects as go
        from src.config import REPORTS_DIR

        keywords = [kw for kw, _ in ranked_keywords]
        counts   = [cnt for _, cnt in ranked_keywords]
        max_count = max(counts) if counts else 1

        # ─── Colour gradient: green (high) → amber → red (low) ──────────────
        def _colour(count):
            ratio = count / max_count
            if ratio >= 0.6:
                return "#22c55e"   # green
            elif ratio >= 0.35:
                return "#f59e0b"   # amber
            else:
                return "#ef4444"   # red

        colours = [_colour(c) for c in counts]

        fig = go.Figure(go.Bar(
            x=counts,
            y=keywords,
            orientation="h",
            marker_color=colours,
            text=[f"  {c}" for c in counts],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Mentions: %{x}<extra></extra>",
        ))

        week_label = f"Last {window_days} Days"
        fig.update_layout(
            title={
                "text": f"📊 Job Market Keyword Demand — {week_label}",
                "x": 0.5,
                "xanchor": "center",
                "font": {"size": 22, "color": "#1e293b"},
            },
            xaxis=dict(
                title="Frequency (mentions + missing keyword score)",
                showgrid=True,
                gridcolor="#e2e8f0",
            ),
            yaxis=dict(
                autorange="reversed",  # highest at top
                tickfont={"size": 13},
            ),
            plot_bgcolor="#f8fafc",
            paper_bgcolor="#ffffff",
            font={"family": "Inter, Arial, sans-serif", "color": "#334155"},
            margin=dict(l=20, r=80, t=80, b=60),
            height=max(500, len(keywords) * 30 + 120),
            annotations=[
                dict(
                    x=0.5, y=-0.12, xref="paper", yref="paper",
                    text=(
                        "<span style='color:#22c55e'>■ High demand</span>  "
                        "<span style='color:#f59e0b'>■ Medium</span>  "
                        "<span style='color:#ef4444'>■ Lower demand</span>"
                    ),
                    showarrow=False, font={"size": 12}, align="center",
                )
            ]
        )

        today_str = datetime.utcnow().strftime("%Y%m%d")
        png_path  = REPORTS_DIR / f"weekly_trends_{today_str}.png"
        html_path = REPORTS_DIR / f"weekly_trends_{today_str}.html"

        # Save interactive HTML (kept as backup)
        fig.write_html(str(html_path), include_plotlyjs="cdn", full_html=True)

        # Save PNG for inline email embedding (requires kaleido)
        try:
            fig.write_image(str(png_path), width=900, height=max(500, len(keywords) * 30 + 120), scale=2)
            logger.info(f"✅ Trends chart PNG saved: {png_path}")
            return str(png_path)
        except Exception as img_err:
            logger.warning(f"Could not write PNG (kaleido issue?), falling back to HTML: {img_err}")
            return str(html_path)

    except ImportError:
        logger.error("Plotly is not installed. Run: pip install plotly")
        return None
    except Exception as e:
        logger.error(f"Chart generation failed: {e}", exc_info=True)
        return None
