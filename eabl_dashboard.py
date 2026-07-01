

import copy
import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objects as go

# Create the Dash App instance
app = dash.Dash(__name__)

# EXPOSE THE FLASK SERVER INSTANCE FOR VERCEL (Crucial)
server = app.server 

# 
#  PROBLEM DATA & GEOGRAPHY
BREWERIES = ["Kisumu", "Ruaraka", "Mombasa"]
OUTLETS   = ["Eldoret", "Machakos", "Kisii", "Kisumu"]

# Lat/Lon for Mapbox integration
COORDS = {
    "Kisumu": {"lat": -0.1022, "lon": 34.7617},
    "Ruaraka": {"lat": -1.2540, "lon": 36.8760}, 
    "Mombasa": {"lat": -4.0435, "lon": 39.6682},
    "Eldoret": {"lat": 0.5143, "lon": 35.2698},
    "Machakos": {"lat": -1.5149, "lon": 37.2634},
    "Kisii": {"lat": -0.6766, "lon": 34.7770}
}

COSTS = [                            #  Eldoret  Machakos   Kisii  Kisumu
    [ 4_400,  11_000,  3_300,    500],   # Kisumu
    [ 9_100,   2_000,  9_700, 10_200],   # Ruaraka
    [26_100,  14_600, 20_700, 23_700],   # Mombasa
]

DEF_SUPPLY = [120, 200,  80]
DEF_DEMAND = [ 80, 100,  60, 150]

SUPPLY_RANGE = [(20, 350), (50, 400), (20, 200)]
DEMAND_RANGE = [(20, 200), (20, 250), (20, 150), (20, 300)]

#  VAM SOLVER
def vam_solve(supply_in, demand_in, costs_in):
    supply = list(supply_in)
    demand = list(demand_in)
    costs  = copy.deepcopy(costs_in)
    m, n   = len(supply), len(demand)
    ts, td = sum(supply), sum(demand)

    dummy_col = dummy_row = False
    if ts > td:
        demand.append(ts - td)
        for c in costs: c.append(0)
        n += 1; dummy_col = True
    elif td > ts:
        supply.append(td - ts)
        costs.append([0] * n)
        m += 1; dummy_row = True

    row_done = [False] * m
    col_done = [False] * n
    routes, iters = [], []

    def active_rows(): return [i for i in range(m) if not row_done[i]]
    def active_cols(): return [j for j in range(n) if not col_done[j]]

    step = 0
    while True:
        ar, ac = active_rows(), active_cols()
        if not ar or not ac: break

        def row_pen(i):
            v = sorted(costs[i][j] for j in ac)
            return v[1] - v[0] if len(v) >= 2 else v[0]
        def col_pen(j):
            v = sorted(costs[i][j] for i in ar)
            return v[1] - v[0] if len(v) >= 2 else v[0]

        row_pens = {i: row_pen(i) for i in ar}
        col_pens = {j: col_pen(j) for j in ac}

        best_row = max(ar, key=lambda i: row_pens[i])
        best_col = max(ac, key=lambda j: col_pens[j])

        if row_pens[best_row] >= col_pens[best_col]:
            i = best_row
            j = min(ac, key=lambda j: costs[i][j])
            chosen = ("row", i, row_pens[best_row])
        else:
            j = best_col
            i = min(ar, key=lambda i: costs[i][j])
            chosen = ("col", j, col_pens[best_col])

        qty = min(supply[i], demand[j])
        supply[i] -= qty
        demand[j] -= qty

        is_dummy = (dummy_col and j == n - 1) or (dummy_row and i == m - 1)
        routes.append(dict(src=i, dst=j, qty=qty, uc=costs[i][j], tc=qty * costs[i][j], dummy=is_dummy, step=step))
        iters.append(dict(step=step, chosen=chosen, src=i, dst=j, qty=qty, uc=costs[i][j]))
        step += 1

        if supply[i] == 0 and demand[j] == 0: col_done[j] = True
        elif supply[i] == 0: row_done[i] = True
        else: col_done[j] = True

    return routes, iters

BG      = "#0B0E14"
SURFACE = "#151A22"
CARD    = "#1D232E"
BORDER  = "#2C3545"
TXT     = "#F8F9FA"
MUTED   = "#9AA6B8"
ACCENT  = "#F4B41A" 
GREEN   = "#2ECC71"
AMBER   = "#E67E22"
RED     = "#E74C3C"

BREW_COLORS   = [GREEN, ACCENT, RED]
OUTLET_COLORS = ["#5DADE2", "#48C9B0", "#F5B041", "#AF7AC5"]
EFF_THRESHOLDS = (3_000, 12_000)

def eff_color(cost): return GREEN if cost < EFF_THRESHOLDS[0] else ACCENT if cost < EFF_THRESHOLDS[1] else RED
def eff_label(cost): return "Efficient" if cost < EFF_THRESHOLDS[0] else "Moderate" if cost < EFF_THRESHOLDS[1] else "Expensive"

def hex_to_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

def rgba(h, a=1.0):
    r, g, b = hex_to_rgb(h)
    return f"rgba({r},{g},{b},{a})"

TRANSPARENT = "rgba(0,0,0,0)"

BASE_LAYOUT = dict(
    paper_bgcolor=TRANSPARENT, plot_bgcolor=TRANSPARENT,
    margin=dict(l=0, r=0, t=10, b=10),
    font=dict(family="Inter, sans-serif", color=TXT, size=12),
    transition=dict(duration=400, easing="cubic-in-out")
)

#  ROBUST FIGURE BUILDERS
def build_map(routes):
    real = [r for r in routes if not r["dummy"]]
    fig = go.Figure()

    # Draw connection lines
    for r in real:
        src = BREWERIES[r['src']]
        dst = OUTLETS[r['dst']]
        fig.add_trace(go.Scattermapbox(
            mode="lines",
            lon=[COORDS[src]["lon"], COORDS[dst]["lon"]],
            lat=[COORDS[src]["lat"], COORDS[dst]["lat"]],
            line=dict(width=max(2, (r['qty'] / max(1, sum([x['qty'] for x in real]))) * 15), color=eff_color(r['uc'])),
            opacity=0.6, hoverinfo="none", showlegend=False
        ))

    # Draw Nodes
    for is_brewery, locations in [(True, BREWERIES), (False, OUTLETS)]:
        fig.add_trace(go.Scattermapbox(
            mode="markers+text",
            lon=[COORDS[loc]["lon"] for loc in locations],
            lat=[COORDS[loc]["lat"] for loc in locations],
            marker=dict(size=14 if is_brewery else 10, color=ACCENT if is_brewery else TXT),
            text=locations, textposition="top right",
            textfont=dict(size=12, color=TXT if is_brewery else MUTED, weight="bold" if is_brewery else "normal"),
            name="Breweries" if is_brewery else "Outlets",
            hoverinfo="text", hovertext=[f"<b>{loc}</b><br>{'Production Hub' if is_brewery else 'Naivas Outlet'}" for loc in locations]
        ))

    fig.update_layout(**BASE_LAYOUT)
    fig.update_layout(
        height=360, margin=dict(l=0,r=0,t=0,b=0),
        mapbox=dict(style="carto-darkmatter", center=dict(lat=-0.5, lon=36.5), zoom=5.5),
        legend=dict(orientation="h", yanchor="bottom", y=0.02, xanchor="center", x=0.5, bgcolor=rgba(CARD, 0.8), bordercolor=BORDER, borderwidth=1)
    )
    return fig

def build_sankey(routes):
    real = [r for r in routes if not r["dummy"]]
    nb = len(BREWERIES)
    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(pad=24, thickness=22, label=BREWERIES + OUTLETS, color=BREW_COLORS + OUTLET_COLORS, line=dict(width=0)),
        link=dict(
            source=[r["src"] for r in real], target=[nb + r["dst"] for r in real],
            value =[r["qty"] for r in real], color=[rgba(eff_color(r["uc"]), 0.35) for r in real],
            customdata=[[r["qty"], f'{r["uc"]:,}', f'{r["tc"]:,}'] for r in real],
            hovertemplate="<b>%{source.label} → %{target.label}</b><br>Volume: %{customdata[0]}u<br>Cost: KES %{customdata[2]}<extra></extra>",
        ),
    ))
    fig.update_layout(**BASE_LAYOUT)
    fig.update_layout(height=280)  
    return fig

def build_treemap(routes):
    real = [r for r in routes if not r["dummy"]]
    labels, parents, values, colors, texts = ["Total Cost"], [""], [sum(r['tc'] for r in real)], [TRANSPARENT], [""]
    
    # Breweries Layer
    for i, b in enumerate(BREWERIES):
        cost = sum(r['tc'] for r in real if r['src'] == i)
        if cost > 0:
            labels.append(b)
            parents.append("Total Cost")
            values.append(cost)
            colors.append(rgba(BREW_COLORS[i], 0.8))
            texts.append(f"KES {cost:,}")

    # Routes Layer
    for r in real:
        if r['tc'] > 0:
            lbl = f"{BREWERIES[r['src']]}→{OUTLETS[r['dst']]}"
            labels.append(lbl)
            parents.append(BREWERIES[r['src']])
            values.append(r['tc'])
            colors.append(rgba(eff_color(r['uc']), 0.6))
            texts.append(f"Qty: {r['qty']} <br>KES {r['tc']:,}")

    fig = go.Figure(go.Treemap(
        labels=labels, parents=parents, values=values, marker=dict(colors=colors),
        textinfo="label+text+percent parent", text=texts,
        hovertemplate="<b>%{label}</b><br>Cost: %{value}<extra></extra>"
    ))
    fig.update_layout(**BASE_LAYOUT)
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0))
    return fig

def build_heatmap(routes):
    am = {(r["src"], r["dst"]): r["qty"] for r in routes if not r["dummy"]}
    text = [[f"KES {COSTS[i][j]:,}" + (f"<br><b>✓ {am[(i,j)]}u</b>" if (i, j) in am else "")
             for j in range(4)] for i in range(3)]
    fig = go.Figure(go.Heatmap(
        z=COSTS, x=OUTLETS, y=BREWERIES,
        colorscale=[[0, rgba(GREEN,0.8)], [0.3, rgba(ACCENT,0.8)], [1, rgba(RED,0.8)]],
        text=text, texttemplate="%{text}", textfont=dict(size=12, color="white"),
        hovertemplate="<b>%{y} → %{x}</b><br>KES %{z:,} / 100c<extra></extra>",
        showscale=True, colorbar=dict(title=dict(text="KES", font=dict(color=MUTED)), tickfont=dict(color=MUTED), thickness=10)
    ))
    fig.update_layout(**BASE_LAYOUT)
    fig.update_layout(height=280, margin=dict(l=0, r=20, t=20, b=20),
                      xaxis=dict(color=MUTED, side="top"), yaxis=dict(color=MUTED))
    return fig

def build_utilization(supply, routes):
    used = [0] * len(BREWERIES)
    for r in routes:
        if not r["dummy"] and r["src"] < len(BREWERIES):
            used[r["src"]] += r["qty"]

    fig = go.Figure()
    for i, (b, s, u) in enumerate(zip(BREWERIES, supply, used)):
        pct = u / s * 100 if s else 0
        fig.add_trace(go.Bar(
            name=b, x=[b], y=[u], marker=dict(color=BREW_COLORS[i], line=dict(width=0)),
            text=[f"{pct:.0f}%<br>({u}/{s})"], textposition="inside", textfont=dict(size=12, color="#000" if i==1 else "white", weight="bold"),
            hovertemplate=f"<b>{b}</b><br>Used: {u}<br>Capacity: {s}<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            name=f"{b} idle", x=[b], y=[s - u], marker=dict(color=rgba(BREW_COLORS[i], 0.15), line=dict(width=0)),
            hovertemplate=f"<b>{b} idle</b><br>{s - u} units<extra></extra>", showlegend=False,
        ))
    fig.update_layout(**BASE_LAYOUT)
    fig.update_layout(height=250, barmode="stack", showlegend=False, xaxis=dict(showgrid=False, color=TXT), yaxis=dict(showgrid=True, gridcolor=BORDER, color=MUTED))
    return fig

def vam_steps_html(iters):
    rows = []
    for it in iters:
        kind, idx, pen = it["chosen"]
        chosen_desc = f"Row {BREWERIES[idx]} (pen {pen:,})" if kind == "row" else f"Col {OUTLETS[idx] if idx<4 else 'Dummy'} (pen {pen:,})"
        rows.append(html.Tr([
            html.Td(f"Step {it['step']+1}", style=dict(padding="10px", color=MUTED, borderBottom=f"1px solid {BORDER}")),
            html.Td(chosen_desc, style=dict(padding="10px", color=TXT, borderBottom=f"1px solid {BORDER}")),
            html.Td(f"{BREWERIES[it['src']]} → {OUTLETS[it['dst']] if it['dst']<4 else 'Dummy'}", style=dict(padding="10px", color=ACCENT, fontWeight="bold", borderBottom=f"1px solid {BORDER}")),
            html.Td(f"{it['qty']} units", style=dict(padding="10px", color=TXT, borderBottom=f"1px solid {BORDER}")),
            html.Td(f"KES {it['qty']*it['uc']:,}", style=dict(padding="10px", color=MUTED, borderBottom=f"1px solid {BORDER}")),
        ]))
    return html.Table([
        html.Thead(html.Tr([html.Th(c, style=dict(padding="10px", color=MUTED, textAlign="left", borderBottom=f"2px solid {BORDER}")) for c in ["Iter", "Decision Pivot", "Route Allocated", "Volume", "Subtotal"]])),
        html.Tbody(rows),
    ], style=dict(width="100%", borderCollapse="collapse", fontSize="13px"))

# ─────────────────────────────────────────────────────────────────────────────
#  COMPONENTS
# ─────────────────────────────────────────────────────────────────────────────
def kpi_card(label, value, sub, color=TXT):
    return html.Div([
        html.Div(label, style=dict(fontSize="11px", color=MUTED, textTransform="uppercase", letterSpacing="1px", marginBottom="8px")),
        html.Div(value, style=dict(fontSize="28px", fontWeight="700", color=color, letterSpacing="-0.5px")),
        html.Div(sub,   style=dict(fontSize="12px", color=MUTED, marginTop="6px")),
    ], style=dict(background=CARD, borderRadius="12px", padding="20px", border=f"1px solid {BORDER}", flex="1", boxShadow="0 4px 12px rgba(0,0,0,0.1)"))

def section(title, subtitle, children, **extra):
    style = {"background": CARD, "borderRadius": "12px", "padding": "24px", "border": f"1px solid {BORDER}", "marginBottom": "16px", "boxShadow": "0 4px 12px rgba(0,0,0,0.1)"}
    if "style" in extra: style.update(extra.pop("style"))
    style.update(extra)
    return html.Div([
        html.Div(title, style={"fontSize": "16px", "fontWeight": "700", "color": TXT, "marginBottom": "4px"}),
        html.Div(subtitle, style={"fontSize": "13px", "color": MUTED, "marginBottom": "20px"}),
        *children,
    ], style=style)

def slider_row(label, slider_id, lo, hi, val, clr):
    return html.Div([
        html.Div([
            html.Span(label, style=dict(fontSize="13px", color=TXT, fontWeight="500")),
            html.Span(f"{val} units", id=f"{slider_id}-val", style=dict(fontSize="12px", color=ACCENT, fontWeight="600")),
        ], style=dict(display="flex", justifyContent="space-between", marginBottom="8px")),
        dcc.Slider(id=slider_id, min=lo, max=hi, step=10, value=val, marks=None, tooltip={"placement": "bottom", "always_visible": False}),
    ], style=dict(marginBottom="24px"))

def route_table_html(routes):
    real = sorted([r for r in routes if not r["dummy"]], key=lambda r: r["tc"], reverse=True)
    ef_bg = {"Efficient": "#0A2419", "Moderate": "#1D160A", "Expensive": "#291010"}
    ef_fg = {"Efficient": GREEN,     "Moderate": ACCENT,    "Expensive": RED}

    rows = []
    for r in real:
        tier = eff_label(r["uc"])
        rows.append(html.Tr([
            html.Td(f"{BREWERIES[r['src']]} → {OUTLETS[r['dst']]}", style=dict(padding="14px 16px", color=TXT, fontWeight="bold", borderBottom=f"1px solid {BORDER}")),
            html.Td(f"{r['qty']} × 100 crates", style=dict(padding="14px 16px", color=MUTED, borderBottom=f"1px solid {BORDER}")),
            html.Td(f"KES {r['uc']:,}", style=dict(padding="14px 16px", color=MUTED, textAlign="right", borderBottom=f"1px solid {BORDER}")),
            html.Td(f"KES {r['tc']:,}", style=dict(padding="14px 16px", color=ACCENT, fontWeight="bold", textAlign="right", borderBottom=f"1px solid {BORDER}")),
            html.Td(html.Span(tier, style=dict(fontSize="12px", fontWeight="600", color=ef_fg[tier], background=ef_bg[tier], padding="4px 12px", borderRadius="20px")), style=dict(padding="14px 16px", borderBottom=f"1px solid {BORDER}")),
        ], className="table-row-hover"))

    return html.Table([
        html.Thead(html.Tr([html.Th(c, style=dict(padding="14px 16px", fontSize="12px", color=MUTED, textAlign="left" if i<2 else "right" if i<4 else "left", borderBottom=f"2px solid {BORDER}", background=SURFACE)) for i, c in enumerate(["Route", "Volume", "Unit Cost (KES)", "Monthly Cost (KES)", "Efficiency Tier"])])),
        html.Tbody(rows),
    ], style=dict(width="100%", borderCollapse="collapse", fontSize="13px"))

# ─────────────────────────────────────────────────────────────────────────────
#  APP LAYOUT
# ─────────────────────────────────────────────────────────────────────────────
app = dash.Dash(__name__, title="EABL × Naivas | Executive Dashboard")

app.index_string = f"""
<!DOCTYPE html>
<html>
  <head>
    {{%metas%}}<title>{{%title%}}</title>{{%favicon%}}{{%css%}}
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
      *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
      body {{ background: {BG}; color: {TXT}; font-family: 'Inter', sans-serif; overflow-x: hidden; }}
      ::-webkit-scrollbar {{ width: 8px; }}
      ::-webkit-scrollbar-track {{ background: {SURFACE}; }}
      ::-webkit-scrollbar-thumb {{ background: {BORDER}; border-radius: 4px; }}
      
      .app-container {{ display: flex; height: 100vh; overflow: hidden; }}
      .sidebar {{ width: 350px; background: {SURFACE}; padding: 30px 24px; display: flex; flex-direction: column; gap: 15px; overflow-y: auto; border-right: 1px solid {BORDER}; z-index: 10; box-shadow: 4px 0 15px rgba(0,0,0,0.2);}}
      .main-content {{ flex: 1; padding: 30px 40px; overflow-y: auto; }}

      .tab-bar {{ display: flex; gap: 8px; margin-bottom: 24px; background: {CARD}; border-radius: 12px; padding: 6px; border: 1px solid {BORDER}; box-shadow: 0 4px 12px rgba(0,0,0,0.1);}}
      .tab-btn {{ flex: 1; padding: 12px 16px; border: none; border-radius: 8px; background: transparent; color: {MUTED}; font-size: 14px; font-weight: 500; cursor: pointer; transition: all 0.3s ease; }}
      .tab-btn:hover {{ color: {TXT}; background: rgba(255,255,255,0.03); }}
      .tab-btn.active {{ color: {BG}; background: {ACCENT}; font-weight: 700; box-shadow: 0 2px 10px rgba(244, 180, 26, 0.3); }}

      .export-btn {{ width: 100%; padding: 14px; background: transparent; color: {TXT}; border: 1px solid {ACCENT}; border-radius: 8px; font-family: 'Inter'; font-weight: 600; cursor: pointer; transition: 0.2s; margin-top: auto;}}
      .export-btn:hover {{ background: {ACCENT}; color: {BG}; box-shadow: 0 4px 12px rgba(244, 180, 26, 0.3);}}

      .rc-slider-rail {{ background: {BORDER} !important; height: 6px !important; border-radius: 3px !important; }}
      .rc-slider-track {{ background: {ACCENT} !important; height: 6px !important; border-radius: 3px !important;}}
      .rc-slider-handle {{ border: 3px solid {ACCENT} !important; background: {CARD} !important; width: 18px !important; height: 18px !important; margin-top: -6px !important; box-shadow: 0 0 0 4px {rgba(ACCENT, 0.15)} !important; cursor: grab !important; transition: transform 0.1s ease !important; }}
      .rc-slider-handle:active {{ transform: scale(1.1) !important; cursor: grabbing !important; }}
      .table-row-hover {{ transition: background 0.2s ease; }}
      .table-row-hover:hover {{ background: {rgba(ACCENT, 0.05)}; }}
    </style>
  </head>
  <body>
    {{%app_entry%}}
    <footer>{{%config%}}{{%scripts%}}{{%renderer%}}</footer>
  </body>
</html>
"""

app.layout = html.Div(className="app-container", children=[
    dcc.Download(id="download-csv"),
    
    # ── SIDEBAR ──
    html.Div(className="sidebar", children=[
        html.Div([
            html.Div("EABL × NAIVAS", style=dict(fontSize="13px", color=ACCENT, fontWeight="700", letterSpacing="2px", marginBottom="6px")),
            html.H1("Logistics Hub", style=dict(fontSize="24px", fontWeight="700", color=TXT, margin=0, lineHeight="1.2")),
        ], style=dict(marginBottom="10px")),

        html.Div("SCENARIO CONTROLS", style=dict(fontSize="11px", fontWeight="700", color=MUTED, letterSpacing="1px", marginTop="10px", borderBottom=f"1px solid {BORDER}", paddingBottom="8px")),
        
        html.Div([
            html.Div("Breweries Supply (100c)", style=dict(fontSize="12px", color=TXT, fontWeight="600", marginBottom="16px")),
            *[slider_row(b, f"sup-{i}", *SUPPLY_RANGE[i], DEF_SUPPLY[i], BREW_COLORS[i]) for i, b in enumerate(BREWERIES)],
        ]),
        html.Div([
            html.Div("Outlets Demand (100c)", style=dict(fontSize="12px", color=TXT, fontWeight="600", marginBottom="16px")),
            *[slider_row(o, f"dem-{i}", *DEMAND_RANGE[i], DEF_DEMAND[i], OUTLET_COLORS[i]) for i, o in enumerate(OUTLETS)],
        ]),
        
        html.Button("📥 Export Allocation CSV", id="btn-export", className="export-btn")
    ]),

    # ── MAIN CONTENT ──
    html.Div(className="main-content", children=[
        html.Div(id="balance-badge", style=dict(marginBottom="24px")),
        html.Div(id="kpi-row", style=dict(display="flex", gap="16px", marginBottom="24px")),

        html.Div([
            html.Button("🌍 Network Routing", id="tab-btn-flows", n_clicks=0, className="tab-btn active"),
            html.Button("💰 Cost Analytics",  id="tab-btn-costs", n_clicks=0, className="tab-btn"),
            html.Button("🧠 Algorithm Matrix",id="tab-btn-matrix",n_clicks=0, className="tab-btn"),
        ], className="tab-bar"),

        dcc.Store(id="active-tab", data="flows"),
        html.Div(id="tab-content", style=dict(marginBottom="24px")),

        section("Master Allocation Schedule", "Optimized monthly freight logic sorted by total route cost", [html.Div(id="route-table")]),
        
        html.Div("EABL Distribution Engine · Powered by Dash & VAM Algorithm · Dean Munywoki, Strathmore University", style=dict(fontSize="12px", color=MUTED, textAlign="center", marginTop="40px", paddingTop="24px", borderTop=f"1px solid {BORDER}")),
    ])
])

# ─────────────────────────────────────────────────────────────────────────────
#  CALLBACKS
# ─────────────────────────────────────────────────────────────────────────────
@app.callback(
    Output("active-tab", "data"),
    Output("tab-btn-flows", "className"), Output("tab-btn-costs", "className"), Output("tab-btn-matrix", "className"),
    Input("tab-btn-flows", "n_clicks"), Input("tab-btn-costs", "n_clicks"), Input("tab-btn-matrix", "n_clicks"),
)
def switch_tab(n_flows, n_costs, n_matrix):
    ctx = dash.callback_context
    tab_map = {"tab-btn-flows": "flows", "tab-btn-costs": "costs", "tab-btn-matrix": "matrix"}
    active = tab_map.get(ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else "tab-btn-flows", "flows")
    return active, "tab-btn active" if active=="flows" else "tab-btn", "tab-btn active" if active=="costs" else "tab-btn", "tab-btn active" if active=="matrix" else "tab-btn"

@app.callback(
    Output("kpi-row", "children"), Output("tab-content", "children"), Output("balance-badge", "children"), Output("route-table", "children"),
    *[Output(f"sup-{i}-val", "children") for i in range(3)], *[Output(f"dem-{i}-val", "children") for i in range(4)],
    Input("active-tab", "data"),
    Input("sup-0", "value"), Input("sup-1", "value"), Input("sup-2", "value"),
    Input("dem-0", "value"), Input("dem-1", "value"), Input("dem-2", "value"), Input("dem-3", "value"),
)
def update_dashboard(tab, s0, s1, s2, d0, d1, d2, d3):
    supply = [s0 or DEF_SUPPLY[0], s1 or DEF_SUPPLY[1], s2 or DEF_SUPPLY[2]]
    demand = [d0 or DEF_DEMAND[0], d1 or DEF_DEMAND[1], d2 or DEF_DEMAND[2], d3 or DEF_DEMAND[3]]
    ts, td = sum(supply), sum(demand)
    routes, iters = vam_solve(supply, demand, COSTS)
    real = [r for r in routes if not r["dummy"]]
    total, crates = sum(r["tc"] for r in real), sum(demand) * 100
    avg = total / crates if crates else 0
    idle = max(0, ts - td)

    kpis = [
        kpi_card("Total Freight Expend", f"KES {total/1e6:.2f}M", "Projected monthly run rate", ACCENT),
        kpi_card("Active Corridors", f"{len(real)} Routes", "Non-degenerate assignments"),
        kpi_card("Unit Economics", f"KES {avg:.0f} / crate", f"~{avg / 25.23:.1f}% of KES 2,523 retail margin"),
        kpi_card("Idle Network Capacity", f"{idle * 100:,} crates", "Unallocated baseline supply", AMBER if idle > 0 else GREEN),
    ]

    diff = ts - td
    
    if diff == 0:
        b_text = "✓ Network Fully Balanced (Supply = Demand)"
        b_fg = GREEN
        b_bg = "rgba(46, 204, 113, 0.1)"
    elif diff > 0:
        b_text = f"⚠ Network Surplus: {diff} unallocated units (Dummy Destination Added)"
        b_fg = AMBER
        b_bg = "rgba(230, 126, 34, 0.1)"
    else:
        b_text = f"⚠ Network Deficit: {-diff} unmet demand units (Dummy Source Added)"
        b_fg = RED
        b_bg = "rgba(231, 76, 60, 0.1)"

    balance = html.Div(
        b_text, 
        style=dict(
            fontSize="13px", color=b_fg, background=b_bg, 
            padding="12px 20px", borderRadius="8px", 
            fontWeight="600", border=f"1px solid {b_fg}40"
        )
    )

    if tab == "flows":
        content = html.Div([
            html.Div([
                section("Geospatial Overview", "Physical supply routes mapped across Kenya. Weight = Volume.", [dcc.Graph(figure=build_map(routes), config=dict(displayModeBar=False))], style=dict(flex="1")),
                section("Production Line Utilization", "Live consumption vs idle capacity.", [dcc.Graph(figure=build_utilization(supply, routes), config=dict(displayModeBar=False))], style=dict(width="380px"))
            ], style=dict(display="flex", gap="16px")),
            section("Supply Chain Topography", "Volumetric flow from Production to Retail.", [dcc.Graph(figure=build_sankey(routes), config=dict(displayModeBar=False))]),
        ])
    elif tab == "costs":
        content = html.Div([
            html.Div([
                section("Financial Exposure Treemap", "Deep dive into cost centers. Size = Capital Allocation.", [dcc.Graph(figure=build_treemap(routes), config=dict(displayModeBar=False))], style=dict(flex="1"))
            ], style=dict(display="flex", gap="16px")),
        ])
    else:
        content = html.Div([
            html.Div([
                section("Logistics Cost Matrix", "Base freight costs per 100 crates. Selected routes marked with ✓.", [dcc.Graph(figure=build_heatmap(routes), config=dict(displayModeBar=False))], style=dict(flex="1")),
                section("Algorithm Audit Log", "Step-by-step trace of Vogel's Approximation Method decisions.", [html.Div(vam_steps_html(iters), style=dict(maxHeight="320px", overflowY="auto"))], style=dict(flex="1.2"))
            ], style=dict(display="flex", gap="16px"))
        ])

    return kpis, content, balance, route_table_html(routes), *[f"{v} units" for v in supply + demand]

@app.callback(
    Output("download-csv", "data"),
    Input("btn-export", "n_clicks"),
    State("sup-0", "value"), State("sup-1", "value"), State("sup-2", "value"),
    State("dem-0", "value"), State("dem-1", "value"), State("dem-2", "value"), State("dem-3", "value"),
    prevent_initial_call=True
)
def generate_csv(n_clicks, s0, s1, s2, d0, d1, d2, d3):
    supply = [s0 or DEF_SUPPLY[0], s1 or DEF_SUPPLY[1], s2 or DEF_SUPPLY[2]]
    demand = [d0 or DEF_DEMAND[0], d1 or DEF_DEMAND[1], d2 or DEF_DEMAND[2], d3 or DEF_DEMAND[3]]
    routes, _ = vam_solve(supply, demand, COSTS)
    
    csv_str = "Source,Destination,Volume (100 Crates),Unit Cost (KES),Monthly Total Cost (KES)\n"
    for r in sorted([r for r in routes if not r["dummy"]], key=lambda r: r["tc"], reverse=True):
        csv_str += f"{BREWERIES[r['src']]},{OUTLETS[r['dst']]},{r['qty']},{r['uc']},{r['tc']}\n"
    
    return dict(content=csv_str, filename="EABL_Naivas_Logistics_Schedule.csv")

if __name__ == "__main__":
    app.run(debug=True, port=8050)
