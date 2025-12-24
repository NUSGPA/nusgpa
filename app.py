import streamlit as st
import pandas as pd
import altair as alt
import os
import data_manager as dm 

# --- SECTION 1: APP CONFIGURATION ---
st.set_page_config(page_title="NUSGPA Calculator", layout="wide")

# Constants
grade_map = {
    "A+": 5.0, "A": 5.0, "A-": 4.5, "B+": 4.0, "B": 3.5, "B-": 3.0,
    "C+": 2.5, "C": 2.0, "D+": 1.5, "D": 1.0, "F": 0.0, 
    "CS": 0.0, "CU": 0.0, "IP": 0.0 
}
sem_mapping = {
    "Y1 S1": 1, "Y1 S2": 2, "Y2 S1": 3, "Y2 S2": 4, "Y3 S1": 5, "Y3 S2": 6,
    "Y4 S1": 7, "Y4 S2": 8, "Y5 S1": 9, "Y5 S2": 10, "Y6 S1": 11, "Y6 S2": 12,
    "Special Term": 99
}

# --- SECTION 2: SESSION STATE ---
if "courses" not in st.session_state:
    st.session_state.courses = pd.DataFrame(columns=["Course", "Semester", "Grade", "Credits", "SU_Opt_Out"])
if "uploader_id" not in st.session_state: st.session_state.uploader_id = 0

keys_defaults = {
    "course_name_input": "", "credits_input": 4.0, "search_selection": None, 
    "sem_input_label": "Y1 S1", "grade_input": "A", "su_input": False
}
for key, default in keys_defaults.items():
    if key not in st.session_state: st.session_state[key] = default

# --- SECTION 3: CALLBACKS ---
def on_module_select():
    # Fetch current AY choice from session state
    current_ay = st.session_state.get("ay_selector", dm.get_current_acad_year())
    df_lookup = dm.get_modules_for_ay(current_ay) # Ask data_manager for data
    
    selection = st.session_state.search_selection
    if selection and not df_lookup.empty:
        matches = df_lookup[df_lookup["display_label"] == selection]
        if not matches.empty:
            row = matches.iloc[0]
            st.session_state.course_name_input = row["moduleCode"]
            st.session_state.credits_input = float(row["moduleCredit"])

def add_course_callback():
    name = st.session_state.course_name_input
    sem_label = st.session_state.sem_input_label 
    grade = st.session_state.grade_input
    credits = st.session_state.credits_input
    su = st.session_state.su_input
    sem_int = sem_mapping.get(sem_label, 1)
    
    final_name = name if name else (st.session_state.search_selection if st.session_state.search_selection else "Unknown Course")
    
    new_row = pd.DataFrame([{
        "Course": final_name, "Semester": sem_int, "Grade": grade, 
        "Credits": credits, "SU_Opt_Out": su
    }])
    st.session_state.courses = pd.concat([st.session_state.courses, new_row], ignore_index=True)
    st.session_state.course_name_input = ""
    st.session_state.search_selection = None

def reset_app_callback():
    st.session_state.courses = pd.DataFrame(columns=["Course", "Semester", "Grade", "Credits", "SU_Opt_Out"])
    st.session_state.last_loaded_hash = None
    st.session_state.uploader_id += 1
    st.session_state.course_name_input = ""
    st.session_state.search_selection = None

# --- SECTION 4: SIDEBAR ---
st.sidebar.header("Data & Actions")

# File Upload
unique_key = f"uploader_{st.session_state.uploader_id}"
uploaded_file = st.sidebar.file_uploader("Load CSV", type=["csv"], key=unique_key, label_visibility="collapsed")
if uploaded_file is None: st.sidebar.caption("📂 Load History (CSV)")

if uploaded_file:
    f_hash = hash(uploaded_file.getvalue())
    if "last_loaded_hash" not in st.session_state or st.session_state.last_loaded_hash != f_hash:
        try:
            df_up = pd.read_csv(uploaded_file)
            if {"Course", "Semester", "Grade", "Credits", "SU_Opt_Out"}.issubset(df_up.columns):
                if "SU_Opt_Out" in df_up.columns: df_up["SU_Opt_Out"] = df_up["SU_Opt_Out"].astype(bool)
                st.session_state.courses = df_up
                st.session_state.last_loaded_hash = f_hash
                st.rerun()
            else: st.error("❌ Invalid CSV columns")
        except Exception as e: st.error(f"Error: {e}")

# Export & Reset
if not st.session_state.courses.empty:
    st.sidebar.download_button("📥 Download CSV", st.session_state.courses.to_csv(index=False).encode('utf-8'), "myNUSGPA.csv", "text/csv", width='stretch')
else:
    st.sidebar.download_button("📥 Download CSV", "", disabled=True, width='stretch')

if st.sidebar.button("⚠️ Reset All", on_click=reset_app_callback, type="primary", width='stretch'): pass

st.sidebar.markdown("---")

# Add Course Form
with st.sidebar.expander("Add New Course", expanded=True):
    # 1. Ask data_manager for Year Options
    ay_list, default_ay = dm.get_ay_options()
    
    # 2. Trigger the "ETL" process to ensure files exist
    dm.ensure_all_years_cached(ay_list)
    
    # 3. Dropdown for Year Selection
    try: idx = ay_list.index(default_ay)
    except: idx = 0
    sel_ay = st.selectbox("AY Source", ay_list, index=idx, key="ay_selector", label_visibility="collapsed")
    
    # 4. Fetch specific year data for Search
    modules_df = dm.get_modules_for_ay(sel_ay)
    opts = modules_df["display_label"].tolist() if not modules_df.empty else []

    st.caption(f"Searching **{sel_ay}** database:")
    st.selectbox("Search", opts, index=None, placeholder="Search (e.g. CS1010)...", key="search_selection", on_change=on_module_select, label_visibility="collapsed")
    
    st.caption("Or edit details manually:")
    st.text_input("Course Code", key="course_name_input", label_visibility="collapsed", placeholder="Course Code")
    
    c1, c2 = st.columns([1.5, 1])
    with c1: st.selectbox("Semester", list(sem_mapping.keys()), key="sem_input_label", label_visibility="collapsed")
    with c2: st.number_input("Credits", 0.0, step=1.0, key="credits_input", label_visibility="collapsed")
    
    c3, c4 = st.columns([1, 1])
    with c3: st.selectbox("Grade", list(grade_map.keys()), key="grade_input", label_visibility="collapsed")
    with c4: st.checkbox("Exercise S/U?", key="su_input")
    
    st.button("Add", on_click=add_course_callback, width='stretch')

st.sidebar.markdown("---")
st.sidebar.caption("Data provided by [NUSMods](https://nusmods.com).")

# --- SECTION 5: MAIN UI ---
st.title("NUSGPA Grade Tracker")
col_L, _, col_R = st.columns([1, 0.1, 0.4], vertical_alignment="top")

with col_L:
    st.subheader("Course Record")
    edited = st.data_editor(
        st.session_state.courses, num_rows="dynamic",
        column_config={
            "SU_Opt_Out": st.column_config.CheckboxColumn("SU Option", default=False),
            "Grade": st.column_config.SelectboxColumn("Grade", options=list(grade_map.keys()), required=True),
            "Credits": st.column_config.NumberColumn("Credits", format="%.1f"),
            "Semester": st.column_config.NumberColumn("Semester", help="1=Y1S1, 2=Y1S2...", step=1)
        },
        width='stretch', key="editor", height=300
    )
    if not edited.equals(st.session_state.courses): st.session_state.courses = edited

# --- SECTION 6: ANALYTICS ---
if not st.session_state.courses.empty:
    df = st.session_state.courses.copy()
    NON_GPA = ["CS", "CU", "IP"]
    
    df["Grade Value"] = df["Grade"].map(grade_map)
    df["Calc_Credits"] = df.apply(lambda x: 0 if (x["SU_Opt_Out"] or x["Grade"] in NON_GPA) else x["Credits"], axis=1)
    df["Q_Points"] = df["Grade Value"] * df["Calc_Credits"]
    
    summ = df.groupby("Semester").apply(lambda x: pd.Series({
        "Term Credits": x["Calc_Credits"].sum(), "Term Points": x["Q_Points"].sum(), "Mods": len(x)
    }), include_groups=False).reset_index()
    
    summ["Sem GPA"] = (summ["Term Points"] / summ["Term Credits"]).fillna(0)
    summ["Cum Points"] = summ["Term Points"].cumsum()
    summ["Cum Credits"] = summ["Term Credits"].cumsum()
    summ["Cumulative GPA"] = (summ["Cum Points"] / summ["Cum Credits"]).fillna(0)
    
    cur_gpa = summ.iloc[-1]["Cumulative GPA"]
    if cur_gpa >= 4.5: lbl = "🥇 First Class Honours"
    elif cur_gpa >= 4.0: lbl = "🥈 Second Class (Upper)"
    elif cur_gpa >= 3.5: lbl = "🥉 Second Class (Lower)"
    elif cur_gpa >= 3.0: lbl = "🎓 Third Class"
    elif cur_gpa >= 2.0: lbl = "📜 Pass"
    else: lbl = "⚠️ Below Graduation Req"
    
    disp_sum = summ[["Semester", "Mods", "Sem GPA", "Cumulative GPA"]].round(2)
    
    # Grade Dist Chart Logic
    def chart_grade(r):
        if r["SU_Opt_Out"]: return "CS" if grade_map.get(r["Grade"],0)>=2.0 else "CU"
        return r["Grade"]
    
    c_df = df.copy()
    c_df["C_Grade"] = c_df.apply(chart_grade, axis=1)
    dist = c_df["C_Grade"].value_counts().reset_index()
    dist.columns = ["Grade", "Count"]
    
    d_chart = alt.Chart(dist).mark_bar(color='#ffb060', cornerRadiusTopLeft=5, cornerRadiusTopRight=5).encode(
        x=alt.X('Grade', sort=list(grade_map.keys()), title=None),
        y=alt.Y('Count', title='Count', axis=alt.Axis(tickMinStep=1)),
        tooltip=['Grade', 'Count']
    ).properties(height=250)
    
    st.divider()
    with col_R:
        st.subheader("Cumulative GPA")
        st.metric("Current Cumulative GPA", f"{cur_gpa:.2f}", lbl, delta_color="off")
        
    c1, _, c2, _, c3 = st.columns([1, 0.1, 1, 0.1, 1], vertical_alignment="top")
    with c1:
        st.subheader("Performance")
        st.dataframe(disp_sum, width='stretch', hide_index=True, height=250)
    with c2:
        st.subheader("Grade Dist.")
        st.altair_chart(d_chart, width='stretch')
    with c3:
        st.subheader("Trend")
        t_data = disp_sum.copy()
        rev_map = {v: k for k, v in sem_mapping.items()}
        t_data["Sem Label"] = t_data["Semester"].map(rev_map)
        
        base = alt.Chart(t_data).encode(x=alt.X('Sem Label', sort=alt.EncodingSortField(field="Semester", order="ascending"), title=None))
        bar = base.mark_bar(opacity=0.7, color='#60b4ff', cornerRadiusTopLeft=5, cornerRadiusTopRight=5).encode(
            y=alt.Y('Sem GPA', scale=alt.Scale(domain=[0,5]), title="GPA"), tooltip=['Sem Label', 'Sem GPA', 'Mods'])
        line = base.mark_line(color="#ff0000", point=True).encode(y='Cumulative GPA', tooltip=['Sem Label', 'Cumulative GPA'])
        st.altair_chart((bar+line).properties(height=250), width='stretch')

else:
    st.info("**Welcome!** Start by adding your modules using the sidebar on the left.")

import os
st.write("Current Directory:", os.getcwd())
st.write("Files in folder:", os.listdir())
