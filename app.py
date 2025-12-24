import streamlit as st
import pandas as pd
import requests
import altair as alt
from datetime import datetime

# --- SECTION 1: APP CONFIGURATION ---
st.set_page_config(page_title="NUSGPA Calculator", layout="wide")

# Define grade-to-point mapping
grade_map = {
    "A+": 5.0, "A": 5.0, "A-": 4.5,
    "B+": 4.0, "B": 3.5, "B-": 3.0,
    "C+": 2.5, "C": 2.0, "D+": 1.5,
    "D": 1.0, "F": 0.0
}

# --- SECTION 2: API INTEGRATION & HELPER UTILITIES ---

def get_current_acad_year():
    """Determines the current academic year based on the system date."""
    now = datetime.now()
    year = now.year
    if now.month >= 6: return f"{year}-{year+1}"
    else: return f"{year-1}-{year}"

def get_ay_options():
    """Generates a list of academic years for the dropdown selector."""
    current = get_current_acad_year()
    start_year = int(current.split("-")[0])
    years = []
    for y in range(start_year - 4, start_year + 2): years.append(f"{y}-{y+1}")
    return sorted(years, reverse=True), current

@st.cache_data(show_spinner=False)
def get_nus_module_list(acad_year):
    """Fetches the complete module list from NUSMods API for the specified AY."""
    url = f"https://api.nusmods.com/v2/{acad_year}/moduleList.json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data)
        df["display_label"] = df["moduleCode"] + ": " + df["title"]
        return df
    except Exception: return pd.DataFrame()

@st.cache_data(show_spinner=False)
def get_module_credits(acad_year, module_code):
    """Retrieves credit information for a specific module."""
    url = f"https://api.nusmods.com/v2/{acad_year}/modules/{module_code}.json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return float(data.get("moduleCredit", 4.0))
    except Exception: return 4.0

# --- SECTION 3: SESSION STATE MANAGEMENT ---

if "courses" not in st.session_state:
    st.session_state.courses = pd.DataFrame(columns=["Course Name", "Semester", "Grade", "Credits", "SU_Opt_Out"])
if "uploader_id" not in st.session_state: st.session_state.uploader_id = 0

keys_defaults = {"course_name_input": "", "credits_input": 4.0, "search_selection": None, "sem_input": 1, "grade_input": "A", "su_input": False}
for key, default in keys_defaults.items():
    if key not in st.session_state: st.session_state[key] = default

# --- SECTION 4: EVENT HANDLERS (CALLBACKS) ---

def on_module_select():
    """Updates input fields when a module is selected from the search dropdown."""
    selection = st.session_state.search_selection
    if selection and not modules_df.empty:
        row = modules_df[modules_df["display_label"] == selection].iloc[0]
        code = row["moduleCode"]
        st.session_state.course_name_input = code
        st.session_state.credits_input = get_module_credits(selected_ay, code)

def add_course_callback():
    """Commits the input form data to the session state DataFrame."""
    name = st.session_state.course_name_input
    sem = st.session_state.sem_input
    grade = st.session_state.grade_input
    credits = st.session_state.credits_input
    su = st.session_state.su_input
    final_name = name if name else (st.session_state.search_selection if st.session_state.search_selection else "Unknown Course")
    
    new_row = pd.DataFrame([{"Course Name": final_name, "Semester": sem, "Grade": grade, "Credits": credits, "SU_Opt_Out": su}])
    st.session_state.courses = pd.concat([st.session_state.courses, new_row], ignore_index=True)
    
    st.session_state.course_name_input = ""
    st.session_state.search_selection = None

def reset_app_callback():
    """Resets all session data and increments uploader ID to clear file input."""
    st.session_state.courses = pd.DataFrame(columns=["Course Name", "Semester", "Grade", "Credits", "SU_Opt_Out"])
    st.session_state.last_loaded_hash = None
    st.session_state.uploader_id += 1
    st.session_state.course_name_input = ""
    st.session_state.search_selection = None

# --- SECTION 5: SIDEBAR INTERFACE ---

st.sidebar.header("Data & Actions")

# 1. File Upload Logic
unique_uploader_key = f"uploader_{st.session_state.uploader_id}"
uploaded_file = st.sidebar.file_uploader("Load CSV", type=["csv"], key=unique_uploader_key, label_visibility="collapsed")
if uploaded_file is None: st.sidebar.caption("📂 Load History (CSV)")

if uploaded_file is not None:
    file_fingerprint = hash(uploaded_file.getvalue())
    if "last_loaded_hash" not in st.session_state or st.session_state.last_loaded_hash != file_fingerprint:
        try:
            df_uploaded = pd.read_csv(uploaded_file)
            REQUIRED_COLUMNS = {"Course Name", "Semester", "Grade", "Credits", "SU_Opt_Out"}
            
            if not REQUIRED_COLUMNS.issubset(df_uploaded.columns):
                missing = REQUIRED_COLUMNS - set(df_uploaded.columns)
                st.error(f"❌ Invalid File! Missing columns: {', '.join(missing)}")
            else:
                if "SU_Opt_Out" in df_uploaded.columns: df_uploaded["SU_Opt_Out"] = df_uploaded["SU_Opt_Out"].astype(bool)
                st.session_state.courses = df_uploaded
                st.session_state.last_loaded_hash = file_fingerprint
                st.success("Loaded!")
                st.rerun()
        except Exception as e: st.error(f"Error: {e}")

# 2. Data Export Control
if not st.session_state.courses.empty:
    csv_data = st.session_state.courses.to_csv(index=False).encode('utf-8')
    st.sidebar.download_button(
        label="📥 Download CSV", 
        data=csv_data,
        file_name="myNUSGPA.csv", 
        mime="text/csv", 
        use_container_width=True
    )
    st.sidebar.info("Download your CSV to save your progress for next time!")
else:
    st.sidebar.download_button("📥 Download CSV", data="", disabled=True, use_container_width=True)

# 3. System Reset Control
if st.sidebar.button("⚠️ Reset All", on_click=reset_app_callback, type="primary", use_container_width=True): pass

st.sidebar.markdown("---")

# 4. Course Entry Form
with st.sidebar.expander("Add New Course", expanded=True):
    ay_options, default_ay = get_ay_options()
    try: default_index = ay_options.index(default_ay)
    except ValueError: default_index = 0
    selected_ay = st.selectbox("AY Source", options=ay_options, index=default_index, label_visibility="collapsed")
    
    modules_df = get_nus_module_list(selected_ay)
    options_list = modules_df["display_label"].tolist() if not modules_df.empty else []

    st.selectbox("Search", options=options_list, index=None, placeholder="Search (e.g. CS1010)...", key="search_selection", on_change=on_module_select, label_visibility="collapsed")
    st.caption("Or edit details manually:")
    st.text_input("Course Code", key="course_name_input", label_visibility="collapsed", placeholder="Course Code")
    c1, c2 = st.columns([1, 1])
    with c1: st.number_input("Semester", min_value=1, step=1, key="sem_input")
    with c2: st.number_input("Credits", min_value=0.0, step=1.0, key="credits_input")
    c3, c4 = st.columns([1, 1])
    with c3: st.selectbox("Grade", options=list(grade_map.keys()), key="grade_input", label_visibility="collapsed")
    with c4: st.checkbox("Exercise S/U?", key="su_input")
    st.button("Add", on_click=add_course_callback, use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.caption("Data provided by [NUSMods](https://nusmods.com). Not affiliated with NUS.")

# --- SECTION 6: MAIN INTERFACE ---

st.title("NUSGPA Grade Tracker")

st.subheader("Course Record")
edited_df = st.data_editor(
    st.session_state.courses,
    num_rows="dynamic",
    column_config={
        "SU_Opt_Out": st.column_config.CheckboxColumn("SU Option", default=False),
        "Grade": st.column_config.SelectboxColumn("Grade", options=list(grade_map.keys()), required=True),
        "Credits": st.column_config.NumberColumn("Credits", format="%.1f")
    },
    use_container_width=True,
    key="editor" 
)

if not edited_df.equals(st.session_state.courses):
    st.session_state.courses = edited_df
    st.rerun()

# --- SECTION 7: ANALYTICS & VISUALIZATION (SIDE-BY-SIDE) ---

if not st.session_state.courses.empty:
    df = st.session_state.courses.copy()
    
    # Compute Weighted Scores
    df["Grade Value"] = df["Grade"].map(grade_map)
    df["Calc_Credits"] = df.apply(lambda x: 0 if x["SU_Opt_Out"] else x["Credits"], axis=1)
    df["Quality_Points"] = df["Grade Value"] * df["Calc_Credits"]
    
    # Aggregate Data
    summary = df.groupby("Semester").apply(
        lambda x: pd.Series({
            "Term Credits": x["Calc_Credits"].sum(),
            "Term Points": x["Quality_Points"].sum()
        }), include_groups=False
    ).reset_index()
    
    summary["Sem GPA"] = (summary["Term Points"] / summary["Term Credits"]).fillna(0)
    summary["Cum Points"] = summary["Term Points"].cumsum()
    summary["Cum Credits"] = summary["Term Credits"].cumsum()
    summary["Cumulative GPA"] = (summary["Cum Points"] / summary["Cum Credits"]).fillna(0)
    
    display_summary = summary[["Semester", "Sem GPA", "Cumulative GPA"]].round(2)
    
    st.divider()

    # --- Create 2 Columns for Side-by-Side Layout ---
    col_left, _, col_right = st.columns([1, 0.2, 1]) 
    
    # LEFT COLUMN: Performance Table & Metric
    with col_left:
        st.subheader("Performance Summary")
        if not display_summary.empty:
            # Show metric and table stacked
            current_gpa = display_summary.iloc[-1]["Cumulative GPA"]
            st.metric(label="Current Cumulative GPA", value=f"{current_gpa:.2f}")
            st.dataframe(display_summary, use_container_width=True, hide_index=True)

    # RIGHT COLUMN: Trend Graph
    with col_right:
        st.subheader("Trend")
        if not display_summary.empty:
            chart_data = display_summary.copy()
            
            base = alt.Chart(chart_data).encode(x=alt.X('Semester:O', title='Semester'))
            
            bars = base.mark_bar(opacity=0.7, color='#60b4ff', cornerRadiusTopLeft=5, cornerRadiusTopRight=5).encode(
                y=alt.Y('Sem GPA', title='GPA', scale=alt.Scale(domain=[0, 5])), 
                tooltip=['Semester', 'Sem GPA']
            )
            
            line = base.mark_line(color="#ff0000", point=True).encode(
                y='Cumulative GPA', 
                tooltip=['Semester', 'Cumulative GPA']
            )
            
            # Use container width to fit the column perfectly
            st.altair_chart((bars + line).properties(height=350), width='stretch')