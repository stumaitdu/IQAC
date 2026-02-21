import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import re
from fpdf import FPDF
import numpy as np

# ==========================================
# 1. PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="IQAC Dashboard",
    layout="wide",
    page_icon="🎓",
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. CSS STYLING
# ==========================================
st.markdown("""
    <style>
        .stApp { background-color: #ffffff !important; color: #212529 !important; }
        [data-testid="stSidebar"] { background-color: #f8f9fa !important; border-right: 1px solid #dee2e6; }
        
        h1, h2, h3, h4, h5, h6, p, span, div, label { color: #212529 !important; font-family: 'Segoe UI', sans-serif; }
        
        [data-testid="stMetric"] { background-color: #ffffff; border: 1px solid #e9ecef; padding: 15px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
        [data-testid="stMetricLabel"] { color: #6c757d !important; }
        [data-testid="stMetricValue"] { color: #212529 !important; }
        
        .js-plotly-plot .plotly .main-svg { background: rgba(0,0,0,0) !important; }

        /* CARDS */
        .compact-topper-row {
            display: flex; justify-content: space-between; align-items: center;
            background-color: #f8f9fa; border: 1px solid #e9ecef; border-left: 4px solid #00CC96;
            border-radius: 8px; padding: 12px 15px; margin-bottom: 5px; transition: 0.2s;
        }
        .compact-topper-row:hover { background-color: #ffffff; box-shadow: 0 4px 8px rgba(0,0,0,0.1); transform: translateY(-2px); }
        
        .ct-rank { font-size: 24px; margin-right: 15px; min-width: 40px; text-align: center; }
        .ct-name { font-size: 16px; font-weight: 700; color: #212529; }
        .ct-details { font-size: 12px; color: #555; margin-top: 4px; }
        
        .ct-stats { text-align: right; min-width: 100px; }
        .ct-score-box { background-color: #e9ecef; color: #212529; font-weight: 700; font-size: 14px; padding: 4px 8px; border-radius: 5px; display: inline-block; margin-bottom: 4px; }
        .ct-cgpa { font-size: 13px; font-weight: 600; color: #444; }
        
        .centered-header { text-align: center; font-size: 24px; font-weight: bold; margin-top: 20px; margin-bottom: 30px; color: #212529; }
        
        .streamlit-expanderHeader {
            font-weight: 600;
            color: #333;
            background-color: white;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
# --- PASTE YOUR GOOGLE SHEET LINK HERE ---
FIXED_SHEET_LINK = "https://docs.google.com/spreadsheets/d/1piyl0Nlf901V2plVayIRQK8B1euemyqVUbr9aPPXNjs/edit?usp=sharing" 

def load_data():
    df = None
    # 1. Try loading from Google Sheets
    if "docs.google.com" in FIXED_SHEET_LINK:
        try:
            url = FIXED_SHEET_LINK.replace("/edit?usp=sharing", "/export?format=csv").replace("/edit", "/export?format=csv")
            df = pd.read_csv(url)
        except: pass 
    
    # 2. Try loading from Local CSV if sheet fails
    if df is None:
        possible_files = ["student_data.csv", "CHECK.csv"]
        for f in possible_files:
            if os.path.exists(f):
                try: df = pd.read_csv(f); break
                except: continue
    
    if df is not None:
        df.columns = df.columns.str.strip()
        df = df.dropna(how='all')
        
        # Load local feedback file if available
        if os.path.exists("student_data.csv"):
            try:
                df_local = pd.read_csv("student_data.csv")
                # Create a key for matching (lowercase name)
                if 'Name' in df.columns: df['Name_Key'] = df.iloc[:, 1].astype(str).str.strip().str.lower()
                else: df['Name_Key'] = df.index.astype(str)
                
                if 'Name' in df_local.columns:
                    df_local['Name_Key'] = df_local['Name'].astype(str).str.strip().str.lower()
                    # Map feedback back to the main dataframe
                    if 'Teacher_Feedback' in df_local.columns:
                        fb_map = df_local.set_index('Name_Key')['Teacher_Feedback'].to_dict()
                        name_col = next((c for c in df.columns if 'name' in c.lower()), df.columns[1])
                        df['Teacher_Feedback'] = df[name_col].astype(str).str.strip().str.lower().map(fb_map).fillna("No feedback yet")
            except: pass
                
    return df

def calculate_points_for_text(text, cat_type="std"):
    text = str(text).lower().strip()
    if text in ['nan', '0', '0.0', '', 'no', 'nil', '-', '.', 'none', 'select']: return 0.0
    points = 0.0
    
    # Logic for scoring based on keywords in 'Level'
    if any(x in text for x in ['international']): points = 2.0
    elif any(x in text for x in ['national', '1st', 'first', 'winner', 'gold']): points = 2.0
    elif any(x in text for x in ['state', 'university', 'inter-college', '2nd', 'second', 'runner', 'silver']): points = 1.5
    elif any(x in text for x in ['3rd', 'third', 'bronze', 'district']): points = 1.0
    elif any(x in text for x in ['leadership', 'secretary', 'head', 'president', 'vice president', 'treasurer', 'coordinator']): points = 1.0
    elif any(x in text for x in ['participation', 'participated', 'member', 'attendee']): points = 0.5
    
    # Default for text present but no specific keyword match (assume participation)
    if points == 0 and len(text) > 2: points = 0.5
    
    return points

# --- ULTRA SMART ACTIVITY EXTRACTOR (POSITIONAL MATCHING) ---
def get_activity_details_df(row, all_columns):
    details = []
    
    # 1. Collect all columns strictly by TYPE (ignoring numbers)
    level_cols = [c for c in all_columns if 'level' in str(c).lower()]
    name_cols = [c for c in all_columns if 'activity' in str(c).lower() and 'name' in str(c).lower()]
    date_cols = [c for c in all_columns if 'date' in str(c).lower()]
    proof_cols = [c for c in all_columns if 'proof' in str(c).lower()]
    
    # 2. Iterate through "Level" columns (since they drive the score)
    for i, lvl_col in enumerate(level_cols):
        col_name = str(lvl_col).lower()
        
        # Determine Category based on header keywords
        cat_name = "Extra-Curricular" # Default
        if any(x in col_name for x in ['aer', 'research', 'paper', 'publication', 'academic']): cat_name = 'Research'
        elif any(x in col_name for x in ['oa', 'outreach', 'social', 'nss']): cat_name = 'Outreach'
        elif any(x in col_name for x in ['sp', 'sport']): cat_name = 'Sports'
        elif 'ncc' in col_name: cat_name = 'NCC'
        elif any(x in col_name for x in ['ie', 'industry', 'intern', 'job']): cat_name = 'Industry/Internship'
        
        # 3. Find corresponding Activity/Date/Proof by POSITION (Index)
        act_col = name_cols[i] if i < len(name_cols) else None
        date_col = date_cols[i] if i < len(date_cols) else None
        proof_col = proof_cols[i] if i < len(proof_cols) else None
        
        # 4. Get Values
        lvl_val = str(row[lvl_col]).strip()
        
        if act_col: act_val = str(row[act_col]).strip()
        else: act_val = "Activity" 
        
        date_val = str(row[date_col]).strip() if date_col else "-"
        proof_val = str(row[proof_col]).strip() if proof_col else None
        
        # Validation
        if lvl_val.lower() not in ['nan', '', 'none', 'no', '0', '0.0', 'select']:
             pts = calculate_points_for_text(lvl_val)
             
             if act_val.lower() in ['nan', '']: act_val = "Not Mentioned"
             if date_val.lower() in ['nan', '']: date_val = "-"
             if proof_val and proof_val.lower() in ['nan', '', 'none', 'no']: proof_val = None

             details.append({
                "Category": cat_name,
                "Activity Name": act_val,
                "Level": lvl_val,
                "Date": date_val,
                "Proof": proof_val,
                "Points": pts
            })

    if not details: return pd.DataFrame()
    return pd.DataFrame(details)


# --- PDF GENERATOR FUNCTION ---
def create_pdf(row):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    def clean(text):
        return str(text).encode('latin-1', 'replace').decode('latin-1')
    
    # 1. Header
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "IQAC Student Report", ln=True, align='C')
    pdf.ln(5)
    
    # 2. Student Details
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Student Profile", ln=True)
    pdf.set_font("Arial", '', 11)
    
    pdf.cell(0, 8, f"Name: {clean(row['Name'])}", ln=True)
    pdf.cell(0, 8, f"Roll No: {clean(row.get('Roll_No', 'N/A'))}", ln=True)
    pdf.cell(0, 8, f"Stream: {clean(row['Stream'])} | Year: {row['Year']}", ln=True)
    pdf.cell(0, 8, f"Email: {clean(row.get('Email_Id', 'N/A'))}", ln=True)
    pdf.cell(0, 8, f"Phone: {clean(row.get('Phone_No', 'N/A'))}", ln=True)
    pdf.ln(5)
    
    # 3. Summary
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Performance Summary", ln=True)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 8, f"Total IQAC Score: {row['Total IQAC Score']}", ln=True)
    pdf.cell(0, 8, f"Status: {clean(row['Status_Text'])}", ln=True)
    pdf.cell(0, 8, f"Batch Rank: #{int(row['Rank'])}", ln=True)
    pdf.ln(5)
    
    # 4. Scores Table
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Score Breakdown", ln=True)
    
    # Table Header
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(140, 8, "Category", 1, 0, 'L', True)
    pdf.cell(40, 8, "Points", 1, 1, 'C', True)
    
    # Table Rows
    pdf.set_font("Arial", '', 10)
    data = [
        ("CGPA Score", f"{row['CGPA_Val']} (Pts: {row['CGPA_Pts']})"),
        ("Sports", row['Sports_Pts']),
        ("Research", row['Research_Pts']),
        ("NCC", row['NCC_Pts']),
        ("Outreach", row['Outreach_Pts']),
        ("Extra-Curricular", row['Extra_Pts']),
        ("Industry/Internship", row['Industry_Pts'])
    ]
    
    for cat, score in data:
        pdf.cell(140, 8, cat, 1, 0, 'L')
        pdf.cell(40, 8, str(score), 1, 1, 'C')

    pdf.ln(10)
    
    # 5. Feedback
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Teacher Feedback", ln=True)
    pdf.set_font("Arial", 'I', 11)
    pdf.multi_cell(0, 8, clean(row['Teacher_Feedback']))
    
    pdf.ln(10)
    pdf.set_font("Arial", '', 8)
    pdf.cell(0, 10, "Generated by IQAC Digital System", align='C')
    
    return pdf.output(dest='S').encode('latin-1')

# --- MAIN PROCESSING FUNCTION ---
def process_and_score_data(df):
    if df is None: return None
    res = pd.DataFrame()
    
    # 1. Basic Info Extraction
    name_col = next((c for c in df.columns if 'name' in c.lower() and 'activity' not in c.lower()), df.columns[1])
    res['Name'] = df[name_col].astype(str).str.strip()
    
    # Contact Info
    email_col = next((c for c in df.columns if 'email' in c.lower()), None)
    phone_col = next((c for c in df.columns if 'contact' in c.lower() or 'mobile' in c.lower() or 'phone' in c.lower()), None)
    roll_col = next((c for c in df.columns if 'roll' in c.lower()), None)
    
    res['Email_Id'] = df[email_col].astype(str) if email_col else "Not Available"
    res['Phone_No'] = df[phone_col].astype(str).str.replace(r'\.0$', '', regex=True).replace('nan', 'N/A') if phone_col else "N/A"
    res['Roll_No'] = df[roll_col].astype(str).str.replace(r'\.0$', '', regex=True).replace('nan', 'N/A') if roll_col else "N/A"

    # =========================================================
    # 2. STREAM & CATEGORY LOGIC
    # =========================================================
    col_hum = next((c for c in df.columns if 'humanities' in c.lower() and 'course' in c.lower()), None)
    col_sci = next((c for c in df.columns if 'science' in c.lower() and 'course' in c.lower()), None)
    col_comm = next((c for c in df.columns if 'commerce' in c.lower() and 'course' in c.lower()), None)

    def get_stream_and_category(row):
        def is_valid(val):
            v = str(val).lower().strip()
            return v not in ['nan', '', 'none', 'select', 'choose', 'select course', 'other'] and len(v) > 2

        if col_hum and is_valid(row[col_hum]): return str(row[col_hum]).strip(), "Humanities"
        if col_sci and is_valid(row[col_sci]): return str(row[col_sci]).strip(), "Science"
        if col_comm and is_valid(row[col_comm]): return str(row[col_comm]).strip(), "Commerce"
        return "Unknown", "General"

    stream_data = df.apply(get_stream_and_category, axis=1, result_type='expand')
    res['Stream'] = stream_data[0]
    res['Category_Main'] = stream_data[1]

    # =========================================================

    # 3. Year / Semester Logic
    sem_col = next((c for c in df.columns if 'sem' in c.lower() and len(c) < 10), None)
    def get_year_from_sem(val):
        try: 
            sem_num = int(re.search(r'\d+', str(val)).group())
            return (sem_num + 1) // 2
        except: return 1
    if sem_col: res['Year'] = df[sem_col].apply(get_year_from_sem)
    else: res['Year'] = 1 

    # 4. CGPA Logic
    cgpa_col = next((c for c in df.columns if 'average cgpa' in c.lower() or 'cgpa' in c.lower()), None)
    if not cgpa_col:
          sgpa_cols = [c for c in df.columns if 'sgpa' in c.lower()]
          if sgpa_cols:
              df['Calc_CGPA'] = df[sgpa_cols].apply(pd.to_numeric, errors='coerce').mean(axis=1)
              res['CGPA_Raw'] = df['Calc_CGPA'].fillna(0)
          else:
              res['CGPA_Raw'] = 0.0
    else:
        res['CGPA_Raw'] = df[cgpa_col].apply(lambda x: float(x) if str(x).replace('.','',1).isdigit() else 0.0)

    # Feedback placeholder
    if 'Teacher_Feedback' in df.columns: res['Teacher_Feedback'] = df['Teacher_Feedback']
    else: res['Teacher_Feedback'] = "No feedback yet"
    
    # Calculate CGPA Points
    def get_cgpa_pts(row):
        try:
            val = float(row['CGPA_Raw'])
            cat = str(row['Category_Main']).lower()
            is_arts = 'humanities' in cat or 'art' in cat
            
            pts = 0.0
            if is_arts: pts = 5.0 if val >= 8 else (4.0 if val >= 7 else (3.0 if val >= 6 else 0.0))
            else: pts = 5.0 if val >= 9 else (4.0 if val >= 8 else (3.0 if val >= 7 else (2.0 if val >= 6 else 0.0)))
            return pts, val
        except: return 0.0, 0.0
    cgpa_data = res.apply(get_cgpa_pts, axis=1, result_type='expand')
    res['CGPA_Pts'] = cgpa_data[0]; res['CGPA_Val'] = cgpa_data[1]

    # 5. ULTRA SMART SCORING (Allows Unlimited Columns, BUT CAPS SCORE at 5.0)
    cats = {'Sports': 0.0, 'Research': 0.0, 'NCC': 0.0, 'Outreach': 0.0, 'Extra': 0.0, 'Industry': 0.0}
    
    def detect_category_smart(col_name):
        txt = str(col_name).lower()
        if "level" not in txt: return None 
        
        if any(x in txt for x in ['aer', 'research', 'paper', 'acad']): return 'Research'
        if any(x in txt for x in ['oa', 'outreach', 'social', 'nss']): return 'Outreach'
        if any(x in txt for x in ['sp', 'sport']): return 'Sports'
        if 'ncc' in txt: return 'NCC'
        if any(x in txt for x in ['ie', 'industry', 'intern']): return 'Industry'
        return 'Extra' 

    final_scores = {k: [] for k in cats.keys()}
    
    for index, row in df.iterrows():
        current_scores = cats.copy()
        
        # Check ALL columns (Smart Scan)
        for col in df.columns:
            cat_key = detect_category_smart(col)
            if cat_key:
                val = row[col]
                pts = calculate_points_for_text(val)
                current_scores[cat_key] += pts
        
        # APPLY CAP: Max 5.0 points per category
        for k in current_scores: 
            final_scores[k].append(min(current_scores[k], 5.0))
            
    for k, v in final_scores.items(): res[f'{k}_Pts'] = v

    # --- SCORE CALCULATION ---
    activity_sum = (res['Sports_Pts'] + res['Research_Pts'] + res['NCC_Pts'] + res['Outreach_Pts'] + res['Extra_Pts'] + res['Industry_Pts'])
    res['Total IQAC Score'] = res['CGPA_Pts'] + activity_sum
    res['Rank'] = res.groupby(['Stream', 'Year'])['Total IQAC Score'].rank(ascending=False, method='min')
    
    # --- IDENTIFY ALL ROUNDER ---
    res['Is_All_Rounder'] = False
    def mark_all_rounders(group):
        if not group.empty:
            top_students = group.sort_values(by=['Total IQAC Score', 'CGPA_Val'], ascending=[False, False])
            top_idx = top_students.index[0]
            top_student = res.loc[top_idx]
            
            activity_score = top_student['Total IQAC Score'] - top_student['CGPA_Pts']
            
            if top_student['CGPA_Val'] >= 6.0 and activity_score > 0:
                res.loc[top_idx, 'Is_All_Rounder'] = True
        return group
    if not res.empty: res.groupby(['Stream', 'Year'], group_keys=False).apply(mark_all_rounders)

    def get_dynamic_status(row):
        rank = row['Rank']
        cgpa = row['CGPA_Val']
        is_topper = row['Is_All_Rounder']
        if cgpa < 6.0: return "Needs Improvement", "🔴"
        elif is_topper: return "Excellent", "🟢"
        elif rank <= 3: return "Good", "🔵"
        else: return "Average", "🟡"

    status_data = res.apply(get_dynamic_status, axis=1)
    res['Status_Text'] = [x[0] for x in status_data]
    res['Status_Icon'] = [x[1] for x in status_data]

    def generate_display_name(row):
        name = row['Name']
        if row['Is_All_Rounder']: name = f"🏅 {name}"
        if row['Status_Text'] == "Needs Improvement": name = f"{name} 🔴"
        return name
    res['Display_Name'] = res.apply(generate_display_name, axis=1)
    
    # Keep Original Index
    res['Original_Index'] = df.index
    
    return res

# --- IMPROVED FEEDBACK SECTION (EDIT & DELETE) ---
def feedback_section(student_name, current_feedback, unique_key_suffix):
    clean_name = student_name.replace('🏅 ', '').replace(' 🔴', '').strip()
    
    with st.form(key=f"fb_{clean_name}_{unique_key_suffix}"):
        st.write(f"📝 *Feedback for {clean_name}*")
        feedback_text = st.text_area("Enter Feedback:", value=current_feedback, height=100)
        
        c1, c2 = st.columns([0.4, 0.6])
        is_save = c1.form_submit_button("💾 Save / Update")
        is_delete = c2.form_submit_button("🗑️ Delete Feedback", type="primary")

        if is_save:
            if os.path.exists("student_data.csv"):
                df_local = pd.read_csv("student_data.csv")
            else:
                df_local = pd.DataFrame(columns=['Name', 'Teacher_Feedback'])
            
            # Remove old entry to prevent duplicates (Edit Logic)
            df_local = df_local[df_local['Name'] != clean_name]
            
            if feedback_text.strip():
                new_row = pd.DataFrame({'Name': [clean_name], 'Teacher_Feedback': [feedback_text]})
                df_local = pd.concat([df_local, new_row], ignore_index=True)
            
            df_local.to_csv("student_data.csv", index=False)
            st.success(f"✅ Feedback updated for {clean_name}")
            st.session_state["df"] = load_data()
            st.rerun()

        if is_delete:
            if os.path.exists("student_data.csv"):
                df_local = pd.read_csv("student_data.csv")
                df_local = df_local[df_local['Name'] != clean_name]
                df_local.to_csv("student_data.csv", index=False)
                st.success(f"🗑️ Feedback deleted for {clean_name}")
                st.session_state["df"] = load_data()
                st.rerun()
            else:
                st.warning("No feedback file found.")

# ==========================================
# 4. MAIN APP LAYOUT
# ==========================================
if "df" not in st.session_state:
    st.session_state["df"] = load_data()

st.sidebar.title("🎓 IQAC")
if st.sidebar.button("🔄 Refresh Data"):
    st.session_state["df"] = load_data()
    st.rerun()

df_raw = st.session_state["df"]

if df_raw is not None:
    df = process_and_score_data(df_raw)
    
    if df is not None and not df.empty:
        
        tab1, tab2, tab3, tab4 = st.tabs(["🎓 Student Dashboard", "📉 Remedial Tracker", "🏆 Hall of Fame", "🌟 Top Performers"])
        
        # --- TAB 1: DASHBOARD ---
        with tab1:
            st.sidebar.markdown("---")
            st.sidebar.subheader("Filter Stream")
            
            sel_stream = None 
            sel_year = None
            
            main_cats = [x for x in sorted(df['Category_Main'].unique()) if str(x).lower() != 'nan']
            
            def on_stream_change(current_cat):
                for cat in main_cats:
                    if cat != current_cat:
                        if f"radio_{cat}" in st.session_state: st.session_state[f"radio_{cat}"] = None

            for cat in main_cats:
                raw_courses = df[df['Category_Main'] == cat]['Stream'].unique()
                courses_in_cat = sorted([x for x in raw_courses if str(x).lower() not in ['nan', 'unknown', 'none']])
                
                if len(courses_in_cat) > 0:
                    with st.sidebar.expander(f"📂 {cat}", expanded=False):
                        selection = st.radio("Select Course:", courses_in_cat, key=f"radio_{cat}", index=None, on_change=on_stream_change, args=(cat,))
                        
                        if selection: 
                            sel_stream = selection
                            available_years = sorted(df[df['Stream'] == selection]['Year'].unique())
                            if len(available_years) > 0:
                                sel_year = st.radio(f"Select Year ({selection}):", available_years, horizontal=True, key=f"year_{selection}")
            
            # --- FILTER DATAFRAME ---
            filtered_df = df.copy()
            if sel_stream:
                filtered_df = filtered_df[filtered_df['Stream'] == sel_stream]
                if sel_year:
                    filtered_df = filtered_df[filtered_df['Year'] == sel_year]
                
            
            if sel_stream and sel_year:
                if not filtered_df.empty:
                    student_options = sorted(filtered_df['Display_Name'].unique())
                    head_col1, head_col2 = st.columns([0.65, 0.35])
                    with head_col2:
                        sel_student_display = st.selectbox("🔍 Switch Student", student_options, label_visibility="collapsed")

                        # --- NEW: MARKSHEET LINK LOGIC ---
                        marksheet_col = next((c for c in df_raw.columns if 'upload' in c.lower() and 'marksheet' in c.lower()), None)
                        
                        if sel_student_display:
                            sel_row_temp = filtered_df[filtered_df['Display_Name'] == sel_student_display].iloc[0]
                            orig_idx = sel_row_temp['Original_Index']
                            
                            if marksheet_col:
                                marksheet_link = str(df_raw.loc[orig_idx, marksheet_col]).strip()
                                
                                if marksheet_link.lower() not in ['nan', '', 'none', 'no']:
                                    st.markdown(f"""
                                        <a href="{marksheet_link}" target="_blank" style="text-decoration: none;">
                                            <button style="width: 100%; margin-top: 5px; background-color: #f8f9fa; border: 1px solid #ced4da; padding: 6px 12px; border-radius: 5px; cursor: pointer; color: #0d6efd; font-weight: 600; font-size: 14px;">
                                                📄 View Marksheet PDF
                                            </button>
                                        </a>
                                    """, unsafe_allow_html=True)


                    if sel_student_display:
                        sel_row = filtered_df[filtered_df['Display_Name'] == sel_student_display].iloc[0]
                        row = sel_row
                        
                        # --- GET RAW DATA ROW FOR DETAILS ---
                        original_idx = row['Original_Index']
                        raw_row = df_raw.iloc[original_idx]

                        badge_html = ""
                        if row['Is_All_Rounder']:
                              badge_html = '<span style="background-color:#FFD700; color:black; padding:4px 12px; border-radius:15px; font-size:12px; font-weight:bold; margin-left:10px; vertical-align: middle; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">🏆 Year Topper</span>'
                        status_html = f'<span style="background-color:#f8f9fa; color:#333; padding:4px 12px; border-radius:15px; font-size:12px; font-weight:600; border: 1px solid #dee2e6; margin-left: 5px; vertical-align: middle;">{row["Status_Icon"]} {row["Status_Text"]}</span>'
                        
                        email_display = row.get('Email_Id', 'N/A'); phone_display = row.get('Phone_No', 'N/A')
                        if str(email_display).lower() == 'nan': email_display = "N/A"
                        if str(phone_display).lower() == 'nan': phone_display = "N/A"

                        with head_col1:
                            st.markdown(f"""
                            <div style="padding-top: 5px;">
                                <h2 style="margin:0; padding:0; color:#212529; display:inline-block;">🎓 {row['Name']}</h2>
                                {badge_html} {status_html}
                                <div style="font-size: 14px; color: #666; margin-top: 8px;">
                                    <b>{row['Stream']}</b> • Year {row['Year']}
                                </div>
                                <div style="font-size: 13px; color: #888; margin-top: 2px;">
                                    📧 {email_display} &nbsp;|&nbsp; 📞 {phone_display}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                        st.markdown("---")
                        
                        c1, c2, c3, c4, c5 = st.columns(5)
                        c1.metric("🏆 Total Score", f"{row['Total IQAC Score']}")
                        c2.metric("🎓 Avg. CGPA", f"{row['CGPA_Val']:.2f}") 
                        c3.metric("📊 CGPA Points", f"{row['CGPA_Pts']}")
                        c4.metric("🚀 Activity Pts", f"{row['Total IQAC Score'] - row['CGPA_Pts']}")
                        c5.metric("📈 Batch Rank", f"#{int(row['Rank'])}")
                        st.markdown("---")

                        chart_data_map = {
                            'Avg CGPA': row['CGPA_Pts'], 'Extra-Curricular': row['Extra_Pts'], 'Research': row['Research_Pts'],
                            'Outreach': row['Outreach_Pts'], 'Sports': row['Sports_Pts'], 'NCC': row['NCC_Pts'], 'Industry': row['Industry_Pts']
                        }
                        cats = list(chart_data_map.keys()); vals = list(chart_data_map.values())
                        
                        # Cap values only for Radar Chart Visualization (max 5)
                        vals_viz = [min(v, 5.0) for v in vals]
                        
                        cl, cr = st.columns(2)
                        with cl:
                            st.subheader("🕸️ Holistic Performance")
                            vals_r = vals_viz + vals_viz[:1]; cats_r = cats + cats[:1]
                            fig = go.Figure(go.Scatterpolar(r=vals_r, theta=cats_r, fill='toself', line_color='#00CC96', marker=dict(color='#00CC96')))
                            fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 5], tickfont=dict(color='#444')), angularaxis=dict(tickfont=dict(color='#444')), bgcolor="rgba(0,0,0,0)"), showlegend=False, height=400, margin=dict(l=40, r=40, t=20, b=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                            st.plotly_chart(fig, use_container_width=True)
                        with cr:
                            st.subheader("📊 Breakdown")
                            # Bar chart uses actual values (but these will be capped at 5 in the dataframe now)
                            bdf = pd.DataFrame({'Category': cats, 'Points': vals})
                            fig2 = px.bar(bdf, x='Points', y='Category', orientation='h', text='Points', color='Points', color_continuous_scale='Mint')
                            fig2.update_layout(xaxis=dict(tickfont=dict(color='#444'), title="Points"), yaxis=dict(tickfont=dict(color='#444'), title=""), coloraxis_showscale=False, height=400, margin=dict(l=0, r=10, t=20, b=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#212529"))
                            st.plotly_chart(fig2, use_container_width=True)
                        st.markdown("---")
                        
                        # --- DETAILED ACTIVITY LOG ---
                        st.markdown("### 📌 Detailed Activity Log")
                        details_df = get_activity_details_df(raw_row, df_raw.columns)
                        
                        if not details_df.empty:
                            st.dataframe(
                                details_df, 
                                use_container_width=True, 
                                hide_index=True,
                                column_config={
                                    "Proof": st.column_config.LinkColumn(
                                        "Evidence",
                                        display_text="View Proof 🔗"
                                    )
                                }
                            )
                        else:
                            st.info("ℹ️ No detailed activity records found for this student.")
                        
                        st.markdown("---")
                        
                        r_col1, r_col2 = st.columns([0.8, 0.2])
                        with r_col1:
                              st.markdown(f"#### ✍️ Update Feedback for {row['Name']}")
                              feedback_section(row['Name'], row['Teacher_Feedback'], "dashboard")
                        with r_col2:
                            st.write("")
                            st.write("")
                            pdf_bytes = create_pdf(row)
                            st.download_button(label="📄 Download PDF Report", data=pdf_bytes, file_name=f"{row['Name']}_Report.pdf", mime='application/pdf')
                else:
                    st.info("⚠️ No students found in this Year/Course.")
            else:
                st.info("👈 Please select a Stream and Year from the sidebar to view student details.")

        # --- TAB 2: REMEDIAL TRACKER ---
        with tab2:
            st.markdown("<h2 class='centered-header'>📉 Remedial Tracker (CGPA < 6.0)</h2>", unsafe_allow_html=True)
            
            categories = [x for x in sorted(df['Category_Main'].unique()) if str(x).lower() != 'nan']
            t2_c1, t2_c2, t2_c3 = st.columns(3)
            
            sel_rem_cat = t2_c1.selectbox("1️⃣ Select Stream:", categories, key="rem_cat")
            sel_rem_course = None
            sel_rem_year = None
            
            if sel_rem_cat:
                raw_courses = df[df['Category_Main'] == sel_rem_cat]['Stream'].unique()
                courses = sorted([x for x in raw_courses if str(x).lower() not in ['nan', 'unknown', 'none']])
                sel_rem_course = t2_c2.selectbox("2️⃣ Select Course:", courses, key="rem_course")
                
                if sel_rem_course:
                    years = sorted(df[(df['Category_Main'] == sel_rem_cat) & (df['Stream'] == sel_rem_course)]['Year'].unique())
                    sel_rem_year = t2_c3.selectbox("3️⃣ Select Year:", years, key="rem_year")

            st.markdown("---")

            if sel_rem_cat and sel_rem_course and sel_rem_year:
                weak_students = df[
                    (df['Category_Main'] == sel_rem_cat) &
                    (df['Stream'] == sel_rem_course) &
                    (df['Year'] == sel_rem_year) &
                    (df['Status_Text'] == "Needs Improvement")
                ].copy()

                if not weak_students.empty:
                    st.dataframe(weak_students[['Name', 'Stream', 'Year', 'CGPA_Val', 'Total IQAC Score', 'Teacher_Feedback']], use_container_width=True)
                    
                    st.markdown("---")
                    st.markdown("### ✍️ Update Remedial Student Feedback")
                    col_sel, col_form = st.columns([0.4, 0.6])
                    with col_sel:
                        rem_student = st.selectbox("Select Student to Update:", weak_students['Name'].unique(), key="rem_select_fb")
                    with col_form:
                        if rem_student:
                            current_fb = weak_students[weak_students['Name'] == rem_student]['Teacher_Feedback'].iloc[0]
                            feedback_section(rem_student, current_fb, "remedial_tab")
                else:
                     st.success("🎉 No remedial students found in this class! Everyone has CGPA >= 6.0.")
            else:
                 st.info("👈 Please select Stream, Course, and Year to view remedial students.")

        # --- TAB 3: HALL OF FAME ---
        with tab3:
            st.markdown("<h2 class='centered-header'>🏆 Institution All-Rounders</h2>", unsafe_allow_html=True)

            col1, col2, col3 = st.columns(3)
            structure = [
                (col1, "HUMANITIES", ["Humanities"]),
                (col2, "SCIENCE", ["Science", "Sciences"]),
                (col3, "COMMERCE", ["Commerce", "Management"])
            ]

            for col, title, keywords in structure:
                with col:
                    st.markdown(f"<h5 style='text-align:center; border-bottom:3px solid #FFD700; padding-bottom:5px; margin-bottom:15px; color:#444;'>{title}</h5>", unsafe_allow_html=True)
                    for year in range(1, 5):
                        topper = df[
                            (df['Category_Main'].apply(lambda x: any(k.lower() in str(x).lower() for k in keywords))) & 
                            (df['Year'] == year) & 
                            (df['Is_All_Rounder'] == True)
                        ]
                        
                        if not topper.empty:
                            row = topper.iloc[0]
                            st.markdown(f"""
                            <div style="background-color: #fff; border: 1px solid #e0e0e0; border-left: 4px solid #00CC96; padding: 10px; border-radius: 6px; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                                <div style="font-size: 11px; font-weight: bold; color: #888; width: 45px; text-transform: uppercase;">YEAR {year}</div>
                                <div style="font-weight: 700; font-size: 13px; color: #333; flex-grow: 1; padding: 0 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">🏅 {row['Name']}</div>
                                <div style="font-weight: 700; font-size: 13px; background: #f8f9fa; padding: 2px 6px; border-radius: 4px; border:1px solid #ddd; color: #333;">{row['Total IQAC Score']}</div>
                            </div>
                            """, unsafe_allow_html=True)

                            # --- UPDATED: VIEW ACTIVITY DETAILS EXPANDER ---
                            with st.expander(f"📂 View Activity Details for {row['Name']}"):
                                raw_row_hof = df_raw.iloc[row['Original_Index']]
                                details_df_hof = get_activity_details_df(raw_row_hof, df_raw.columns)
                                
                                if not details_df_hof.empty:
                                        st.dataframe(
                                        details_df_hof, 
                                        use_container_width=True, 
                                        hide_index=True,
                                        column_config={
                                            "Proof": st.column_config.LinkColumn(
                                                "Evidence",
                                                display_text="View Proof 🔗"
                                            )
                                        }
                                    )
                                else:
                                    st.write("No proof links found.")
                            
                            # --- NEW: MARKSHEET BUTTON SECTION ---
                            marksheet_col = next((c for c in df_raw.columns if 'upload' in c.lower() and 'marksheet' in c.lower()), None)
                            if marksheet_col:
                                m_link = str(df_raw.loc[row['Original_Index'], marksheet_col]).strip()
                                if m_link.lower() not in ['nan', '', 'none', 'no']:
                                    st.markdown(f"""
                                        <div style="margin-top: 5px; margin-bottom: 10px;">
                                            <a href="{m_link}" target="_blank" style="text-decoration: none;">
                                                <button style="background-color: #f0f2f6; border: 1px solid #dce4ef; padding: 8px 16px; border-radius: 4px; color: #0068c9; font-weight: 600; cursor: pointer;">
                                                    📄 View Marksheet
                                                </button>
                                            </a>
                                        </div>
                                    """, unsafe_allow_html=True)

                        else:
                            st.markdown(f"""
                            <div style="background-color: #f9f9f9; border: 1px dashed #ccc; padding: 10px; border-radius: 6px; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; opacity: 0.6;">
                                <div style="font-size: 11px; font-weight: bold; color: #aaa; width: 45px; text-transform: uppercase;">YEAR {year}</div>
                                <div style="font-size: 12px; color: #aaa;">N/A</div>
                            </div>
                            """, unsafe_allow_html=True)

            st.markdown("---")
            st.subheader("📝 Batch Toppers Table & Feedback")
            
            # --- MODIFIED TABLE SECTION (CGPA Points + MARKSHEET) ---
            all_toppers = df[df['Is_All_Rounder'] == True].sort_values(by=['Category_Main', 'Year']).copy()
            
            marksheet_col = next((c for c in df_raw.columns if 'upload' in c.lower() and 'marksheet' in c.lower()), None)

            if marksheet_col:
                # Use Original_Index to map the link back from df_raw
                # We extract values safely to avoid index mismatch
                all_toppers['Marksheet_View'] = df_raw.loc[all_toppers['Original_Index'], marksheet_col].values
            else:
                all_toppers['Marksheet_View'] = None

            st.dataframe(
                all_toppers[['Name', 'Category_Main', 'Stream', 'Year', 'Total IQAC Score', 'CGPA_Pts', 'Marksheet_View', 'Teacher_Feedback']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Marksheet_View": st.column_config.LinkColumn("Marksheet", display_text="📄 View PDF"),
                    "CGPA_Pts": st.column_config.NumberColumn("CGPA Points", format="%.1f"),
                    "Total IQAC Score": st.column_config.NumberColumn("Score", format="%.1f")
                }
            )
            
            st.markdown("### ✍️ Update Topper Feedback")
            t_col_sel, t_col_form = st.columns([0.4, 0.6])
            with t_col_sel:
                topper_student = st.selectbox("Select Topper to Update:", all_toppers['Name'].unique(), key="topper_select_fb")
            with t_col_form:
                if topper_student:
                    t_curr_fb = all_toppers[all_toppers['Name'] == topper_student]['Teacher_Feedback'].iloc[0]
                    feedback_section(topper_student, t_curr_fb, "hof_tab")

        # --- TAB 4: TOP PERFORMERS ---
        with tab4:
            st.markdown("<h2 class='centered-header'>🌟 Top Performers (Course-wise)</h2>", unsafe_allow_html=True)

            categories = [x for x in sorted(df['Category_Main'].unique()) if str(x).lower() != 'nan']
            c1, c2, c3 = st.columns(3)
            selected_cat = c1.selectbox("1️⃣ Select Stream Category:", categories)

            if selected_cat:
                raw_courses = df[df['Category_Main'] == selected_cat]['Stream'].unique()
                courses = sorted([x for x in raw_courses if str(x).lower() not in ['nan', 'unknown', 'none']])
                selected_course = c2.selectbox("2️⃣ Select Course:", courses)

                if selected_course:
                    years = sorted(df[(df['Category_Main'] == selected_cat) & (df['Stream'] == selected_course)]['Year'].unique())
                    selected_year = c3.selectbox("3️⃣ Select Year:", years)

                    if selected_year:
                        subset = df[(df['Stream'] == selected_course) & (df['Year'] == selected_year)]
                        
                        # --- FILTER: EXCLUDE STUDENTS WITH 0 ACTIVITY POINTS ---
                        subset = subset[ (subset['Total IQAC Score'] - subset['CGPA_Pts']) > 0 ]
                        
                        subset = subset.sort_values(by='Total IQAC Score', ascending=False).head(3)

                        st.markdown("---")
                        if not subset.empty:
                            for i, (idx, row) in enumerate(subset.iterrows()):
                                rank = i + 1
                                rank_icon = ["🥇", "🥈", "🥉"][i] if i < 3 else f"#{rank}"

                                st.markdown(f"""
                                <div class="compact-topper-row">
                                    <div style="display:flex; align-items:center; width: 100%;">
                                        <div class="ct-rank">{rank_icon}</div>
                                        <div style="flex-grow: 1;">
                                            <div class="ct-name">{row['Name']}</div>
                                            <div class="ct-details">
                                                🆔 <b>{row.get('Roll_No', 'N/A')}</b> &nbsp;|&nbsp; 📞 {row.get('Phone_No', 'N/A')} &nbsp;|&nbsp; 📧 {row.get('Email_Id', 'N/A')}
                                            </div>
                                        </div>
                                        <div class="ct-stats">
                                            <div class="ct-score-box">🏆 {row['Total IQAC Score']} Pts</div>
                                            <div class="ct-cgpa">🎓 CGPA: {row['CGPA_Val']:.2f}</div>
                                        </div>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # --- UPDATED: VIEW ACTIVITY DETAILS EXPANDER ---
                                with st.expander(f"📂 View Activity Details for {row['Name']}"):
                                    raw_row_tp = df_raw.iloc[row['Original_Index']]
                                    details_df_tp = get_activity_details_df(raw_row_tp, df_raw.columns)
                                    
                                    if not details_df_tp.empty:
                                         st.dataframe(
                                            details_df_tp, 
                                            use_container_width=True, 
                                            hide_index=True,
                                            column_config={
                                                "Proof": st.column_config.LinkColumn(
                                                    "Evidence",
                                                    display_text="View Proof 🔗"
                                                )
                                            }
                                        )
                                    else:
                                        st.write("No proof links found.")
                                
                                # --- NEW: MARKSHEET BUTTON SECTION ---
                                marksheet_col = next((c for c in df_raw.columns if 'upload' in c.lower() and 'marksheet' in c.lower()), None)
                                if marksheet_col:
                                    m_link = str(df_raw.loc[row['Original_Index'], marksheet_col]).strip()
                                    if m_link.lower() not in ['nan', '', 'none', 'no']:
                                        st.markdown(f"""
                                            <div style="margin-top: 5px; margin-bottom: 10px;">
                                                <a href="{m_link}" target="_blank" style="text-decoration: none;">
                                                    <button style="background-color: #f0f2f6; border: 1px solid #dce4ef; padding: 8px 16px; border-radius: 4px; color: #0068c9; font-weight: 600; cursor: pointer;">
                                                        📄 View Marksheet
                                                    </button>
                                                </a>
                                            </div>
                                        """, unsafe_allow_html=True)

                        else:
                            st.info("ℹ️ No students in this class qualify as Top Performers yet (Must have Activity Points > 0).")

else:
    st.warning("⚠️ No data found. Please check your Google Sheet link or upload a CSV file.")