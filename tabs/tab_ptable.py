
import math

import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
import xraydb

# ── Data ────────────────────────────────────────────────────────────────────

periodic_table = [
    ["H",  "",   "",    "",   "",   "",   "",   "",   "",   "",   "",   "",   "",   "",   "",   "",   "",   "He"],
    ["Li", "Be", "",    "",   "",   "",   "",   "",   "",   "",   "",   "",   "B",  "C",  "N",  "O",  "F",  "Ne"],
    ["Na", "Mg", "",    "",   "",   "",   "",   "",   "",   "",   "",   "",   "Al", "Si", "P",  "S",  "Cl", "Ar"],
    ["K",  "Ca", "Sc", "Ti", "V",  "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn", "Ga", "Ge", "As", "Se", "Br", "Kr"],
    ["Rb", "Sr", "Y",  "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn", "Sb", "Te", "I",  "Xe"],
    ["Cs", "Ba", "*",  "Hf", "Ta", "W",  "Re", "Os", "Ir", "Pt", "Au", "Hg", "Tl", "Pb", "Bi", "Po", "At", "Rn"],
    ["Fr", "Ra", "**", "Rf", "Db", "Sg", "Bh", "Hs", "Mt", "Ds", "Rg", "Cn", "Fl", "Lv", "Ts", "Og", "",   ""],
    ["",   "",   "",   "",   "",   "",   "",   "",   "",   "",   "",   "",   "",   "",   "",   "",   "",   ""],
    ["",   "",   "La", "Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu", ""],
    ["",   "",   "Ac", "Th", "Pa", "U",  "Np", "Pu", "Am", "Cm", "Bk", "Cf", "Es", "Fm", "Md", "No", "Lr", ""],
]

element_names = {
    'H':'Hydrogen','He':'Helium','Li':'Lithium','Be':'Beryllium','B':'Boron',
    'C':'Carbon','N':'Nitrogen','O':'Oxygen','F':'Fluorine','Ne':'Neon',
    'Na':'Sodium','Mg':'Magnesium','Al':'Aluminum','Si':'Silicon','P':'Phosphorus',
    'S':'Sulfur','Cl':'Chlorine','Ar':'Argon','K':'Potassium','Ca':'Calcium',
    'Sc':'Scandium','Ti':'Titanium','V':'Vanadium','Cr':'Chromium','Mn':'Manganese',
    'Fe':'Iron','Co':'Cobalt','Ni':'Nickel','Cu':'Copper','Zn':'Zinc',
    'Ga':'Gallium','Ge':'Germanium','As':'Arsenic','Se':'Selenium','Br':'Bromine',
    'Kr':'Krypton','Rb':'Rubidium','Sr':'Strontium','Y':'Yttrium','Zr':'Zirconium',
    'Nb':'Niobium','Mo':'Molybdenum','Tc':'Technetium','Ru':'Ruthenium','Rh':'Rhodium',
    'Pd':'Palladium','Ag':'Silver','Cd':'Cadmium','In':'Indium','Sn':'Tin',
    'Sb':'Antimony','Te':'Tellurium','I':'Iodine','Xe':'Xenon','Cs':'Cesium',
    'Ba':'Barium','La':'Lanthanum','Ce':'Cerium','Pr':'Praseodymium','Nd':'Neodymium',
    'Pm':'Promethium','Sm':'Samarium','Eu':'Europium','Gd':'Gadolinium','Tb':'Terbium',
    'Dy':'Dysprosium','Ho':'Holmium','Er':'Erbium','Tm':'Thulium','Yb':'Ytterbium',
    'Lu':'Lutetium','Hf':'Hafnium','Ta':'Tantalum','W':'Tungsten','Re':'Rhenium',
    'Os':'Osmium','Ir':'Iridium','Pt':'Platinum','Au':'Gold','Hg':'Mercury',
    'Tl':'Thallium','Pb':'Lead','Bi':'Bismuth','Po':'Polonium','At':'Astatine',
    'Rn':'Radon','Fr':'Francium','Ra':'Radium','Ac':'Actinium','Th':'Thorium',
    'Pa':'Protactinium','U':'Uranium','Np':'Neptunium','Pu':'Plutonium','Am':'Americium',
    'Cm':'Curium','Bk':'Berkelium','Cf':'Californium','Es':'Einsteinium','Fm':'Fermium',
    'Md':'Mendelevium','No':'Nobelium','Lr':'Lawrencium','Rf':'Rutherfordium',
    'Db':'Dubnium','Sg':'Seaborgium','Bh':'Bohrium','Hs':'Hassium','Mt':'Meitnerium',
    'Ds':'Darmstadtium','Rg':'Roentgenium','Cn':'Copernicium','Fl':'Flerovium',
    'Lv':'Livermorium','Ts':'Tennessine','Og':'Oganesson',
}

# Flat list of all real element symbols in grid order (used for button IDs)
all_symbols = []
for row in periodic_table:
    for elem in row:
        if elem and elem not in ("*", "**"):
            all_symbols.append(elem)

# ── Color logic ──────────────────────────────────────────────────────────────

# Each tile is classified into a shell family (K, L, or M) by priority --
# whichever of those shells has an edge reachable in [e_min, e_max] first
# wins, checked in K > L > M order. Within that shell, the tile's shade is a
# gradient from a pale tint up to the shell's full base color, based on how
# much headroom (eV) the best edge in that shell has before e_max. Below
# HEADROOM_MIN there isn't even room for XANES, so the tile falls back to
# white ("cannot reach").
HEADROOM_MIN = 100   # eV — bare minimum margin past an edge to be useful (XANES)
HEADROOM_MAX = 500   # eV — margin considered ample (full EXAFS)

SHELL_EDGES = {
    "K": ["K"],
    "L": ["L1", "L2", "L3"],
    "M": ["M1", "M2", "M3", "M4", "M5"],
}

SHELL_COLORS = {
    "K": "#3fbf8a",   # mediumaquamarine (green)
    "L": "#87ceeb",   # skyblue (blue)
    "M": "#f5deb3",   # wheat (yellow)
}


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, round(c))) for c in rgb))


def shell_gradient_color(shell, headroom_ev, light_frac=0.85):
    """Interpolate from a pale tint of the shell's base color (at
    HEADROOM_MIN) up to the full base color (at HEADROOM_MAX)."""
    frac = (headroom_ev - HEADROOM_MIN) / (HEADROOM_MAX - HEADROOM_MIN)
    frac = max(0.0, min(1.0, frac))
    white = (255, 255, 255)
    base = _hex_to_rgb(SHELL_COLORS[shell])
    t = light_frac * (1 - frac)   # weight of white in the blend
    rgb = tuple(w * t + b * (1 - t) for w, b in zip(white, base))
    return _rgb_to_hex(rgb)


def _shell_status(edges, shell, e_min, e_max):
    """Classify a shell relative to [e_min, e_max]:
    - ("ok", edge_name, headroom): an edge is reachable, with its headroom (eV)
    - ("above", None, None): every edge in the shell is above e_max (not
      reached yet at this range)
    - ("below", None, None): every edge in the shell is below e_min
      (already passed)
    - ("none", None, None): the element has no edges for this shell at all
    """
    energies = []
    for name in SHELL_EDGES[shell]:
        edge = edges.get(name)
        energy = getattr(edge, "energy", None) if edge else None
        if energy is not None:
            energies.append((name, energy))

    if not energies:
        return "none", None, None

    best_name, best_headroom = None, None
    for name, energy in energies:
        if e_min <= energy <= e_max:
            headroom = e_max - energy
            if best_headroom is None or headroom > best_headroom:
                best_headroom = headroom
                best_name = name
    if best_headroom is not None:
        return "ok", best_name, best_headroom

    if min(e for _, e in energies) > e_max:
        return "above", None, None
    if max(e for _, e in energies) < e_min:
        return "below", None, None
    return "above", None, None   # straddles the range without landing inside it


def get_tile_colors(symbol, e_min, e_max):
    """Return (background_color, badge_color) for a tile: background is the
    shell's gradient shade, badge is that shell's pure legend color, so the
    two can be compared side by side. Both are white when unreachable."""
    sym = symbol.replace("*", "")
    if not sym:
        return "#f0f0f0", "#f0f0f0"
    try:
        edges = xraydb.xray_edges(sym)
    except Exception:
        return "#ffffff", "#ffffff"

    for shell in ("K", "L", "M"):
        status, _, headroom = _shell_status(edges, shell, e_min, e_max)
        if status == "ok" and headroom >= HEADROOM_MIN:
            return shell_gradient_color(shell, headroom), SHELL_COLORS[shell]

    return "#ffffff", "#ffffff"   # cannot usefully reach any edge


# ── k-space (scattering vector) conversion ──────────────────────────────────
# E_kinetic = K_TO_E_PREFACTOR * k^2 (k in Å^-1, E_kinetic in eV), from
# hbar^2 / (2 m_e) -- the same relation used to plan constant-k EXAFS scans
# at the beamline, so "headroom" (eV past an edge) doubles as "how far out in
# k-space" a scan could reach.
_M_E = 9.10938356e-31                    # electron mass, kg
_H_BAR = 6.62607015e-34 / (2 * math.pi)  # J*s
_JOULES_TO_EV = 1.602176634e-19
K_TO_E_PREFACTOR = (_H_BAR ** 2 / (2 * _M_E)) * (1 / (_JOULES_TO_EV * 1e-20))  # eV per (1/Å)^2


def headroom_to_k(headroom_ev):
    """Convert eV of headroom above an edge into the equivalent
    photoelectron wavenumber k (Å^-1)."""
    return (headroom_ev / K_TO_E_PREFACTOR) ** 0.5


def shell_headroom_details(symbol, e_min, e_max):
    """Return [(shell, status, headroom_eV_or_None, k_or_None), ...] for K,
    L, M -- the full breakdown, independent of which shell "wins" the tile's
    color, so e.g. an ample M headroom is still visible even when a
    barely-qualifying L is the one driving the tile's shade. status is "ok"
    (headroom/k populated), "above" (every edge in the shell is above
    e_max), "below" (every edge is below e_min), or "none" (the element has
    no edges for that shell)."""
    sym = symbol.replace("*", "")
    try:
        edges = xraydb.xray_edges(sym)
    except Exception:
        edges = {}

    details = []
    for shell in ("K", "L", "M"):
        status, _edge_name, headroom = _shell_status(edges, shell, e_min, e_max)
        k = headroom_to_k(headroom) if headroom is not None else None
        details.append((shell, status, headroom, k))
    return details


def l_edge_gaps(symbol):
    """For each L-edge present (L3, L2, L1), return
    (edge_name, energy, next_edge_name, gap_ev) describing how far it can be
    scanned before the next real edge up (another L-edge, or K) starts
    interfering. Unlike shell_headroom_details, this is a fixed property of
    the element -- independent of any chosen e_min/e_max scan range."""
    sym = symbol.replace("*", "")
    try:
        edges = xraydb.xray_edges(sym)
    except Exception:
        edges = {}

    order = ["L3", "L2", "L1", "K"]
    results = []
    for name, next_name in zip(order[:-1], order[1:]):
        edge = edges.get(name)
        if edge is None:
            continue
        next_edge = edges.get(next_name)
        gap = (next_edge.energy - edge.energy) if next_edge is not None else None
        results.append((name, edge.energy, next_name, gap))
    return results

# ── Layout helpers ───────────────────────────────────────────────────────────

# CELL_SIZE = "36px"

def make_element_button(symbol):
    """Return a single periodic-table cell (button or placeholder)."""
    if not symbol:
        return html.Div(style={"flex": "1", "aspectRatio": "1", "margin": "1px",
                               "visibility": "hidden"})
    if symbol in ("*", "**"):
        return html.Div(
            symbol,
            style={
                "flex": "1", "aspectRatio": "1",
                "display": "flex", "alignItems": "center",
                "justifyContent": "center", "fontSize": "25px",
                "color": "#555", "margin": "1px",
            }
        )
    return html.Button(
        symbol,
        id={"type": "element-btn", "index": symbol},
        n_clicks=0,
        style={
            "flex": "1", "aspectRatio": "1",
            "margin": "1px", "padding": "0",
            "fontWeight": "bold", "fontSize": "25px",
            "border": "1.5px solid #888",
            "borderRadius": "5px",
            "cursor": "pointer",
            "backgroundColor": "#ffffff",
            "color": "#111",
        }
    )


def make_pt_grid():
    rows = []
    for row in periodic_table:
        cells = [make_element_button(sym) for sym in row]
        rows.append(
            html.Div(cells, style={"display": "flex", "flexWrap": "nowrap",
                                   "width": "100%", "marginBottom": "2px"})
        )
    return html.Div(rows)


def make_legend():
    items = [
        (SHELL_COLORS["K"], "K"),
        (SHELL_COLORS["L"], "L"),
        (SHELL_COLORS["M"], "M"),
        ("#ffffff", "Unreachable"),
    ]
    chips = []
    for color, label in items:
        chips.append(
            html.Div([
                html.Div(style={
                    "width": "34px", "height": "24px",
                    "backgroundColor": color,
                    "border": "1px solid #555",
                    "borderRadius": "3px",
                    "display": "inline-block",
                    "marginRight": "8px",
                    "verticalAlign": "middle",
                }),
                html.Span(label, style={"fontSize": "18px", "verticalAlign": "middle"}),
            ], style={"display": "inline-flex", "alignItems": "center",
                      "marginRight": "20px"})
        )
    return html.Div(chips, style={"display": "flex", "flexWrap": "wrap",
                                  "padding": "6px 0"})


# ── Full tab layout ──────────────────────────────────────────────────────────

layout = dbc.Container(
    fluid=True,
    className="mt-3",
    children=[
        # Store: keeps selected element and energy range across tab switches
        dcc.Store(id="ptable-store", data={"selected": None, "emin": 2100, "emax": 5500}),

        dbc.Row([

            # ── LEFT COLUMN: controls + legend + periodic table ──────────────
            dbc.Col(width=9, children=[

                # Energy range controls + color legend
                dbc.Card(dbc.CardBody([
                    html.Div([
                        html.Div([
                            html.Span("Energy Range (eV)",
                                      style={"fontWeight": "bold", "marginRight": "20px",
                                             "fontSize": "14px"}),
                            html.Span("Min:", style={"marginRight": "5px"}),
                            dcc.Input(id="pt-emin", type="number", value=2100,
                                      min=0, max=100000, step=10,
                                      style={"width": "90px", "marginRight": "20px"}),
                            html.Span("Max:", style={"marginRight": "5px"}),
                            dcc.Input(id="pt-emax", type="number", value=5500,
                                      min=0, max=100000, step=10,
                                      style={"width": "90px"}),
                        ], style={"display": "flex", "alignItems": "center"}),
                        make_legend(),
                    ], style={"display": "flex", "alignItems": "center",
                              "justifyContent": "space-between", "flexWrap": "wrap"}),
                ]), className="mb-2 py-1"),

                # Periodic table grid
                dbc.Card(dbc.CardBody(
                    html.Div(id="pt-grid", children=make_pt_grid())
                ), className="mb-2"),
            ]),

            # ── RIGHT COLUMN: element detail panel ──────────────────────────
            dbc.Col(width=3, children=[

                # Element Details card
                dbc.Card([
                    dbc.CardHeader("Element Details",
                                   style={"fontWeight": "bold", "fontSize": "15px"}),
                    dbc.CardBody(
                        html.Div(id="pt-detail-panel", children=[
                            html.Div("Click an element to see details.",
                                     style={"color": "#888", "fontSize": "13px"})
                        ]),
                        style={"minHeight": "380px"}
                    ),
                ], className="mb-3"),

                # Headroom card -- K/L/M eV headroom + equivalent k for the
                # current energy range, independent of which shell drives
                # the grid tile's color.
                dbc.Card([
                    dbc.CardHeader("Headroom",
                                   style={"fontWeight": "bold", "fontSize": "15px"}),
                    dbc.CardBody(
                        html.Div(id="pt-headroom-panel", children=[
                            html.Div("Click an element to see headroom details.",
                                     style={"color": "#888", "fontSize": "13px"})
                        ]),
                    ),
                ], className="mb-3"),

                # Notes card
                dbc.Card([
                    dbc.CardHeader("Notes",
                                   style={"fontWeight": "bold", "fontSize": "15px"}),
                    dbc.CardBody([
                        html.Div(id="pt-notes-panel", children=[
                            html.Div("", style={"color": "#666", "fontSize": "13px"})
                        ]),
                        dcc.Textarea(
                            id="pt-notes-input",
                            placeholder="Add a note for this element...",
                            style={"width": "100%", "height": "60px",
                                   "fontSize": "13px", "marginTop": "10px"},
                        ),
                        dbc.Button("Add Note", id="pt-notes-add-btn", size="sm",
                                   color="primary", className="mt-1", n_clicks=0),
                    ], style={"minHeight": "120px"}),
                ]),

            ]),
        ]),
    ],
)

