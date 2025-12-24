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
    "D": 1.0, "F": 0.0, 
    "CS": 0.0, "CU": 0.0, "IP": 0.0 
}

# Mapping friendly labels to cumulative integers for logic/sorting
sem_mapping = {
    "Y1 S1": 1, "Y1 S2": 2,
    "Y2 S1": 3, "Y2 S2": 4,
    "Y3 S1": 5, "Y3 S2": 6,
    "Y4 S1": 7, "Y4 S2": 8,
    "Y5 S1": 9, "Y5 S2": 10,
    "Y6 S1": 11, "Y6 S2": 12,
    "Special Term": 99
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
    st.session_state.courses = pd.DataFrame(columns=["Course", "Semester", "Grade", "Credits", "SU_Opt_Out"])
if "uploader_id" not in st.session_state: st.session_state.uploader_id = 0

keys_defaults = {
    "course_name_input": "", 
    "credits_input": 4.0, 
    "search_selection": None, 
    "sem_input_label": "Y1 S1",
    "grade_input": "A", 
    "su_input": False
}
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
    sem_label = st.session_state.sem_input_label 
    grade = st.session_state.grade_input
    credits = st.session_state.credits_input
    su = st.session_state.su_input
    
    sem_int = sem_mapping.get(sem_label, 1)
    final_name = name if name else (st.session_state.search_selection if st.session_state.search_selection else "Unknown Course")
    
    new_row = pd.DataFrame([{
        "Course": final_name, 
        "Semester": sem_int,
        "Grade": grade, 
        "Credits": credits, 
        "SU_Opt_Out": su
    }])
    st.session_state.courses = pd.concat([st.session_state.courses, new_row], ignore_index=True)
    
    st.session_state.course_name_input = ""
    st.session_state.search_selection = None

def reset_app_callback():
    """Resets all session data and increments uploader ID to clear file input."""
    st.session_state.courses = pd.DataFrame(columns=["Course", "Semester", "Grade", "Credits", "SU_Opt_Out"])
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
            REQUIRED_COLUMNS = {"Course", "Semester", "Grade", "Credits", "SU_Opt_Out"}
            
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
    
    c1, c2 = st.columns([1.5, 1])
    with c1: 
        st.selectbox("Semester", options=list(sem_mapping.keys()), key="sem_input_label", label_visibility="collapsed")
    with c2: 
        st.number_input("Credits", min_value=0.0, step=1.0, key="credits_input", label_visibility="collapsed")
    
    c3, c4 = st.columns([1, 1])
    with c3: st.selectbox("Grade", options=list(grade_map.keys()), key="grade_input", label_visibility="collapsed")
    with c4: st.checkbox("Exercise S/U?", key="su_input")
    
    st.button("Add", on_click=add_course_callback, use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.caption("Data provided by [NUSMods](https://nusmods.com). Not affiliated with NUS.")

# --- SECTION 6: MAIN INTERFACE ---

st.title("NUSGPA Grade Tracker")

col_left, col_mid, col_right = st.columns([1, 0.1, 0.4], vertical_alignment="top")

with col_left:
# 1. Interactive Data Table
    st.subheader("Course Record")
    edited_df = st.data_editor(
        st.session_state.courses,
        num_rows="dynamic",
        column_config={
            "SU_Opt_Out": st.column_config.CheckboxColumn("SU Option", default=False),
            "Grade": st.column_config.SelectboxColumn("Grade", options=list(grade_map.keys()), required=True),
            "Credits": st.column_config.NumberColumn("Credits", format="%.1f"),
            "Semester": st.column_config.NumberColumn("Semester", help="1=Y1S1, 2=Y1S2, etc.", step=1)
        },
        use_container_width=True,
        key="editor" 
    )

if not edited_df.equals(st.session_state.courses):
    st.session_state.courses = edited_df
    st.rerun()

# --- SECTION 7: ANALYTICS & VISUALIZATION ---

if not st.session_state.courses.empty:
    df = st.session_state.courses.copy()
    
    # Excluded grades list (Non-GPA)
    NON_GPA_GRADES = ["CS", "CU", "IP"]

    # Compute Weighted Scores
    df["Grade Value"] = df["Grade"].map(grade_map)
    df["Calc_Credits"] = df.apply(
        lambda x: 0 if (x["SU_Opt_Out"] or x["Grade"] in NON_GPA_GRADES) else x["Credits"], 
        axis=1
    )
    df["Quality_Points"] = df["Grade Value"] * df["Calc_Credits"]
    
    # Aggregate Data
    summary = df.groupby("Semester").apply(
        lambda x: pd.Series({
            "Term Credits": x["Calc_Credits"].sum(),
            "Term Points": x["Quality_Points"].sum(),
            "Mods": len(x)
        }), include_groups=False
    ).reset_index()
    
    summary["Sem GPA"] = (summary["Term Points"] / summary["Term Credits"]).fillna(0)
    summary["Cum Points"] = summary["Term Points"].cumsum()
    summary["Cum Credits"] = summary["Term Credits"].cumsum()
    summary["Cumulative GPA"] = (summary["Cum Points"] / summary["Cum Credits"]).fillna(0)
    
    # Determine Honours Class
    current_gpa = summary.iloc[-1]["Cumulative GPA"]
    if current_gpa >= 4.5: class_label = "🥇 First Class Honours"
    elif current_gpa >= 4.0: class_label = "🥈 Second Class (Upper)"
    elif current_gpa >= 3.5: class_label = "🥉 Second Class (Lower)"
    elif current_gpa >= 3.0: class_label = "🎓 Third Class"
    elif current_gpa >= 2.0: class_label = "📜 Pass"
    else: class_label = "⚠️ Below Graduation Req"

    display_summary = summary[["Semester", "Mods", "Sem GPA", "Cumulative GPA"]].round(2)
    
    # --- LOGIC UPDATE: Map S/U Grades to CS/CU ---
    def get_chart_grade(row):
        if row["SU_Opt_Out"]:
            # If SU is checked, map to CS if grade is C (2.0) or higher, else CU
            original_val = grade_map.get(row["Grade"], 0)
            return "CS" if original_val >= 2.0 else "CU"
        return row["Grade"]

    # Create a temp copy for charting
    chart_df = df.copy()
    chart_df["Chart_Grade"] = chart_df.apply(get_chart_grade, axis=1)
    
    dist_df = chart_df["Chart_Grade"].value_counts().reset_index()
    dist_df.columns = ["Grade", "Count"]
    grade_order = list(grade_map.keys())

    dist_chart = alt.Chart(dist_df).mark_bar(
        color='#ffb060', 
        cornerRadiusTopLeft=5, 
        cornerRadiusTopRight=5
    ).encode(
        x=alt.X('Grade', sort=grade_order, title=None),
        y=alt.Y('Count', title='Module Count', axis=alt.Axis(tickMinStep=1)),
        tooltip=['Grade', 'Count']
    ).properties(
        height=250
    )
    # --- END LOGIC UPDATE ---

    st.divider()

    # Metric Display
    with col_right:
        st.subheader("Cumulative GPA")
        if not display_summary.empty:
            st.metric(
                label="Current Cumulative GPA", 
                value=f"{current_gpa:.2f}",
                delta=class_label, 
                delta_color="off"
            )

    # --- ROW 1: Visualizations ---
    c1, _, c2, _, c3 = st.columns([1, 0.1, 1, 0.1, 1], vertical_alignment="top") 
    
    # LEFT: Performance Table
    with c1:
        st.subheader("Performance")
        if not display_summary.empty:
            st.dataframe(
                display_summary, 
                width="stretch", 
                hide_index=True,
                height=250
            )

    # MIDDLE: Grade Distribution (Now shows CS/CU)
    with c2:
        st.subheader("Grade Dist.")
        st.altair_chart(dist_chart, width="stretch", height=250)

    # RIGHT: Trend Graph
    with c3:
        st.subheader("Trend")
        if not display_summary.empty:
            chart_data = display_summary.copy()
            rev_mapping = {v: k for k, v in sem_mapping.items()}
            chart_data["Sem Label"] = chart_data["Semester"].map(rev_mapping)
            
            base = alt.Chart(chart_data).encode(
                x=alt.X('Sem Label', sort=alt.EncodingSortField(field="Semester", order="ascending"), title=None)
            )
            
            bars = base.mark_bar(opacity=0.7, color='#60b4ff', cornerRadiusTopLeft=5, cornerRadiusTopRight=5).encode(
                y=alt.Y('Sem GPA', title='GPA', scale=alt.Scale(domain=[0, 5])), 
                tooltip=['Sem Label', 'Sem GPA', 'Mods']
            )
            
            line = base.mark_line(color="#ff0000", point=True).encode(
                y='Cumulative GPA', 
                tooltip=['Sem Label', 'Cumulative GPA']
            )
            
            st.altair_chart((bars + line).properties(height=250), width="stretch")

else:
    st.info("**Welcome!** Start by adding your modules using the sidebar on the left.")
