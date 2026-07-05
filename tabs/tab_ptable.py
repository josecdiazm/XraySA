
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

def get_tile_color(symbol, e_min, e_max):
    sym = symbol.replace("*", "")
    if not sym:
        return "#f0f0f0"
    try:
        edges = xraydb.xray_edges(sym)
    except Exception:
        return "#ffffff"
    K  = edges.get("K")
    L1 = edges.get("L1")
    L2 = edges.get("L2")
    L3 = edges.get("L3")
    if K and e_min <= K.energy <= e_max and (K.energy + 500) <= e_max:
        return "#3fbf8a"          # mediumaquamarine – K EXAFS
    if L1 and e_min <= L1.energy <= e_max and (L1.energy + 500) <= e_max:
        return "#87ceeb"          # skyblue – L1 EXAFS
    K_X  = K  and e_min <= K.energy  <= e_max and (K.energy  + 150) <= e_max
    L1_X = L1 and e_min <= L1.energy <= e_max and (L1.energy + 150) <= e_max
    L2_X = L2 and e_min <= L2.energy <= e_max and (L2.energy + 150) <= e_max
    L3_X = L3 and e_min <= L3.energy <= e_max and (L3.energy + 150) <= e_max
    if any([K_X, L1_X, L2_X, L3_X]):
        return "#f5deb3"          # wheat – XANES
    return "#ffffff"              # white – cannot reach

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
        ("#3fbf8a", "K – EXAFS"),
        ("#87ceeb", "L₁ – EXAFS"),
        ("#f5deb3", "K, L₁, L₂, L₃ — XANES"),
        ("#ffffff", "Cannot Reach"),
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

                # Energy range controls
                dbc.Card(dbc.CardBody([
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
                ]), className="mb-2 py-1"),

                # Color legend
                dbc.Card(dbc.CardBody(make_legend()), className="mb-2 py-1"),

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

