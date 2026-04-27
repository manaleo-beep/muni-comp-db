import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from pathlib import Path

DB = "muni_comp.db"

# ---------- DB SETUP ----------
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS municipalities(
        id INTEGER PRIMARY KEY,
        name TEXT, state TEXT, county TEXT,
        population INTEGER, form_of_government TEXT,
        fiscal_year INTEGER, median_hh_income INTEGER,
        grand_list REAL, fte_count INTEGER,
        UNIQUE(name, state, fiscal_year));
    CREATE TABLE IF NOT EXISTS positions(
        id INTEGER PRIMARY KEY,
        standard_title TEXT UNIQUE,
        job_family TEXT, flsa_status TEXT);
    CREATE TABLE IF NOT EXISTS position_aliases(
        id INTEGER PRIMARY KEY,
        position_id INTEGER,
        alias_title TEXT,
        UNIQUE(alias_title),
        FOREIGN KEY(position_id) REFERENCES positions(id));
    CREATE TABLE IF NOT EXISTS compensation(
        id INTEGER PRIMARY KEY,
        municipality_id INTEGER,
        position_id INTEGER,
        fiscal_year INTEGER,
        min_salary REAL, mid_salary REAL, max_salary REAL,
        actual_salary REAL, hourly_rate REAL, hours_per_week REAL,
        benefits_pct REAL, total_comp REAL,
        FOREIGN KEY(municipality_id) REFERENCES municipalities(id),
        FOREIGN KEY(position_id) REFERENCES positions(id));
    """)
    # Seed standard positions
    seed = [
        ("Town Manager","Administration","Exempt"),
        ("Town Administrator","Administration","Exempt"),
        ("Assistant Town Manager","Administration","Exempt"),
        ("Town Clerk","Clerk","Exempt"),
        ("Finance Director","Finance","Exempt"),
        ("Treasurer","Finance","Exempt"),
        ("Accountant","Finance","Non-Exempt"),
        ("Police Chief","Police","Exempt"),
        ("Police Sergeant","Police","Non-Exempt"),
        ("Police Officer","Police","Non-Exempt"),
        ("Fire Chief","Fire","Exempt"),
        ("Firefighter/EMT","Fire","Non-Exempt"),
        ("DPW Director","Public Works","Exempt"),
        ("Highway Foreman","Public Works","Non-Exempt"),
        ("Equipment Operator","Public Works","Non-Exempt"),
        ("Water/Wastewater Operator","Public Works","Non-Exempt"),
        ("Planner","Planning","Exempt"),
        ("Zoning Administrator","Planning","Non-Exempt"),
        ("Library Director","Library","Exempt"),
        ("Recreation Director","Recreation","Exempt"),
        ("Assessor","Assessing","Exempt"),
    ]
    for t,f,fl in seed:
        c.execute("INSERT OR IGNORE INTO positions(standard_title,job_family,flsa_status) VALUES(?,?,?)",(t,f,fl))
    # Seed common aliases
    aliases = [
        ("Town Manager","City Manager"),("Town Manager","Town Manager/Administrator"),
        ("Town Administrator","Selectboard Administrator"),
        ("DPW Director","Public Works Director"),("DPW Director","Highway Superintendent"),
        ("Highway Foreman","Road Foreman"),("Highway Foreman","Road Commissioner"),
        ("Police Officer","Patrol Officer"),("Police Officer","Patrolman"),
        ("Firefighter/EMT","Firefighter"),("Firefighter/EMT","FF/EMT"),
        ("Finance Director","Director of Finance"),("Finance Director","Business Manager"),
        ("Town Clerk","Town Clerk/Treasurer"),
        ("Zoning Administrator","Code Enforcement Officer"),("Zoning Administrator","ZA"),
    ]
    for std, alias in aliases:
        c.execute("SELECT id FROM positions WHERE standard_title=?",(std,))
        pid = c.fetchone()[0]
        c.execute("INSERT OR IGNORE INTO position_aliases(position_id,alias_title) VALUES(?,?)",(pid,alias))
    conn.commit(); conn.close()

def q(sql, params=()):
    conn = sqlite3.connect(DB)
    df = pd.read_sql(sql, conn, params=params)
    conn.close(); return df

def exec_sql(sql, params=()):
    conn = sqlite3.connect(DB); c = conn.cursor()
    c.execute(sql, params); conn.commit(); rid = c.lastrowid; conn.close(); return rid

# ---------- POSITION MAPPING LOGIC ----------
def map_title_to_position(raw_title):
    """Look up a raw title via aliases -> standard position id."""
    raw = raw_title.strip()
    df = q("SELECT p.id FROM positions p WHERE LOWER(p.standard_title)=LOWER(?)",(raw,))
    if not df.empty: return int(df.iloc[0,0])
    df = q("SELECT position_id FROM position_aliases WHERE LOWER(alias_title)=LOWER(?)",(raw,))
    if not df.empty: return int(df.iloc[0,0])
    return None

# ---------- UI ----------
st.set_page_config(page_title="Municipal Compensation DB — VT/NH/ME", layout="wide")
init_db()

st.title("🏛️ Municipal Compensation Database")
st.caption("Vermont • New Hampshire • Maine — comparative wage & benefits data")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📤 Upload Data","🔍 Compare Municipalities","📊 Position Benchmark","🔗 Title Mapping","📋 Browse Raw Data"])

# ---- TAB 1: UPLOAD ----
def safe_str(v):
    if v is None: return None
    if isinstance(v, float) and pd.isna(v): return None
    return str(v).strip() or None

def safe_int(v, default=None):
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)): return default
        return int(float(v))
    except (ValueError, TypeError):
        return default

def safe_float(v, default=None):
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)): return default
        return float(v)
    except (ValueError, TypeError):
        return default

with tab1:
    st.header("Upload Excel / CSV Compensation File")
    st.markdown("""
    **Required columns:** `municipality`, `state`, `fiscal_year`, `position_title`, `actual_salary`  
    **Optional:** `population, min_salary, max_salary, hourly_rate, hours_per_week, benefits_pct, total_comp, county, form_of_government`
    
    *Column names are case-insensitive. Spaces are auto-converted to underscores.*
    """)
    up = st.file_uploader("Choose Excel/CSV file", type=["xlsx","xls","csv"])

    if up:
        try:
            if up.name.lower().endswith(".csv"):
                df = pd.read_csv(up)
            else:
                df = pd.read_excel(up, engine="openpyxl")
        except Exception as e:
            st.error(f"❌ Could not read file: {e}")
            st.stop()

        # Normalize column names
        df.columns = [str(c).lower().strip().replace(" ","_").replace("-","_") for c in df.columns]
        # Drop fully empty rows
        df = df.dropna(how="all").reset_index(drop=True)

        # Validate required columns
        required = {"municipality","state","fiscal_year","position_title","actual_salary"}
        missing = required - set(df.columns)
        if missing:
            st.error(f"❌ Missing required column(s): {missing}")
            st.write("Columns found in your file:", list(df.columns))
            st.stop()

        st.success(f"✅ File parsed. {len(df)} data rows detected.")
        st.dataframe(df.head(10))

        if st.button("🚀 Import to Database"):
            inserted, skipped, unmapped = 0, [], []
            errors = []
            progress = st.progress(0)

            for i, r in df.iterrows():
                progress.progress((i+1)/len(df))
                try:
                    muni = safe_str(r.get("municipality"))
                    state = safe_str(r.get("state"))
                    fy = safe_int(r.get("fiscal_year"), 2024)
                    title = safe_str(r.get("position_title"))
                    salary = safe_float(r.get("actual_salary"))

                    # Skip rows missing the essentials
                    if not muni or not state or not title:
                        skipped.append(f"Row {i+2}: missing muni/state/title")
                        continue

                    # Insert/find municipality
                    exec_sql("""INSERT OR IGNORE INTO municipalities
                        (name,state,fiscal_year,population,county,form_of_government)
                        VALUES(?,?,?,?,?,?)""",
                        (muni, state, fy,
                         safe_int(r.get("population"), 0),
                         safe_str(r.get("county")),
                         safe_str(r.get("form_of_government"))))
                    row = q("SELECT id FROM municipalities WHERE name=? AND state=? AND fiscal_year=?",
                            (muni, state, fy))
                    if row.empty:
                        errors.append(f"Row {i+2}: could not create/find municipality '{muni}'")
                        continue
                    mid = int(row.iloc[0,0])

                    # Map title → standard position
                    pid = map_title_to_position(title)
                    if pid is None:
                        unmapped.append(title)
                        continue

                    exec_sql("""INSERT INTO compensation
                        (municipality_id,position_id,fiscal_year,min_salary,max_salary,
                         actual_salary,hourly_rate,hours_per_week,benefits_pct,total_comp)
                        VALUES(?,?,?,?,?,?,?,?,?,?)""",
                        (mid, pid, fy,
                         safe_float(r.get("min_salary")),
                         safe_float(r.get("max_salary")),
                         salary,
                         safe_float(r.get("hourly_rate")),
                         safe_float(r.get("hours_per_week")),
                         safe_float(r.get("benefits_pct")),
                         safe_float(r.get("total_comp"))))
                    inserted += 1
                except Exception as e:
                    errors.append(f"Row {i+2}: {e}")

            progress.empty()
            st.success(f"✅ Imported {inserted} rows.")
            if skipped:
                with st.expander(f"⚠️ Skipped {len(skipped)} rows (missing required data)"):
                    for s in skipped[:50]: st.text(s)
            if unmapped:
                unique_unmapped = sorted(set(unmapped))
                with st.expander(f"🔗 {len(unique_unmapped)} unmapped position titles — add these in the Mapping tab"):
                    for t in unique_unmapped: st.text(f"• {t}")
            if errors:
                with st.expander(f"❌ {len(errors)} errors"):
                    for e in errors[:50]: st.text(e)

# ---- TAB 2: COMPARE ----
with tab2:
    st.header("Compare Municipalities Side-by-Side")
    munis = q("SELECT DISTINCT name||' ('||state||')' AS label, id FROM municipalities ORDER BY name")
    if munis.empty:
        st.info("Upload data first.")
    else:
        sel = st.multiselect("Select municipalities", munis["label"].tolist())
        if sel:
            ids = munis[munis["label"].isin(sel)]["id"].tolist()
            ph = ",".join("?"*len(ids))
            df = q(f"""SELECT m.name||' ('||m.state||')' AS Municipality,
                              p.standard_title AS Position,
                              c.actual_salary, c.total_comp, c.benefits_pct
                       FROM compensation c
                       JOIN municipalities m ON m.id=c.municipality_id
                       JOIN positions p ON p.id=c.position_id
                       WHERE m.id IN ({ph})""", ids)
            pivot = df.pivot_table(index="Position", columns="Municipality",
                                   values="actual_salary", aggfunc="mean")
            st.subheader("Actual Salary Comparison")
            st.dataframe(pivot.style.format("${:,.0f}"))
            fig = px.bar(df, x="Position", y="actual_salary", color="Municipality",
                         barmode="group", title="Salary by Position")
            st.plotly_chart(fig, use_container_width=True)

# ---- TAB 3: BENCHMARK ----
with tab3:
    st.header("Position Benchmark Analysis")
    pos = q("SELECT id, standard_title FROM positions ORDER BY standard_title")
    if not pos.empty:
        choice = st.selectbox("Position", pos["standard_title"])
        pid = int(pos[pos["standard_title"]==choice]["id"].iloc[0])
        states = st.multiselect("States", ["VT","NH","ME"], default=["VT","NH","ME"])
        if states:
            ph = ",".join("?"*len(states))
            df = q(f"""SELECT m.name AS Municipality, m.state, m.population,
                              c.actual_salary, c.total_comp
                       FROM compensation c
                       JOIN municipalities m ON m.id=c.municipality_id
                       WHERE c.position_id=? AND m.state IN ({ph})""",
                   [pid]+states)
            if not df.empty:
                col1,col2,col3,col4 = st.columns(4)
                col1.metric("N", len(df))
                col2.metric("Median", f"${df['actual_salary'].median():,.0f}")
                col3.metric("25th %ile", f"${df['actual_salary'].quantile(.25):,.0f}")
                col4.metric("75th %ile", f"${df['actual_salary'].quantile(.75):,.0f}")
                st.dataframe(df)
                fig = px.scatter(df, x="population", y="actual_salary", color="state",
                                 hover_name="Municipality", trendline="ols",
                                 title=f"{choice}: Salary vs Population")
                st.plotly_chart(fig, use_container_width=True)

# ---- TAB 4: MAPPING ----
with tab4:
    st.header("Position Title Mapping")
    st.caption("Map a town's local title (e.g. 'Road Commissioner') to a standard title.")
    pos = q("SELECT id, standard_title FROM positions ORDER BY standard_title")
    with st.form("map"):
        alias = st.text_input("Local/Alias Title")
        std = st.selectbox("Maps to Standard Title", pos["standard_title"])
        if st.form_submit_button("Add Mapping"):
            pid = int(pos[pos["standard_title"]==std]["id"].iloc[0])
            exec_sql("INSERT OR IGNORE INTO position_aliases(position_id,alias_title) VALUES(?,?)",(pid,alias))
            st.success(f"Mapped '{alias}' → '{std}'")
    st.subheader("Current Mappings")
    st.dataframe(q("""SELECT a.alias_title AS Alias, p.standard_title AS Standard
                      FROM position_aliases a JOIN positions p ON p.id=a.position_id
                      ORDER BY p.standard_title"""))

# ---- TAB 5: BROWSE ----
with tab5:
    st.header("All Compensation Records")
    df = q("""SELECT m.name AS Municipality, m.state, m.fiscal_year,
                     p.standard_title AS Position, p.job_family,
                     c.actual_salary, c.total_comp, c.benefits_pct
              FROM compensation c
              JOIN municipalities m ON m.id=c.municipality_id
              JOIN positions p ON p.id=c.position_id
              ORDER BY m.state, m.name""")
    st.dataframe(df, use_container_width=True)
    st.download_button("Download CSV", df.to_csv(index=False), "compensation_export.csv")