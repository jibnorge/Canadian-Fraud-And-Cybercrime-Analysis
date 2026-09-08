"""
Canadian Fraud and Cybercrime Analysis Dashboard

Run with:
    python dashboard.py

Then open http://127.0.0.1:8050 in a browser.

All KPIs and all four charts are driven by one shared filter bar
(Category, Province, Gender, Date Range) — changing any filter recomputes
every KPI and every chart against the same filtered slice of data.
"""

import json
import urllib.request

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output

# ---------------------------------------------------------------------------
# Data loading & cleaning (mirrors analysis.ipynb)
# ---------------------------------------------------------------------------

CSV_PATH = "cafc-open-gouv-database-2021-01-01-to-2025-09-30-extracted-2025-10-01.csv"

data = pd.read_csv(CSV_PATH)

data.columns = [
    "Number ID", "Date Received",
    "Complaint Received Type", "Country", "Province",
    "Fraud and Cybercrime Thematic Categories", "Solicitation Method",
    "Gender", "Language of Correspondence",
    "Victim Age Range", "Complaint Type",
    "Number of Victims",
    "Dollar Loss",
]

data["Date Received"] = pd.to_datetime(data["Date Received"])
data["Victim Age Range"] = data["Victim Age Range"].str.strip("'")
data["Dollar Loss"] = (
    data["Dollar Loss"].astype(str).str.strip("$").str.replace(",", "").astype(float)
)

data["Country"].replace({
    "Bolivia, Plurinational State of": "Bolivia",
    "Congo, The Democratic Republic of the": "Congo",
    "France, Metropolitan": "France",
    "Iran, Islamic Republic of": "Iran",
    "Korea, Republic of": "South Korea",
    "Macedonia, The Former Yugoslav Republic of": "Macedonia",
    "Palestinian Territory, Occupied": "Palestinian",
    "Taiwan, Province of China": "Taiwan",
    "Tanzania, United Republic of": "Tanzania",
    "United States Minor Outlying Islands": "Others",
    "Not Specified": "Others",
    "Unknown": "Others",
    "Venezuela, Bolivarian Republic of": "Venezuela",
    "Viet Nam": "Vietnam",
    "Virgin Islands, British": "British Virgin Islands",
}, inplace=True)

data["Province"].replace("Not Specified", "Others", inplace=True)

# Fix two known mis-tagged US records (see analysis.ipynb)
mis_tagged_idx = data[
    (data["Country"] == "Canada")
    & (data["Province"].isin(["California", "Northern Mariana Islands"]))
].index
data.loc[mis_tagged_idx, "Country"] = "United States"

data["Quarter Date Received"] = data["Date Received"].dt.to_period("q").astype(str)

CATEGORY_COL = "Fraud and Cybercrime Thematic Categories"

CANADA_ZIP_MAP = {
    "Ontario": "ON", "Quebec": "QC", "Nova Scotia": "NS", "New Brunswick": "NB",
    "Manitoba": "MB", "British Columbia": "BC", "Prince Edward Island": "PE",
    "Saskatchewan": "SK", "Alberta": "AB", "Newfoundland And Labrador": "NL",
    "North West Territories": "NT", "Yukon": "YT", "Nunavut": "NU",
}
GEO_NAME_FIX = {
    "North West Territories": "Northwest Territories",
    "Yukon": "Yukon Territory",
    "Newfoundland And Labrador": "Newfoundland and Labrador",
}

GEOJSON_URL = (
    "https://raw.githubusercontent.com/codeforamerica/click_that_hood/"
    "master/public/data/canada.geojson"
)
try:
    with urllib.request.urlopen(GEOJSON_URL, timeout=10) as response:
        canada_geojson = json.loads(response.read().decode())
except Exception:
    canada_geojson = None

# ---------------------------------------------------------------------------
# Filter options / defaults
# ---------------------------------------------------------------------------

category_options = data[CATEGORY_COL].value_counts().index.tolist()
default_categories = category_options[:5]

province_options = list(CANADA_ZIP_MAP.keys()) + ["Others"]

gender_options = sorted(data["Gender"].dropna().unique().tolist())

min_date = data["Date Received"].min().date()
max_date = data["Date Received"].max().date()

# ---------------------------------------------------------------------------
# Filtering helper — every KPI and every chart reads from this
# ---------------------------------------------------------------------------


def filter_data(categories, provinces, genders, start_date, end_date):
    df = data
    if start_date:
        df = df[df["Date Received"] >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df["Date Received"] <= pd.to_datetime(end_date)]
    if categories:
        df = df[df[CATEGORY_COL].isin(categories)]
    if provinces:
        df = df[df["Province"].isin(provinces)]
    if genders:
        df = df[df["Gender"].isin(genders)]
    return df


# ---------------------------------------------------------------------------
# Dash app
# ---------------------------------------------------------------------------

app = Dash(__name__)
app.title = "Canadian Fraud & Cybercrime Dashboard"
server = app.server

COLORS = {
    "bg": "#0f1420",
    "panel": "#1a2133",
    "text": "#e8ecf5",
    "muted": "#8f9bb3",
    "accent": "#4f8dff",
}

BASE_LAYOUT = dict(
    paper_bgcolor=COLORS["panel"],
    plot_bgcolor=COLORS["panel"],
    font_color=COLORS["text"],
    margin=dict(l=40, r=20, t=20, b=40),
    legend=dict(bgcolor="rgba(0,0,0,0)"),
)


def kpi_card(title, value_id, subtitle=None):
    children = [
        html.Div(title, className="kpi-title"),
        html.Div(id=value_id, className="kpi-value"),
    ]
    if subtitle:
        children.append(html.Div(subtitle, className="kpi-subtitle"))
    return html.Div(children, className="kpi-card")


def empty_figure(message):
    fig = go.Figure()
    fig.update_layout(
        **BASE_LAYOUT,
        xaxis={"visible": False},
        yaxis={"visible": False},
        annotations=[dict(text=message, showarrow=False, font=dict(color=COLORS["muted"]))],
    )
    return fig


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

app.layout = html.Div(
    className="app-container",
    children=[
        html.Div(
            className="header",
            children=[
                html.H1("Canadian Fraud & Cybercrime Analysis"),
                html.P("CAFC Open Government Data — 2021-01-01 to 2025-09-30"),
            ],
        ),
        html.Div(
            className="filter-bar",
            children=[
                html.Div(
                    className="filter-control",
                    children=[
                        html.Label("Fraud Category"),
                        dcc.Dropdown(
                            id="category-filter",
                            options=[{"label": c, "value": c} for c in category_options],
                            value=default_categories,
                            multi=True,
                            placeholder="All categories",
                            className="dropdown",
                        ),
                    ],
                ),
                html.Div(
                    className="filter-control",
                    children=[
                        html.Label("Province"),
                        dcc.Dropdown(
                            id="province-filter",
                            options=[{"label": p, "value": p} for p in province_options],
                            value=[],
                            multi=True,
                            placeholder="All provinces",
                            className="dropdown",
                        ),
                    ],
                ),
                html.Div(
                    className="filter-control",
                    children=[
                        html.Label("Gender"),
                        dcc.Dropdown(
                            id="gender-filter",
                            options=[{"label": g, "value": g} for g in gender_options],
                            value=[],
                            multi=True,
                            placeholder="All genders",
                            className="dropdown",
                        ),
                    ],
                ),
                html.Div(
                    className="filter-control",
                    children=[
                        html.Label("Date Received"),
                        dcc.DatePickerRange(
                            id="date-filter",
                            min_date_allowed=min_date,
                            max_date_allowed=max_date,
                            start_date=min_date,
                            end_date=max_date,
                            display_format="YYYY-MM-DD",
                        ),
                    ],
                ),
                html.Button("Reset Filters", id="reset-filters", n_clicks=0, className="reset-btn"),
            ],
        ),
        html.Div(
            className="kpi-row",
            children=[
                kpi_card("Median Dollar Loss", "kpi-median-loss", "Excludes $0 loss records"),
                kpi_card("Fraud Types", "kpi-fraud-types", "Distinct thematic categories in view"),
                kpi_card("Total Victims", "kpi-total-victims", "Sum of reported victims in view"),
            ],
        ),
        html.Div(
            className="grid-2x2",
            children=[
                html.Div(
                    className="panel",
                    children=[
                        html.H3("Cybercrime Attempts by Category Over Time"),
                        dcc.Graph(id="attempts-over-time", config={"displayModeBar": False}),
                    ],
                ),
                html.Div(
                    className="panel",
                    children=[
                        html.H3("Dollar Loss by Category Over Time"),
                        dcc.Graph(id="stacked-area-loss", config={"displayModeBar": False}),
                    ],
                ),
                html.Div(
                    className="panel",
                    children=[
                        html.H3("Median Dollar Loss by Province"),
                        dcc.Graph(id="province-map", config={"displayModeBar": False}),
                    ],
                ),
                html.Div(
                    className="panel",
                    children=[
                        html.H3("Victim Age Range by Gender"),
                        dcc.Graph(id="age-gender-plot", config={"displayModeBar": False}),
                    ],
                ),
            ],
        ),
    ],
)


# ---------------------------------------------------------------------------
# Reset button -> clears every filter control
# ---------------------------------------------------------------------------

@app.callback(
    Output("category-filter", "value"),
    Output("province-filter", "value"),
    Output("gender-filter", "value"),
    Output("date-filter", "start_date"),
    Output("date-filter", "end_date"),
    Input("reset-filters", "n_clicks"),
    prevent_initial_call=True,
)
def reset_filters(_):
    return default_categories, [], [], min_date, max_date


# ---------------------------------------------------------------------------
# Main callback — one filtered dataframe feeds every KPI and every chart
# ---------------------------------------------------------------------------

@app.callback(
    Output("kpi-median-loss", "children"),
    Output("kpi-fraud-types", "children"),
    Output("kpi-total-victims", "children"),
    Output("attempts-over-time", "figure"),
    Output("stacked-area-loss", "figure"),
    Output("province-map", "figure"),
    Output("age-gender-plot", "figure"),
    Input("category-filter", "value"),
    Input("province-filter", "value"),
    Input("gender-filter", "value"),
    Input("date-filter", "start_date"),
    Input("date-filter", "end_date"),
)
def update_dashboard(categories, provinces, genders, start_date, end_date):
    df = filter_data(categories, provinces, genders, start_date, end_date)

    # ---- KPIs ----
    nonzero_loss = df.loc[df["Dollar Loss"] != 0, "Dollar Loss"]
    median_loss = nonzero_loss.median() if not nonzero_loss.empty else 0
    fraud_types = df[CATEGORY_COL].nunique()
    total_victims = int(df["Number of Victims"].sum())

    kpi_median = f"${median_loss:,.2f}"
    kpi_types = f"{fraud_types:,}"
    kpi_victims = f"{total_victims:,}"

    if df.empty:
        no_data = empty_figure("No records match the current filters")
        return kpi_median, kpi_types, kpi_victims, no_data, no_data, no_data, no_data

    # ---- Shared time axis (respects the date filter) ----
    quarters_axis = sorted(df["Quarter Date Received"].unique())

    # ---- Attempts by category over time ----
    cats_for_trend = categories if categories else df[CATEGORY_COL].value_counts().nlargest(5).index.tolist()
    fig_attempts = go.Figure()
    for cat in cats_for_trend:
        sub = (
            df[df[CATEGORY_COL] == cat]["Quarter Date Received"]
            .value_counts()
            .reindex(quarters_axis, fill_value=0)
            .sort_index()
        )
        fig_attempts.add_trace(go.Scatter(x=quarters_axis, y=sub.values, mode="lines+markers", name=cat))
    fig_attempts.update_layout(**BASE_LAYOUT, xaxis_title="Quarter", yaxis_title="Number of Attempts")
    fig_attempts.update_xaxes(tickangle=45)

    # ---- Stacked area: dollar loss by category over time ----
    if categories:
        cats_for_area = categories
    else:
        cats_for_area = (
            df[df["Dollar Loss"] != 0].groupby(CATEGORY_COL)["Dollar Loss"].mean().nlargest(5).index.tolist()
        )
    fig_area = go.Figure()
    for cat in cats_for_area:
        sub = (
            df[(df[CATEGORY_COL] == cat) & (df["Dollar Loss"] != 0)]
            .groupby("Quarter Date Received")["Dollar Loss"]
            .mean()
            .reindex(quarters_axis)
            .fillna(0)
        )
        fig_area.add_trace(
            go.Scatter(x=quarters_axis, y=sub.values, mode="lines", stackgroup="one", name=cat)
        )
    fig_area.update_layout(**BASE_LAYOUT, xaxis_title="Quarter", yaxis_title="Avg Dollar Loss ($)")
    fig_area.update_xaxes(tickangle=45)

    # ---- Province choropleth ----
    if canada_geojson is None:
        fig_map = empty_figure("Map data unavailable (no internet access)")
    else:
        canada_df = df[(df["Country"] == "Canada") & (df["Province"].isin(CANADA_ZIP_MAP.keys()))]
        loss_by_province = (
            canada_df[canada_df["Dollar Loss"] != 0].groupby("Province")["Dollar Loss"].median()
        )
        province_summary = pd.DataFrame({"Province": list(CANADA_ZIP_MAP.keys())})
        province_summary["Dollar Loss"] = province_summary["Province"].map(loss_by_province).fillna(0)
        province_summary["Abbreviation"] = province_summary["Province"].map(CANADA_ZIP_MAP)
        province_summary["Formatted Loss"] = province_summary["Dollar Loss"].apply(lambda x: f"${x:,.2f}")
        province_summary["GeoName"] = province_summary["Province"].replace(GEO_NAME_FIX)

        fig_map = px.choropleth(
            province_summary,
            geojson=canada_geojson,
            locations="GeoName",
            featureidkey="properties.name",
            color="Dollar Loss",
            hover_name="Province",
            hover_data={"Abbreviation": True, "Dollar Loss": False, "Formatted Loss": True, "GeoName": False},
            color_continuous_scale="Blues",
            labels={"Dollar Loss": "Median Loss ($ CAD)"},
        )
        fig_map.update_geos(visible=False, projection_type="conic conformal", fitbounds="locations")
        map_layout = {**BASE_LAYOUT, "margin": dict(l=0, r=0, t=0, b=0)}
        fig_map.update_layout(**map_layout)

    # ---- Victim age range by gender ----
    age_sub = df[
        (df["Victim Age Range"] != "Not Available / non disponible") & (~df["Victim Age Range"].isna())
    ]
    if age_sub.empty:
        fig_age = empty_figure("No victim age data for current filters")
    else:
        counts = age_sub.groupby(["Victim Age Range", "Gender"]).size().reset_index(name="Count")
        fig_age = px.bar(
            counts,
            x="Count",
            y="Victim Age Range",
            color="Gender",
            orientation="h",
            barmode="group",
        )
        fig_age.update_layout(**BASE_LAYOUT, xaxis_title="Number of Victims", yaxis_title="Victim Age Range")
        fig_age.update_yaxes(categoryorder="total ascending")

    return kpi_median, kpi_types, kpi_victims, fig_attempts, fig_area, fig_map, fig_age


if __name__ == "__main__":
    app.run(debug=True)
