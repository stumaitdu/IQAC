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
    page_title="SmarTrack Dashboard",
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
            font-weight: 600; color: #333; background-color: white; border: 1px solid #ddd; border-radius: 5px;
        }
        
        .empathetic-note {
            font-size: 12.5px; color: #6c757d; font-style: italic; background-color: #f1f3f5;
            padding: 6px 10px; border-radius: 4px; border-left: 3px solid #ffc107; margin-top: 5px; margin-bottom: 10px;
        }
        .premium-note {
            font-size: 12.5px; color: #0f5132; font-style: italic; background-color: #d1e7dd;
            padding: 6px 10px; border-radius: 4px; border-left: 3px solid #198754; margin-top: 5px; margin-bottom: 10px;
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
FIXED_SHEET_LINK = "https://docs.google.com/spreadsheets/d/1piyl0Nlf901V2plVayIRQK8B1euemyqVUbr9aPPXNjs/edit?usp=sharing"

def load_data():
    df = None
    if "docs.google.com" in FIXED_SHEET_LINK:
        try:
            url = FIXED_SHEET_LINK.replace("/edit?usp=sharing", "/export?format=csv").replace("/edit", "/export?format=csv")
            df = pd.read_csv(url)
        except: pass
    
    if df is None:
        possible_files = ["student_data.csv", "CHECK.csv"]
        for f in possible_files:
            if os.path.exists(f):
                try: df = pd.read_csv(f); break
                except: continue
    
    if df is not None:
        df.columns = df.columns.str.strip()
        df = df.dropna(how='all')
        
        if os.path.exists("student_data.csv"):
            try:
                df_local = pd.read_csv("student_data.csv")
                if 'Name' in df.columns: df['Name_Key'] = df.iloc[:, 1].astype(str).str.strip().str.lower()
                else: df['Name_Key'] = df.index.astype(str)
                
                if 'Name' in df_local.columns:
                    df_local['Name_Key'] = df_local['Name'].astype(str).str.strip().str.lower()
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
    
    if any(x in text for x in ['international']): points = 2.0
    elif any(x in text for x in ['national', '1st', 'first', 'winner', 'gold']): points = 2.0
    elif any(x in text for x in ['state', 'university', 'inter-college', '2nd', 'second', 'runner', 'silver']): points = 1.5
    elif any(x in text for x in ['3rd', 'third', 'bronze', 'district']): points = 1.0
    elif any(x in text for x in ['leadership', 'secretary', 'head', 'president', 'vice president', 'treasurer', 'coordinator']): points = 1.0
    elif any(x in text for x in ['participation', 'participated', 'member', 'attendee']): points = 0.5
    
    if points == 0 and len(text) > 2: points = 0.5
    return points

def get_activity_details_df(row, all_columns):
    details = []
    level_cols = [c for c in all_columns if 'level' in str(c).lower()]
    name_cols = [c for c in all_columns if 'activity' in str(c).lower() and 'name' in str(c).lower()]
    date_cols = [c for c in all_columns if 'date' in str(c).lower()]
    proof_cols = [c for c in all_columns if 'proof' in str(c).lower()]
    
    for i, lvl_col in enumerate(level_cols):
        col_name = str(lvl_col).lower()
        cat_name = "Extra-Curricular"
        if any(x in col_name for x in ['aer', 'research', 'paper', 'publication', 'academic']): cat_name = 'Research'
        elif any(x in col_name for x in ['oa', 'outreach', 'social', 'nss']): cat_name = 'Outreach'
        elif any(x in col_name for x in ['sp', 'sport']): cat_name = 'Sports'
        elif 'ncc' in col_name: cat_name = 'NCC'
        elif any(x in col_name for x in ['ie', 'industry', 'intern', 'job']): cat_name = 'Industry/Internship'
        
        act_col = name_cols[i] if i < len(name_cols) else None
        date_col = date_cols[i] if i < len(date_cols) else None
        proof_col = proof_cols[i] if i < len(proof_cols) else None
        
        lvl_val = str(row[lvl_col]).strip()
        act_val = str(row[act_col]).strip() if act_col else "Activity"
        date_val = str(row[date_col]).strip() if date_col else "-"
        proof_val = str(row[proof_col]).strip() if proof_col else None
        
        if lvl_val.lower() not in ['nan', '', 'none', 'no', '0', '0.0', 'select']:
             pts = calculate_points_for_text(lvl_val)
             if act_val.lower() in ['nan', '']: act_val = "Not Mentioned"
             if date_val.lower() in ['nan', '']: date_val = "-"
             if proof_val and proof_val.lower() in ['nan', '', 'none', 'no']: proof_val = None

             details.append({"Category": cat_name, "Activity Name": act_val, "Level": lvl_val, "Date": date_val, "Proof": proof_val, "Points": pts})

    if not details: return pd.DataFrame()
    return pd.DataFrame(details)

def get_smartrack_analysis(row):
    academics = row.get('CGPA_Pts', 0)
    cgpa_val = float(row.get('CGPA_Val', 0.0))
    social = min(row.get('Outreach_Pts', 0) + row.get('NCC_Pts', 0), 5.0)
    physical = row.get('Sports_Pts', 0)
    research = row.get('Research_Pts', 0)
    literacy = min(row.get('Extra_Pts', 0) + row.get('Industry_Pts', 0), 5.0)
    
    areas = {'Academics': academics, 'Social Responsibility': social, 'Physical Health': physical, 'Research': research, 'Literacy': literacy}
    
    white_areas = []
    gray_areas = []  
    black_areas = []
    
    for cat, score in areas.items():
        if score >= 3.0: white_areas.append(cat)
        elif score >= 1.0: gray_areas.append(cat)
        else: black_areas.append(cat)
        
    recommendation = ""
    if 'Academics' in white_areas and cgpa_val >= 7.0 and 'Social Responsibility' in black_areas:
        recommendation = "🌟 You are doing exceptionally well in Academics! However, focusing entirely on studies can lead to burnout. We highly encourage you to participate in 'Social Responsibility' (like joining an NGO). This promotes holistic development and acts as a great stress-buster."
    elif 'Physical Health' in black_areas:
        recommendation = "🏃‍♂️ Your physical health category needs attention. Constant studying without physical activity increases stress. Try joining a sports event or daily physical activity to boost your mental well-being."
    elif 'Academics' in black_areas or cgpa_val < 7.0:
        recommendation = "📚 Academic focus is needed right now to boost your CGPA securely. Ensure you maintain balance. Don't take last-minute exam pressure! Check out our curated 'Study Material' tab to clear your concepts easily."
    elif len(white_areas) >= 3:
        recommendation = "🏆 Excellent holistic balance! You are managing your time well across multiple domains, which is the best way to maintain good mental health and a strong profile."
    else:
        recommendation = f"🌱 Step out of your comfort zone! Start exploring your areas like {', '.join(gray_areas + black_areas)} to build a well-rounded personality."
        
    return areas, white_areas, gray_areas, black_areas, recommendation

def fetch_personalized_opportunities(white_areas, black_areas, course, cgpa_val, current_year):
    opps = []
    course_lower = str(course).lower()
    try: year = int(current_year)
    except: year = 1

    if 'Academics' in white_areas and cgpa_val >= 7.0:
        if any(k in course_lower for k in ['cs', 'computer', 'science']):
            if year == 1:
                opps.append({"name": "Freshman Intra-College Coding Sprint", "type": "Premium Academic", "date": "Next Month", "premium": True, "note": "🌟 You have a great start! Test your basic programming skills here."})
            elif year == 2:
                opps.append({"name": "State-Level Tech Symposium & Hackathon", "type": "Premium Academic", "date": "15 April", "premium": True, "note": "🌟 Use your strong core concepts to build real-world projects and compete!"})
            else:
                opps.append({"name": "Global Open Source & AI Fellowship", "type": "Premium Academic", "date": "May", "premium": True, "note": "🌟 Ready for the big leagues! Leverage your high CGPA for this advanced fellowship."})
        
        elif any(k in course_lower for k in ['commerce', 'b.com', 'eco']):
            if year == 1:
                opps.append({"name": "Foundation Business & Economics Quiz", "type": "Premium Academic", "date": "TBA", "premium": True, "note": "🌟 Great academic base! Sharpen your knowledge against peers."})
            elif year == 2:
                opps.append({"name": "National Finance & Strategy Case Challenge", "type": "Premium Academic", "date": "22 April", "premium": True, "note": "🌟 Compete with top minds by solving real-world corporate strategy cases."})
            else:
                opps.append({"name": "Pre-Placement Investment Banking Workshop", "type": "Premium Academic", "date": "May", "premium": True, "note": "🌟 Polish your stellar profile for top-tier corporate placements."})
        
        else: 
            if year == 1:
                opps.append({"name": "University Freshers Debate & Essay Fest", "type": "Premium Academic", "date": "Next Month", "premium": True, "note": "🌟 Express your strong academic thoughts on a bigger platform."})
            elif year == 2:
                opps.append({"name": "National Model United Nations (MUN)", "type": "Premium Academic", "date": "18 April", "premium": True, "note": "🌟 Use your analytical skills in policy drafting and diplomacy."})
            else:
                opps.append({"name": "National Level Research & Policy Conference", "type": "Premium Academic", "date": "May", "premium": True, "note": "🌟 Your academics are stellar! Try publishing and presenting a research paper."})
                
    elif cgpa_val < 7.0:
        if year == 1:
            opps.append({"name": "First-Year Transition & Exam Strategy Workshop", "type": "Academic Support", "date": "Upcoming Week", "premium": False, "note": "📚 Build a strong base early on! Use the 'Study Material' tab to boost your grades safely."})
        elif year == 2:
            opps.append({"name": "Core Subject Peer Tutoring & Mentorship", "type": "Academic Support", "date": "Ongoing", "premium": False, "note": "📚 Second year gets tough. Join peer study groups to clear concepts and improve your CGPA."})
        else:
            opps.append({"name": "Final Year Intensive Grade Improvement Bootcamp", "type": "Academic Support", "date": "Next Weekend", "premium": False, "note": "📚 It's not too late to push your CGPA up before graduation. Focus on High-Yield topics!"})

    if 'Social Responsibility' in black_areas:
        opps.append({"name": "Campus NGO Orientation & Weekend Outreach", "type": "Social Responsibility", "date": "Every Sunday", "premium": False,
                     "note": "🌱 We noticed your social involvement is a bit low right now. Don't worry, every expert was once a beginner! Try this beginner-friendly drive."})
    
    if 'Physical Health' in black_areas:
        opps.append({"name": "Beginner's 3K Campus Run & Yoga Camp", "type": "Physical Well-being", "date": "Next Saturday", "premium": False,
                     "note": "🏃‍♂️ Taking a break from studies is crucial. Join this easy, stress-free physical activity to refresh your mind!"})
                     
    if 'Research' in black_areas and cgpa_val >= 6.0:
        if year <= 2:
            opps.append({"name": "Intro to Research Paper Writing Workshop", "type": "Research Skills", "date": "Upcoming Week", "premium": False,
                         "note": "🔬 Never written a research paper? No problem! This beginner workshop is the perfect place to start."})
        else:
            opps.append({"name": "Final Year Thesis & Project Formatting Seminar", "type": "Research Skills", "date": "TBA", "premium": False,
                         "note": "🔬 Essential for final year students. Learn how to document your projects properly."})
                     
    if 'Literacy' in black_areas: 
        if any(k in course_lower for k in ['cs', 'computer', 'science']):
            opps.append({"name": "Beginner GitHub & Tech Resume Workshop", "type": "Skill Development", "date": "Friday Evening", "premium": False, "note": "💡 Start building your tech portfolio! Essential for practical industry knowledge."})
        elif any(k in course_lower for k in ['commerce', 'eco', 'finance']):
            opps.append({"name": "Excel Basics & Financial Modeling 101", "type": "Skill Development", "date": "Friday Evening", "premium": False, "note": "💡 Practical skills matter! Learn the absolute basics used in the corporate world."})
        else:
            opps.append({"name": "Content Writing & Digital Communication Basics", "type": "Skill Development", "date": "Friday Evening", "premium": False, "note": "💡 Boost your communication skills for better internship opportunities."})

    if not opps:
        opps.append({"name": "Inter-College Innovation & Leadership Challenge", "type": "Holistic Excellence", "date": "TBA", "premium": True, "note": "🏆 You are an all-rounder! Check out this premier leadership challenge to test all your skills."})

    return opps

def fetch_study_materials(stream_name, current_year):
    course = str(stream_name).lower()
    try: year_key = int(current_year)
    except: year_key = 1
    if year_key > 3: year_key = 3
    
    resources = {}
    resources["DU Official Exam Guidelines & Past Year Questions (PYQs)"] = {
        "syllabus": "Official DU Portal for General Exams and Pattern",
        "video": "https://www.youtube.com/results?search_query=Delhi+University+NEP+Exam+Pattern",
        "pyq1": "http://exam.du.ac.in/?Past-Question-Papers",
        "pyq3": "https://www.google.com/search?q=Delhi+University+Question+Papers+Drive+PDF"
    }
    
    base_subjects = {
        "cs": {
            1: ["Programming Fundamentals using C++", "Computer System Architecture"],
            2: ["Data Structures", "Operating Systems", "Design and Analysis of Algorithms"],
            3: ["Internet Technologies", "Theory of Computation", "Artificial Intelligence"]
        },
        "computer": { 
            1: ["Programming Fundamentals using C++", "Computer System Architecture"],
            2: ["Data Structures", "Operating Systems", "Design and Analysis of Algorithms"],
            3: ["Internet Technologies", "Theory of Computation", "Artificial Intelligence"]
        },
        "eco": {
            1: ["Introductory Microeconomics", "Mathematical Methods for Economics"],
            2: ["Intermediate Microeconomics", "Intermediate Macroeconomics", "Statistical Methods for Economics"],
            3: ["Indian Economy", "Development Economics", "International Economics"]
        },
        "commerce": {
            1: ["Financial Accounting", "Business Laws", "Business Organization and Management"],
            2: ["Corporate Accounting", "Company Law", "Income Tax Law and Practice"],
            3: ["Auditing and Corporate Governance", "Fundamentals of Financial Management", "GST and Customs Law"]
        },
        "b.com": { 
            1: ["Financial Accounting", "Business Laws", "Business Organization and Management"],
            2: ["Corporate Accounting", "Company Law", "Income Tax Law and Practice"],
            3: ["Auditing and Corporate Governance", "Fundamentals of Financial Management", "GST and Customs Law"]
        },
        "sanskrit": {
            1: ["Classical Sanskrit Literature (Poetry)", "Critical Survey of Sanskrit Literature"],
            2: ["Classical Sanskrit Literature (Drama)", "Poetics and Literary Criticism", "Indian Epigraphy"],
            3: ["Vedic Literature", "Ayurvedic Text", "Sanskrit Linguistics"]
        },
        "history": {
            1: ["History of India (Earliest times to c. 300 CE)", "Social Formations and Cultural Patterns of the Ancient World"],
            2: ["History of India (c. 750-1200)", "Rise of the Modern West"],
            3: ["History of Modern Europe", "History of India (c. 1605-1750)"]
        },
        "political": {
            1: ["Understanding Political Theory", "Constitutional Government and Democracy in India"],
            2: ["Political Processes and Institutions in Comparative Perspective", "Public Administration in India"],
            3: ["Classical Political Philosophy", "Indian Political Thought"]
        },
        "english": {
            1: ["Indian Classical Literature", "European Classical Literature"],
            2: ["British Poetry and Drama (14th to 17th Century)", "American Literature"],
            3: ["Women's Writing", "Modern European Drama", "Postcolonial Literatures"]
        },
        "physics": {
            1: ["Mathematical Physics-I", "Mechanics"],
            2: ["Mathematical Physics-II", "Thermal Physics", "Digital Systems and Applications"],
            3: ["Quantum Mechanics and Applications", "Solid State Physics"]
        },
        "math": {
            1: ["Calculus", "Algebra"],
            2: ["Real Analysis", "Differential Equations", "Theory of Real Functions"],
            3: ["Metric Spaces and Complex Analysis", "Ring Theory and Linear Algebra"]
        },
        "chemistry": {
            1: ["Atomic Structure and Chemical Bonding", "States of Matter and Ionic Equilibrium", "Fundamentals of Organic Chemistry"],
            2: ["Chemical Thermodynamics", "Solutions and Phase Equilibrium", "Chemistry of s- and p-Block Elements"],
            3: ["Transition Elements and Coordination Chemistry", "Quantum Chemistry and Spectroscopy", "Electrochemistry"]
        },
        "physical science": {
            1: ["Mechanics", "Atomic Structure and Chemical Bonding", "Calculus and Matrices"],
            2: ["Thermal Physics", "Chemical Thermodynamics", "Differential Equations"],
            3: ["Solid State Physics", "Quantum Chemistry", "Basic Instrumentation Skills"]
        }
    }

    found_match = False
    for keyword, y_data in base_subjects.items():
        if keyword in course:
            found_match = True
            subjects = y_data.get(year_key, y_data[3])
            
            for subj in subjects:
                if keyword in ['cs', 'computer']:
                    video_link = f"https://www.youtube.com/results?search_query=GeeksforGeeks+{subj.replace(' ', '+')}"
                    ref_book = "Standard Computer Science Text (e.g., Cormen/Galvin/Balagurusamy) as per NEP"
                else:
                    video_link = f"https://www.youtube.com/results?search_query={subj.replace(' ', '+')}+University+Lectures"
                    ref_book = f"Standard DU Recommended Reading for {subj} as per NEP"

                pyq1 = f"https://www.google.com/search?q=Delhi+University+{subj.replace(' ', '+')}+PYQ+PDF"
                pyq3 = f"https://www.google.com/search?q=DU+Buddy+{subj.replace(' ', '+')}+Previous+Year+Question+Papers"

                resources[subj] = {
                    "syllabus": f"NEP Syllabus Guidelines & Reference Books: {ref_book}",
                    "video": video_link,
                    "pyq1": pyq1,
                    "pyq3": pyq3
                }

    if not found_match:
        resources["General Foundation & AEC/VAC Subjects"] = {
            "syllabus": "NEP Syllabus Guidelines & Reference Books: DU Undergraduate Curriculum Framework (UGCF) Standard Readings",
            "video": "https://www.youtube.com/results?search_query=Delhi+University+NEP+VAC+AEC+Lectures",
            "pyq1": "https://www.google.com/search?q=Delhi+University+NEP+AEC+VAC+PYQ+PDF",
            "pyq3": "https://www.google.com/search?q=DU+Buddy+NEP+Previous+Year+Question+Papers"
        }

    return resources

def create_pdf(row):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Emojis ab ignore ho jayenge, ???? nahi aayega
    def clean(text):
        return str(text).encode('latin-1', 'ignore').decode('latin-1').strip()
    
    pdf.set_font("Times", 'B', 14) 
    pdf.cell(0, 10, "SmarTrack Student Report", ln=True, align='C')
    pdf.ln(5)
    
    pdf.set_font("Times", 'B', 12)
    pdf.cell(0, 10, "Student Profile", ln=True)
    pdf.set_font("Times", '', 12)
    
    pdf.cell(0, 8, f"Name: {clean(row['Name'])}", ln=True)
    pdf.cell(0, 8, f"Roll No: {clean(row.get('Roll_No', 'N/A'))}", ln=True)
    pdf.cell(0, 8, f"Stream: {clean(row['Stream'])} | Year: {row['Year']}", ln=True)
    pdf.cell(0, 8, f"Email: {clean(row.get('Email_Id', 'N/A'))}", ln=True)
    pdf.cell(0, 8, f"Phone: {clean(row.get('Phone_No', 'N/A'))}", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Times", 'B', 12)
    pdf.cell(0, 10, "Performance Summary", ln=True)
    pdf.set_font("Times", '', 12)
    pdf.cell(0, 8, f"Total SmarTrack Score: {row['Total SmarTrack Score']}", ln=True)
    pdf.cell(0, 8, f"Status: {clean(row['Status_Text'])}", ln=True)
    pdf.cell(0, 8, f"Batch Rank: #{int(row['Rank'])}", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Times", 'B', 12)
    pdf.cell(0, 10, "Score Breakdown", ln=True)
    
    # Attractive Table Styling
    pdf.set_font("Times", 'B', 12)
    pdf.set_fill_color(220, 230, 245) # Light blue header
    pdf.cell(140, 8, "Category", 1, 0, 'L', True)
    pdf.cell(40, 8, "Points", 1, 1, 'C', True)
    
    pdf.set_font("Times", '', 12)
    
    cgpa_formatted = f"{float(row['CGPA_Val']):.2f}" 
    
    data = [
        ("CGPA Score", f"{cgpa_formatted} (Pts: {row['CGPA_Pts']})"),
        ("Sports", row['Sports_Pts']),
        ("Research", row['Research_Pts']),
        ("NCC", row['NCC_Pts']),
        ("Outreach", row['Outreach_Pts']),
        ("Extra-Curricular", row['Extra_Pts']),
        ("Industry/Internship", row['Industry_Pts'])
    ]
    
    for i, (cat, score) in enumerate(data):
        fill = True if i % 2 == 0 else False
        if fill:
            pdf.set_fill_color(248, 248, 248) # Light grey for alternate rows
        pdf.cell(140, 8, cat, 1, 0, 'L', fill)
        pdf.cell(40, 8, str(score), 1, 1, 'C', fill)
    
    pdf.ln(10)
    
    pdf.set_font("Times", 'B', 12)
    pdf.cell(0, 10, "SmarTrack: Holistic Well-being Recommendation", ln=True)
    pdf.set_font("Times", 'I', 12)
    _, _, _, _, ai_reco = get_smartrack_analysis(row)
    pdf.multi_cell(0, 8, clean(ai_reco))
    pdf.ln(10)

    pdf.set_font("Times", 'B', 12)
    pdf.cell(0, 10, "Teacher Feedback", ln=True)
    pdf.set_font("Times", 'I', 12)
    
    fb_text = clean(row['Teacher_Feedback'])
    if fb_text.lower() == "no feedback yet":
        fb_text = ""
        
    pdf.multi_cell(0, 8, fb_text)
    
    # Footer fixed to the bottom of the current page
    pdf.set_y(-15)
    pdf.set_font("Times", 'I', 8) 
    pdf.cell(0, 10, "Generated by SmarTrack Digital System", align='C')
    
    return pdf.output(dest='S').encode('latin-1')

def process_and_score_data(df):
    if df is None: return None
    res = pd.DataFrame()
    
    name_col = next((c for c in df.columns if 'name' in c.lower() and 'activity' not in c.lower()), df.columns[1])
    res['Name'] = df[name_col].astype(str).str.strip()
    
    email_col = next((c for c in df.columns if 'email' in c.lower()), None)
    phone_col = next((c for c in df.columns if 'contact' in c.lower() or 'mobile' in c.lower() or 'phone' in c.lower()), None)
    roll_col = next((c for c in df.columns if 'roll' in c.lower()), None)
    
    res['Email_Id'] = df[email_col].astype(str) if email_col else "Not Available"
    res['Phone_No'] = df[phone_col].astype(str).str.replace(r'\.0$', '', regex=True).replace('nan', 'N/A') if phone_col else "N/A"
    res['Roll_No'] = df[roll_col].astype(str).str.replace(r'\.0$', '', regex=True).replace('nan', 'N/A') if roll_col else "N/A"

    col_hum = next((c for c in df.columns if 'humanities' in c.lower() and 'course' in c.lower()), None)
    col_sci = next((c for c in df.columns if 'science' in c.lower() and 'course' in c.lower()), None)
    col_comm = next((c for c in df.columns if 'commerce' in c.lower() and 'course' in c.lower()), None)

    def get_stream_and_category(row):
        def is_valid(val):
            v = str(val).lower().strip()
            return v not in ['nan', '', 'none', 'select', 'choose', 'select course', 'other'] and len(v) > 2
        
        for col in [col_hum, col_sci, col_comm]:
            if col and is_valid(row[col]):
                val = str(row[col]).strip()
                v_lower = val.lower()
                
                if 'political science' in v_lower or 'home science' in v_lower:
                    return val, "Humanities"
                
                if any(k in v_lower for k in ['b.a', 'ba ', 'ba(', 'humanities', 'arts']):
                    return val, "Humanities"
                if any(k in v_lower for k in ['b.com', 'bcom', 'commerce', 'management']):
                    return val, "Commerce"
                if any(k in v_lower for k in ['b.sc', 'bsc', 'science']):
                    return val, "Science"
                    
                if 'eco' in v_lower or 'history' in v_lower or 'english' in v_lower: return val, "Humanities"
                if 'computer' in v_lower or 'math' in v_lower or 'physics' in v_lower: return val, "Science"

        if col_hum and is_valid(row[col_hum]): return str(row[col_hum]).strip(), "Humanities"
        if col_sci and is_valid(row[col_sci]): return str(row[col_sci]).strip(), "Science"
        if col_comm and is_valid(row[col_comm]): return str(row[col_comm]).strip(), "Commerce"
        return "Unknown", "General"

    stream_data = df.apply(get_stream_and_category, axis=1, result_type='expand')
    res['Stream'] = stream_data[0]
    res['Category_Main'] = stream_data[1]

    sem_col = next((c for c in df.columns if 'sem' in c.lower() and len(c) < 10), None)
    def get_year_from_sem(val):
        try: return (int(re.search(r'\d+', str(val)).group()) + 1) // 2
        except: return 1
    res['Year'] = df[sem_col].apply(get_year_from_sem) if sem_col else 1

    cgpa_col = next((c for c in df.columns if 'average cgpa' in c.lower() or 'cgpa' in c.lower()), None)
    if not cgpa_col:
          sgpa_cols = [c for c in df.columns if 'sgpa' in c.lower()]
          res['CGPA_Raw'] = df[sgpa_cols].apply(pd.to_numeric, errors='coerce').mean(axis=1).fillna(0) if sgpa_cols else 0.0
    else:
        res['CGPA_Raw'] = df[cgpa_col].apply(lambda x: float(x) if str(x).replace('.','',1).isdigit() else 0.0)

    res['Teacher_Feedback'] = df['Teacher_Feedback'] if 'Teacher_Feedback' in df.columns else "No feedback yet"
    
    def get_cgpa_pts(row):
        try:
            val = float(row['CGPA_Raw']); cat = str(row['Category_Main']).lower()
            pts = 5.0 if val >= 8 else (4.0 if val >= 7 else (3.0 if val >= 6 else 0.0)) if ('humanities' in cat or 'art' in cat) else \
                  5.0 if val >= 9 else (4.0 if val >= 8 else (3.0 if val >= 7 else (2.0 if val >= 6 else 0.0)))
            return pts, val
        except: return 0.0, 0.0
    cgpa_data = res.apply(get_cgpa_pts, axis=1, result_type='expand')
    res['CGPA_Pts'] = cgpa_data[0]; res['CGPA_Val'] = cgpa_data[1]

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
        for col in df.columns:
            cat_key = detect_category_smart(col)
            if cat_key: current_scores[cat_key] += calculate_points_for_text(row[col])
        for k in current_scores: final_scores[k].append(min(current_scores[k], 5.0))
            
    for k, v in final_scores.items(): res[f'{k}_Pts'] = v

    res['Total SmarTrack Score'] = res['CGPA_Pts'] + res['Sports_Pts'] + res['Research_Pts'] + res['NCC_Pts'] + res['Outreach_Pts'] + res['Extra_Pts'] + res['Industry_Pts']
    res['Rank'] = res.groupby(['Stream', 'Year'])['Total SmarTrack Score'].rank(ascending=False, method='min')
    
    res['Is_All_Rounder'] = False
    def mark_all_rounders(group):
        if not group.empty:
            top_idx = group.sort_values(by=['Total SmarTrack Score', 'CGPA_Val'], ascending=[False, False]).index[0]
            top_student = res.loc[top_idx]
            if top_student['CGPA_Val'] >= 6.0 and (top_student['Total SmarTrack Score'] - top_student['CGPA_Pts']) > 0:
                res.loc[top_idx, 'Is_All_Rounder'] = True
        return group
    if not res.empty: res.groupby(['Stream', 'Year'], group_keys=False).apply(mark_all_rounders)

    def get_dynamic_status(row):
        if row['CGPA_Val'] < 6.0: return "Needs Improvement", "🔴"
        elif row['Is_All_Rounder']: return "Excellent", "🟢"
        elif row['Rank'] <= 3: return "Good", "🔵"
        else: return "Average", "🟡"

    status_data = res.apply(get_dynamic_status, axis=1)
    res['Status_Text'] = [x[0] for x in status_data]; res['Status_Icon'] = [x[1] for x in status_data]

    def generate_display_name(row):
        name = row['Name']
        if row['Is_All_Rounder']: name = f"🏅 {name}"
        if row['Status_Text'] == "Needs Improvement": name = f"{name} 🔴"
        return name
    res['Display_Name'] = res.apply(generate_display_name, axis=1)
    res['Original_Index'] = df.index
    
    return res

def feedback_section(student_name, current_feedback, unique_key_suffix):
    clean_name = student_name.replace('🏅 ', '').replace(' 🔴', '').strip()
    with st.form(key=f"fb_{clean_name}_{unique_key_suffix}"):
        st.write(f"📝 Feedback for {clean_name}")
        
        display_val = "" if current_feedback == "No feedback yet" else current_feedback
        feedback_text = st.text_area("Enter Feedback:", value=display_val, height=100)
        
        c1, c2 = st.columns([0.4, 0.6])
        if c1.form_submit_button("💾 Save / Update"):
            df_local = pd.read_csv("student_data.csv") if os.path.exists("student_data.csv") else pd.DataFrame(columns=['Name', 'Teacher_Feedback'])
            df_local = df_local[df_local['Name'] != clean_name]
            if feedback_text.strip(): df_local = pd.concat([df_local, pd.DataFrame({'Name': [clean_name], 'Teacher_Feedback': [feedback_text]})], ignore_index=True)
            df_local.to_csv("student_data.csv", index=False)
            st.success(f"✅ Feedback updated for {clean_name}"); st.session_state["df"] = load_data(); st.rerun()
        if c2.form_submit_button("🗑️ Delete Feedback", type="primary"):
            if os.path.exists("student_data.csv"):
                df_local = pd.read_csv("student_data.csv")
                df_local = df_local[df_local['Name'] != clean_name]
                df_local.to_csv("student_data.csv", index=False)
                st.success(f"🗑️ Feedback deleted for {clean_name}"); st.session_state["df"] = load_data(); st.rerun()

# ==========================================
# 4. MAIN APP LAYOUT
# ==========================================
if "df" not in st.session_state: st.session_state["df"] = load_data()

st.sidebar.title("🎓 SmarTrack")

if st.sidebar.button("🔄 Refresh Data"):
    st.session_state["df"] = load_data()
    st.rerun()

df_raw = st.session_state["df"]

if df_raw is not None:
    df = process_and_score_data(df_raw)
    if df is not None: df = df[df['Category_Main'] != 'General']
    
    if df is not None and not df.empty:
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["🎓 Student Dashboard", "📉 Remedial Tracker", "🏆 Hall of Fame", "🌟 Top Performers", "📚 Study Material"])
        
        # --- TAB 1: DASHBOARD ---
        with tab1:
            st.sidebar.markdown("---")
            st.sidebar.subheader("Filter Stream")
            sel_stream = None; sel_year = None
            main_cats = [x for x in sorted(df['Category_Main'].unique()) if str(x).lower() != 'nan']
            
            def on_stream_change(current_cat):
                for cat in main_cats:
                    if cat != current_cat and f"radio_{cat}" in st.session_state: st.session_state[f"radio_{cat}"] = None

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
            
            filtered_df = df.copy()
            if sel_stream:
                filtered_df = filtered_df[filtered_df['Stream'] == sel_stream]
                if sel_year: filtered_df = filtered_df[filtered_df['Year'] == sel_year]
            
            if sel_stream and sel_year:
                if not filtered_df.empty:
                    student_options = sorted(filtered_df['Display_Name'].unique())
                    head_col1, head_col2 = st.columns([0.65, 0.35])
                    with head_col2:
                        sel_student_display = st.selectbox("🔍 Switch Student", student_options, label_visibility="collapsed")
                        marksheet_col = next((c for c in df_raw.columns if 'upload' in c.lower() and 'marksheet' in c.lower()), None)
                        if sel_student_display:
                            orig_idx = filtered_df[filtered_df['Display_Name'] == sel_student_display].iloc[0]['Original_Index']
                            if marksheet_col:
                                marksheet_link = str(df_raw.loc[orig_idx, marksheet_col]).strip()
                                if marksheet_link.lower() not in ['nan', '', 'none', 'no']:
                                    st.markdown(f"""<a href="{marksheet_link}" target="_blank" style="text-decoration: none;"><button style="width: 100%; margin-top: 5px; background-color: #f8f9fa; border: 1px solid #ced4da; padding: 6px 12px; border-radius: 5px; cursor: pointer; color: #0d6efd; font-weight: 600; font-size: 14px;">📄 View Marksheet PDF</button></a>""", unsafe_allow_html=True)

                    if sel_student_display:
                        row = filtered_df[filtered_df['Display_Name'] == sel_student_display].iloc[0]
                        raw_row = df_raw.iloc[row['Original_Index']]

                        badge_html = '<span style="background-color:#FFD700; color:black; padding:4px 12px; border-radius:15px; font-size:12px; font-weight:bold; margin-left:10px; vertical-align: middle; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">🏆 Year Topper</span>' if row['Is_All_Rounder'] else ""
                        status_html = f'<span style="background-color:#f8f9fa; color:#333; padding:4px 12px; border-radius:15px; font-size:12px; font-weight:600; border: 1px solid #dee2e6; margin-left: 5px; vertical-align: middle;">{row["Status_Icon"]} {row["Status_Text"]}</span>'
                        
                        email_display = row.get('Email_Id', 'N/A'); phone_display = row.get('Phone_No', 'N/A')

                        with head_col1:
                            st.markdown(f"""
                            <div style="padding-top: 5px;">
                                <h2 style="margin:0; padding:0; color:#212529; display:inline-block;">🎓 {row['Name']}</h2> {badge_html} {status_html}
                                <div style="font-size: 14px; color: #666; margin-top: 8px;"><b>{row['Stream']}</b> • Year {row['Year']}</div>
                                <div style="font-size: 13px; color: #888; margin-top: 2px;">📧 {email_display} &nbsp;|&nbsp; 📞 {phone_display}</div>
                            </div>""", unsafe_allow_html=True)
                        st.markdown("---")
                        
                        c1, c2, c3, c4, c5 = st.columns(5)
                        c1.metric("🏆 Total Score", f"{row['Total SmarTrack Score']}")
                        c2.metric("🎓 Avg. CGPA", f"{row['CGPA_Val']:.2f}")
                        c3.metric("📊 CGPA Points", f"{row['CGPA_Pts']}")
                        c4.metric("🚀 Activity Pts", f"{row['Total SmarTrack Score'] - row['CGPA_Pts']}")
                        c5.metric("📈 Batch Rank", f"#{int(row['Rank'])}")
                        st.markdown("---")

                        chart_data_map = {'Avg CGPA': row['CGPA_Pts'], 'Extra-Curricular': row['Extra_Pts'], 'Research': row['Research_Pts'], 'Outreach': row['Outreach_Pts'], 'Sports': row['Sports_Pts'], 'NCC': row['NCC_Pts'], 'Industry': row['Industry_Pts']}
                        cats = list(chart_data_map.keys()); vals = list(chart_data_map.values())
                        vals_viz = [min(v, 5.0) for v in vals]
                        
                        cl, cr = st.columns(2)
                        with cl:
                            st.subheader("🕸️ Holistic Performance")
                            vals_r = vals_viz + vals_viz[:1]; cats_r = cats + cats[:1]
                            fig = go.Figure(go.Scatterpolar(r=vals_r, theta=cats_r, fill='toself', line_color='#00CC96', marker=dict(color='#00CC96')))
                            fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 5])), showlegend=False, height=400, margin=dict(l=40, r=40, t=20, b=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                            st.plotly_chart(fig, use_container_width=True)
                        with cr:
                            st.subheader("📊 Breakdown")
                            fig2 = px.bar(pd.DataFrame({'Category': cats, 'Points': vals}), x='Points', y='Category', orientation='h', text='Points', color='Points', color_continuous_scale='Mint')
                            fig2.update_layout(coloraxis_showscale=False, height=400, margin=dict(l=0, r=10, t=20, b=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                            st.plotly_chart(fig2, use_container_width=True)
                        st.markdown("---")
                        
                        st.markdown("### 📌 Detailed Activity Log")
                        details_df = get_activity_details_df(raw_row, df_raw.columns)
                        if not details_df.empty: st.dataframe(details_df, use_container_width=True, hide_index=True, column_config={"Proof": st.column_config.LinkColumn("Evidence", display_text="View Proof 🔗")})
                        else: st.info("ℹ️ No detailed activity records found for this student.")
                        
                        st.markdown("---")
                        
                        st.markdown(f"### 🧠 Personal Development Analysis for {row['Name']}")
                        areas, white_areas, gray_areas, black_areas, recommendation = get_smartrack_analysis(row)
                        
                        chart_col, text_col = st.columns([0.4, 0.6])
                        
                        with chart_col:
                            oh_df = pd.DataFrame(list(areas.items()), columns=['Category', 'Points'])
                            color_scale = [(0.0, "#ff4b4b"), (0.2, "#ff4b4b"), (0.2, "#ffa157"), (0.6, "#ffa157"), (0.6, "#00cc96"), (1.0, "#00cc96")]
                            
                            fig_oh = px.bar_polar(oh_df, r="Points", theta="Category", color="Points", color_continuous_scale=color_scale, template="plotly_white", title="Well-being Profile")
                            fig_oh.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 5], gridcolor="#e9ecef", tickfont=dict(color="#444")), angularaxis=dict(gridcolor="#e9ecef", tickfont=dict(color="#444"))), showlegend=False, height=400, margin=dict(l=50, r=50, t=60, b=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", title_font=dict(size=18), coloraxis_showscale=False)
                            st.plotly_chart(fig_oh, use_container_width=True)
                        
                        with text_col:
                            st.write(""); st.write("")
                            st.success(f"⚪ Strengths (White Areas): " + (", ".join(white_areas) if white_areas else "None yet"))
                            st.warning(f"🔘 Average (Gray Areas): " + (", ".join(gray_areas) if gray_areas else "None"))
                            st.error(f"⚫ Needs Focus (Black Areas): " + (", ".join(black_areas) if black_areas else "None! Amazing!"))
                            st.markdown("#### 💡 SmarTrack Recommendation")
                            st.info(recommendation)
                        
                        st.markdown("---")
                        
                        st.markdown("#### 🎯 Curated Opportunities For You")
                        st.write("Based on your performance profile and academic year, we recommend getting involved in these areas:")
                        
                        personalized_opps = fetch_personalized_opportunities(white_areas, black_areas, row['Stream'], row['CGPA_Val'], row['Year'])
                        for opp in personalized_opps:
                            st.markdown(f"- 🏆 {opp['name']} ({opp['date']}) - [{opp['type']}]")
                            if opp['premium']:
                                st.markdown(f"<div class='premium-note'>{opp['note']}</div>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"<div class='empathetic-note'>{opp['note']}</div>", unsafe_allow_html=True)
                        
                        st.markdown("---")

                        r_col1, r_col2 = st.columns([0.8, 0.2])
                        with r_col1:
                              st.markdown(f"#### ✍️ Update Feedback for {row['Name']}")
                              feedback_section(row['Name'], row['Teacher_Feedback'], "dashboard")
                        with r_col2:
                            st.write(""); st.write("")
                            
                            # Clean the file name so it has no illegal characters
                            safe_course_name = re.sub(r'[\\/*?:"<>|]', "", str(row['Stream']))
                            new_pdf_name = f"{row['Name']}_{safe_course_name}_Year{row['Year']}.pdf"
                            
                            st.download_button(label="📄 Download PDF Report", data=create_pdf(row), file_name=new_pdf_name, mime='application/pdf')
                else: st.info("⚠️ No students found in this Year/Course.")
            else: st.info("👈 Please select a Stream and Year from the sidebar to view student details.")

        # --- TAB 2: REMEDIAL TRACKER ---
        with tab2:
            st.markdown("<h2 class='centered-header'>📉 Remedial Tracker (CGPA < 6.0)</h2>", unsafe_allow_html=True)
            t2_c1, t2_c2, t2_c3 = st.columns(3)
            sel_rem_cat = t2_c1.selectbox("1️⃣ Select Stream:", [x for x in sorted(df['Category_Main'].unique()) if str(x).lower() != 'nan'], key="rem_cat")
            sel_rem_course = None; sel_rem_year = None
            if sel_rem_cat:
                sel_rem_course = t2_c2.selectbox("2️⃣ Select Course:", sorted([x for x in df[df['Category_Main'] == sel_rem_cat]['Stream'].unique() if str(x).lower() not in ['nan', 'unknown', 'none']]), key="rem_course")
                if sel_rem_course: sel_rem_year = t2_c3.selectbox("3️⃣ Select Year:", sorted(df[(df['Category_Main'] == sel_rem_cat) & (df['Stream'] == sel_rem_course)]['Year'].unique()), key="rem_year")

            st.markdown("---")
            if sel_rem_cat and sel_rem_course and sel_rem_year:
                weak_students = df[(df['Category_Main'] == sel_rem_cat) & (df['Stream'] == sel_rem_course) & (df['Year'] == sel_rem_year) & (df['Status_Text'] == "Needs Improvement")].copy()
                if not weak_students.empty:
                    st.dataframe(weak_students[['Name', 'Stream', 'Year', 'CGPA_Val', 'Total SmarTrack Score', 'Teacher_Feedback']], use_container_width=True)
                    st.markdown("---"); st.markdown("### ✍️ Update Remedial Student Feedback")
                    col_sel, col_form = st.columns([0.4, 0.6])
                    with col_sel: rem_student = st.selectbox("Select Student to Update:", weak_students['Name'].unique(), key="rem_select_fb")
                    with col_form:
                        if rem_student: feedback_section(rem_student, weak_students[weak_students['Name'] == rem_student]['Teacher_Feedback'].iloc[0], "remedial_tab")
                else: st.success("🎉 No remedial students found in this class! Everyone has CGPA >= 6.0.")
            else: st.info("👈 Please select Stream, Course, and Year to view remedial students.")

        # --- TAB 3: HALL OF FAME ---
        with tab3:
            st.markdown("<h2 class='centered-header'>🏆 Institution All-Rounders</h2>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns(3)
            for col, title, keywords in [(col1, "HUMANITIES", ["Humanities"]), (col2, "SCIENCE", ["Science", "Sciences"]), (col3, "COMMERCE", ["Commerce", "Management"])]:
                with col:
                    st.markdown(f"<h5 style='text-align:center; border-bottom:3px solid #FFD700; padding-bottom:5px; margin-bottom:15px; color:#444;'>{title}</h5>", unsafe_allow_html=True)
                    for year in range(1, 5):
                        topper = df[(df['Category_Main'].apply(lambda x: any(k.lower() in str(x).lower() for k in keywords))) & (df['Year'] == year) & (df['Is_All_Rounder'] == True)]
                        if not topper.empty:
                            row = topper.iloc[0]
                            st.markdown(f"""<div style="background-color: #fff; border: 1px solid #e0e0e0; border-left: 4px solid #00CC96; padding: 10px; border-radius: 6px; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 2px 4px rgba(0,0,0,0.05);"><div style="font-size: 11px; font-weight: bold; color: #888; width: 45px;">YEAR {year}</div><div style="font-weight: 700; font-size: 13px; color: #333; flex-grow: 1; padding: 0 8px;">🏅 {row['Name']}</div><div style="font-weight: 700; font-size: 13px; background: #f8f9fa; padding: 2px 6px; border-radius: 4px; border:1px solid #ddd; color: #333;">{row['Total SmarTrack Score']}</div></div>""", unsafe_allow_html=True)
                            with st.expander(f"📂 View Activity Details for {row['Name']}"):
                                details_df_hof = get_activity_details_df(df_raw.iloc[row['Original_Index']], df_raw.columns)
                                if not details_df_hof.empty: st.dataframe(details_df_hof, use_container_width=True, hide_index=True, column_config={"Proof": st.column_config.LinkColumn("Evidence", display_text="View Proof 🔗")})
                                else: st.write("No proof links found.")
                                marksheet_col = next((c for c in df_raw.columns if 'upload' in c.lower() and 'marksheet' in c.lower()), None)
                                if marksheet_col and str(df_raw.loc[row['Original_Index'], marksheet_col]).strip().lower() not in ['nan', '', 'none', 'no']:
                                    st.markdown(f"""<div style="margin-top: 5px; margin-bottom: 10px;"><a href="{str(df_raw.loc[row['Original_Index'], marksheet_col]).strip()}" target="_blank" style="text-decoration: none;"><button style="background-color: #f0f2f6; border: 1px solid #dce4ef; padding: 8px 16px; border-radius: 4px; color: #0068c9; font-weight: 600; cursor: pointer;">📄 View Marksheet</button></a></div>""", unsafe_allow_html=True)
                        else: st.markdown(f"""<div style="background-color: #f9f9f9; border: 1px dashed #ccc; padding: 10px; border-radius: 6px; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; opacity: 0.6;"><div style="font-size: 11px; font-weight: bold; color: #aaa; width: 45px;">YEAR {year}</div><div style="font-size: 12px; color: #aaa;">N/A</div></div>""", unsafe_allow_html=True)

            st.markdown("---"); st.subheader("📝 Batch Toppers Table & Feedback")
            all_toppers = df[df['Is_All_Rounder'] == True].sort_values(by=['Category_Main', 'Year']).copy()
            marksheet_col = next((c for c in df_raw.columns if 'upload' in c.lower() and 'marksheet' in c.lower()), None)
            all_toppers['Marksheet_View'] = df_raw.loc[all_toppers['Original_Index'], marksheet_col].values if marksheet_col else None
            st.dataframe(all_toppers[['Name', 'Category_Main', 'Stream', 'Year', 'Total SmarTrack Score', 'CGPA_Pts', 'Marksheet_View', 'Teacher_Feedback']], use_container_width=True, hide_index=True, column_config={"Marksheet_View": st.column_config.LinkColumn("Marksheet", display_text="📄 View PDF"), "CGPA_Pts": st.column_config.NumberColumn("CGPA Points", format="%.1f"), "Total SmarTrack Score": st.column_config.NumberColumn("Score", format="%.1f")})
            
            st.markdown("### ✍️ Update Topper Feedback")
            t_col_sel, t_col_form = st.columns([0.4, 0.6])
            with t_col_sel: topper_student = st.selectbox("Select Topper to Update:", all_toppers['Name'].unique(), key="topper_select_fb")
            with t_col_form:
                if topper_student: feedback_section(topper_student, all_toppers[all_toppers['Name'] == topper_student]['Teacher_Feedback'].iloc[0], "hof_tab")

        # --- TAB 4: TOP PERFORMERS ---
        with tab4:
            st.markdown("<h2 class='centered-header'>🌟 Top Performers (Course-wise)</h2>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            selected_cat = c1.selectbox("1️⃣ Select Stream Category:", [x for x in sorted(df['Category_Main'].unique()) if str(x).lower() != 'nan'])
            if selected_cat:
                selected_course = c2.selectbox("2️⃣ Select Course:", sorted([x for x in df[df['Category_Main'] == selected_cat]['Stream'].unique() if str(x).lower() not in ['nan', 'unknown', 'none']]))
                if selected_course:
                    selected_year = c3.selectbox("3️⃣ Select Year:", sorted(df[(df['Category_Main'] == selected_cat) & (df['Stream'] == selected_course)]['Year'].unique()))
                    if selected_year:
                        subset = df[(df['Stream'] == selected_course) & (df['Year'] == selected_year)]
                        subset = subset[(subset['Total SmarTrack Score'] - subset['CGPA_Pts']) > 0].sort_values(by='Total SmarTrack Score', ascending=False).head(3)
                        st.markdown("---")
                        if not subset.empty:
                            for i, (idx, row) in enumerate(subset.iterrows()):
                                rank_icon = ["🥇", "🥈", "🥉"][i] if i < 3 else f"#{i+1}"
                                st.markdown(f"""<div class="compact-topper-row"><div style="display:flex; align-items:center; width: 100%;"><div class="ct-rank">{rank_icon}</div><div style="flex-grow: 1;"><div class="ct-name">{row['Name']}</div><div class="ct-details">🆔 <b>{row.get('Roll_No', 'N/A')}</b> &nbsp;|&nbsp; 📞 {row.get('Phone_No', 'N/A')} &nbsp;|&nbsp; 📧 {row.get('Email_Id', 'N/A')}</div></div><div class="ct-stats"><div class="ct-score-box">🏆 {row['Total SmarTrack Score']} Pts</div><div class="ct-cgpa">🎓 CGPA: {row['CGPA_Val']:.2f}</div></div></div></div>""", unsafe_allow_html=True)
                                with st.expander(f"📂 View Activity Details for {row['Name']}"):
                                    details_df_tp = get_activity_details_df(df_raw.iloc[row['Original_Index']], df_raw.columns)
                                    if not details_df_tp.empty: st.dataframe(details_df_tp, use_container_width=True, hide_index=True, column_config={"Proof": st.column_config.LinkColumn("Evidence", display_text="View Proof 🔗")})
                                    else: st.write("No proof links found.")
                                    marksheet_col = next((c for c in df_raw.columns if 'upload' in c.lower() and 'marksheet' in c.lower()), None)
                                    if marksheet_col and str(df_raw.loc[row['Original_Index'], marksheet_col]).strip().lower() not in ['nan', '', 'none', 'no']:
                                        st.markdown(f"""<div style="margin-top: 5px; margin-bottom: 10px;"><a href="{str(df_raw.loc[row['Original_Index'], marksheet_col]).strip()}" target="_blank" style="text-decoration: none;"><button style="background-color: #f0f2f6; border: 1px solid #dce4ef; padding: 8px 16px; border-radius: 4px; color: #0068c9; font-weight: 600; cursor: pointer;">📄 View Marksheet</button></a></div>""", unsafe_allow_html=True)
                        else: st.info("ℹ️ No students in this class qualify as Top Performers yet (Must have Activity Points > 0).")
        
        # --- TAB 5: STUDY MATERIAL ---
        with tab5:
            st.markdown("<h2 class='centered-header'>📚 Study Material & NEP Syllabus Resources</h2>", unsafe_allow_html=True)
            st.write("Access authentic curated materials, subject-specific reference books, and Past Year Questions (PYQs) aligned with DU NEP framework.")
            
            sm_c1, sm_c2, sm_c3 = st.columns(3)
            sm_cat = sm_c1.selectbox("1️⃣ Select Stream Category:", [x for x in sorted(df['Category_Main'].unique()) if str(x).lower() != 'nan'], key="sm_cat")
            
            if sm_cat:
                sm_course = sm_c2.selectbox("2️⃣ Select Course:", sorted([x for x in df[df['Category_Main'] == sm_cat]['Stream'].unique() if str(x).lower() not in ['nan', 'unknown', 'none']]), key="sm_course")
                if sm_course:
                    sm_year = sm_c3.selectbox("3️⃣ Select Year:", [1, 2, 3, 4], key="sm_year")
                    
                    if sm_year:
                        st.markdown("---")
                        st.subheader(f"📖 Curated Subject Resources for {sm_course} (Year {sm_year})")
                        
                        resources = fetch_study_materials(sm_course, sm_year)
                        
                        if resources:
                            for subject, data in resources.items():
                                st.markdown(f"""
                                <div style="background-color: #f8f9fa; border-left: 4px solid #0d6efd; padding: 15px; margin-bottom: 15px; border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                                    <h4 style="margin-top: 0; margin-bottom: 8px; color: #212529;">📘 {subject}</h4>
                                    <div style="font-size: 13.5px; color: #198754; margin-bottom: 10px; background: #e8f5e9; padding: 5px 8px; border-radius: 4px; display: inline-block;">
                                        <b>📚 {data['syllabus']}</b>
                                    </div>
                                    <div style="margin-bottom: 12px;">
                                        <a href="{data['video']}" target="_blank" style="text-decoration: none; color: #dc3545; font-weight: 600; background: #ffe6e6; padding: 5px 10px; border-radius: 4px;">▶️ Watch Video Lectures</a>
                                    </div>
                                    <div style="font-size: 13.5px; color: #333; border-top: 1px solid #ddd; padding-top: 8px;">
                                        <b style="color: #444;">📝 Past Year Question Papers (PYQs):</b><br>
                                        <div style="margin-top: 5px;">
                                            <a href="{data['pyq1']}" target="_blank" style="text-decoration: none; color: #0d6efd; margin-right: 15px;">🔍 DU Archive Search</a>
                                            <a href="{data['pyq3']}" target="_blank" style="text-decoration: none; color: #0d6efd;">🎓 Student Portals</a>
                                        </div>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.info("Currently, no specific resources are mapped for this selection.")

else:
    st.warning("⚠️ No data found. Please check your Google Sheet link or upload a CSV file.")
