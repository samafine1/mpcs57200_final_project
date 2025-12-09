import streamlit as st
from openai import OpenAI
import PyPDF2
import json
import os
import time
import random
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Page Config & Custom CSS ---
st.set_page_config(page_title="Adaptive Critical Thinking Quiz", page_icon="🧠", layout="wide")

st.markdown("""
<style>
    .stProgress > div > div > div > div {
        background-color: #4CAF50;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #4CAF50;
        text-align: center;
    }
    .difficulty-badge {
        padding: 5px 10px;
        border-radius: 15px;
        font-weight: bold;
        color: white;
    }
    .timer-box {
        font-size: 20px;
        font-weight: bold;
        color: #d32f2f;
        padding: 10px;
        border: 2px solid #d32f2f;
        border-radius: 5px;
        text-align: center;
        margin-bottom: 10px;
    }
    .diff-easy { background-color: #2196F3; }
    .diff-medium { background-color: #FF9800; }
    .diff-hard { background-color: #f44336; }
    .diff-expert { background-color: #9C27B0; }
</style>
""", unsafe_allow_html=True)

# --- Persistence Functions ---
DATA_FILE = "quiz_data.json"

def load_topic_data(topic_name):
    """Loads the saved Elo for a specific topic."""
    if not os.path.exists(DATA_FILE):
        return 1200 # Default start
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            return data.get(topic_name, {}).get('elo', 1200)
    except:
        return 1200

def save_topic_data(topic_name, elo):
    """Saves the Elo for a specific topic."""
    data = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
        except:
            data = {}
    
    # Update data
    if topic_name not in data:
        data[topic_name] = {}
    data[topic_name]['elo'] = elo
    
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

# --- Helper Functions ---

def get_openai_client(api_key):
    return OpenAI(api_key=api_key)

@st.cache_data
def extract_text_from_pdf(pdf_file):
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        st.error(f"Error reading PDF: {e}")
        return None

def calculate_elo(current_elo, is_correct, question_difficulty_rating):
    """
    Updates Elo rating based on standard Elo formula.
    """
    k_factor = 32
    expected_score = 1 / (1 + 10 ** ((question_difficulty_rating - current_elo) / 400))
    actual_score = 1 if is_correct else 0
    new_elo = current_elo + k_factor * (actual_score - expected_score)
    return round(new_elo)

def get_difficulty_label(elo):
    """Returns label, css class, and an estimated 'rating' for that difficulty tier."""
    if elo < 1300: return "Easy", "diff-easy", 1100
    elif elo < 1500: return "Medium", "diff-medium", 1400
    elif elo < 1700: return "Hard", "diff-hard", 1600
    else: return "Expert", "diff-expert", 1800

def generate_question(client, context, elo, history):
    """
    Generates a question based on Elo and context, focusing on deep understanding.
    Randomly chooses between Multiple Choice or Detailed Problem/Analysis.
    """
    diff_label, _, _ = get_difficulty_label(elo)
    
    # Randomly select type
    q_type_selection = random.choice(["multiple_choice", "detailed_analysis"])
    
    if q_type_selection == "multiple_choice":
        q_inst = "Generate a Multiple Choice Question (4 options) that requires critical thinking, deduction, or calculation to solve."
    else:
        q_inst = "Generate a 'Detailed Problem' or 'Analysis Request' requiring a step-by-step solution, argument, or literary analysis."

    history_summary = "\n".join([f"Q: {h['question'][:50]}... | Result: {'Correct' if h['is_correct'] else 'Incorrect'}" for h in history[-3:]])

    system_prompt = f"""
    You are an expert Professor in the subject matter of the provided context.
    Context: {context[:50000]} (Use relevant sections).
    Current User Rating: {elo} (Level: {diff_label})
    
    Task: {q_inst}
    
    **CRITICAL GUIDELINES**:
    1. **Goal**: Test **Deep Understanding** and **Critical Thinking**, NOT memorization.
    2. **Relevance**: Questions must be tightly bound to the specific content/themes in the Context.
    3. **Math/Science Topics**: Require derivation, calculation, and application of principles. Use LaTeX (single $) for math.
    4. **Humanities/Literature/History Topics**: Require thematic analysis, evidence-based argumentation, comparison, or critique. Do NOT ask for simple dates or names; ask *why* or *how*.
    
    Output Format (JSON):
    {{
        "type": "{q_type_selection}",
        "question": "Question text...",
        "options": ["A) ...", "B) ...", "C) ...", "D) ..."] (Only for MC, otherwise null),
        "correct_option": "Option text" (Only for MC, used for internal validation),
        "hint": "A conceptual hint (e.g., a formula or a thematic lens) without giving away the answer.",
        "difficulty_rating_estimate": {elo}
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Avoid these recent questions: {history_summary}"}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"Error generating question: {e}")
        return None

def evaluate_answer(client, question_data, user_answer, context):
    """
    Evaluates answer focusing on reasoning, evidence, and methodology.
    """
    system_prompt = f"""
    You are a strict academic professor grading an assessment.
    
    Context: {context[:20000]}
    
    Question: {question_data['question']}
    Question Type: {question_data.get('type', 'detailed_analysis')}
    Correct Answer/Key (if available): {question_data.get('correct_option', 'N/A')}
    
    Student Answer: "{user_answer}"
    
    Task: Grade the student's answer based on the subject type.
    
    Grading Rubric:
    1. **Accuracy/Validity**: Is the conclusion or argument factually/logically sound?
    2. **Depth/Methodology**: 
       - For Math/Science: Did they use the correct formula/derivation?
       - For Humanities: Did they provide specific evidence/reasoning from the text?
    3. **Completeness**: Did they address the core of the prompt?
    
    Output JSON:
    {{
        "is_correct": boolean (true if the core analysis/solution is sound),
        "score_percentage": integer (0-100),
        "explanation": "Detailed feedback on the reasoning, analysis, or derivation.",
        "model_answer": "The ideal step-by-step solution or analytical response.",
        "key_concepts_missed": ["Concept A", "Concept B"]
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Grade this solution."}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"is_correct": False, "explanation": f"Error: {e}", "score_percentage": 0}

def generate_analytics_report(client, history, context):
    history_str = json.dumps(history, indent=2)
    prompt = f"""
    Analyze this assessment session.
    Context Topic: {context[:500]}...
    History: {history_str}
    
    Generate a Markdown report:
    1. **Critical Thinking Skills**: Assessment of logic, analysis, and application.
    2. **Conceptual Gaps**: Specific themes, formulas, or ideas struggled with.
    3. **Study Plan**: 3 concrete areas to review or practice.
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": "You are an expert academic advisor."}, {"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# --- Session State Init ---
if 'quiz_state' not in st.session_state:
    st.session_state.quiz_state = {
        "active": False,
        "finished": False,
        "context": "",
        "topic_name": "",
        "history": [],
        "elo": 1200,
        "streak": 0,
        "total_score": 0,
        "current_q": None,
        "feedback": None,
        "q_count": 0,
        "start_time": None,
        "q_start_timestamp": None, # For timer
        "hint_used": False
    }

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Settings")
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        api_key = st.text_input("OpenAI API Key", type="password")
    
    source = st.radio("Source Material", ["Topic", "Upload PDF"])
    context_input = ""
    topic_name_input = "" 

    if source == "Topic":
        topic_name_input = st.text_input("Enter Subject/Topic", "Literary Theory")
        context_input = topic_name_input
    else:
        pdf = st.file_uploader("Upload PDF", type="pdf")
        if pdf:
            topic_name_input = pdf.name 
            with st.spinner("Processing PDF..."):
                context_input = extract_text_from_pdf(pdf)
                if context_input: st.success("PDF Loaded!")

    q_limit = st.slider("Questions", 3, 20, 5)
    
    if st.button("Start Quiz"):
        if api_key and context_input:
            st.session_state.openai_key = api_key
            start_elo = load_topic_data(topic_name_input)
            
            st.session_state.quiz_state = {
                "active": True,
                "finished": False,
                "context": context_input,
                "topic_name": topic_name_input,
                "history": [],
                "elo": start_elo,
                "streak": 0,
                "total_score": 0,
                "current_q": None,
                "feedback": None,
                "q_count": 0,
                "start_time": time.time(),
                "q_start_timestamp": None,
                "hint_used": False
            }
            st.rerun()
        else:
            st.error("Missing API Key or Content")

# --- Main UI ---
st.title("🧠 Adaptive Critical Thinking Quiz")

qs = st.session_state.quiz_state

if not qs["active"]:
    st.info("👈 Setup your quiz in the sidebar to begin.")
    st.markdown("""
    ### Features
    * **Deep Understanding:** Tests analysis and application, not just recall.
    * **Any Subject:** Optimized for Math, Science, Literature, History, and more.
    * **2-Minute Timer:** Strict time limit per problem to test fluency.
    * **Adaptive Elo:** Difficulty scales with your performance.
    """)

elif qs["finished"]:
    st.balloons()
    st.header("📊 Quiz Results")
    
    # Summary Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Final Elo", qs["elo"], delta=qs["elo"] - qs["history"][0]["elo_after"] if qs["history"] else 0)
    c2.metric("Total Score", qs["total_score"])
    c3.metric("Max Streak", max([h.get('streak',0) for h in qs['history']] + [0]))
    accuracy = sum(1 for h in qs['history'] if h['is_correct']) / len(qs['history'])
    c4.metric("Accuracy", f"{accuracy:.0%}")

    # Charts
    if qs['history']:
        df = pd.DataFrame(qs['history'])
        df['q_num'] = range(1, len(df) + 1)
        
        tab1, tab2 = st.tabs(["Difficulty Trend", "Time & Score"])
        with tab1:
            fig = px.line(df, x='q_num', y='elo_after', title='Elo Rating Progression', markers=True)
            st.plotly_chart(fig, use_container_width=True)
        with tab2:
            fig2 = px.bar(df, x='q_num', y='score_gained', color='is_correct', title='Score per Question')
            st.plotly_chart(fig2, use_container_width=True)

    client = get_openai_client(st.session_state.openai_key)
    with st.spinner("Generating Learning Path..."):
        report = generate_analytics_report(client, qs['history'], qs['context'])
    
    st.markdown("### 📝 Personalized Study Plan")
    st.markdown(report)
    
    if st.button("Restart"):
        st.session_state.quiz_state["active"] = False
        st.rerun()

else:
    # --- HUD ---
    diff_name, diff_class, diff_rating_est = get_difficulty_label(qs["elo"])
    
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    with col1:
        st.write(f"**Question {qs['q_count'] + 1}/{q_limit}**")
        st.progress((qs['q_count']) / q_limit)
    with col2:
        st.markdown(f"<div class='metric-card'>🔥 Streak: {qs['streak']}</div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='metric-card'>🏆 Score: {qs['total_score']}</div>", unsafe_allow_html=True)
    with col4:
        st.markdown(f"<div class='metric-card {diff_class}'>{diff_name} ({qs['elo']})</div>", unsafe_allow_html=True)

    # --- Question Generation ---
    if not qs["current_q"]:
        client = get_openai_client(st.session_state.openai_key)
        with st.spinner("AI is formulating a challenge..."):
            q_data = generate_question(client, qs["context"], qs["elo"], qs["history"])
            if q_data:
                qs["current_q"] = q_data
                qs["hint_used"] = False
                qs["q_start_timestamp"] = time.time() # Start Timer
                st.rerun()

    # --- Question Display ---
    q_data = qs["current_q"]
    st.divider()
    
    # Timer Display Logic
    elapsed = time.time() - qs["q_start_timestamp"]
    remaining = 120 - elapsed
    
    if remaining > 0:
        st.markdown(f"<div class='timer-box'>⏳ Time Remaining: {int(remaining)}s</div>", unsafe_allow_html=True)
        # Warning if low
        if remaining < 30:
            st.warning("⚠️ Less than 30 seconds remaining!")
    else:
        st.markdown(f"<div class='timer-box' style='color:red; border-color:red;'>⌛ TIME EXPIRED</div>", unsafe_allow_html=True)

    st.markdown(f"### Question:")
    st.markdown(f"#### {q_data['question']}")
    
    # Hint System
    if not qs["hint_used"]:
        if st.button("💡 Get Hint (-50 pts)"):
            qs["hint_used"] = True
            st.rerun()
    else:
        st.info(f"💡 Hint: {q_data.get('hint', 'No hint available.')}")

    # Input Form
    with st.form("answer_form"):
        user_input = None
        widget_key = f"q_{qs['q_count']}"
        
        # Check Question Type
        if q_data.get('type') == 'multiple_choice' and q_data.get('options'):
            st.markdown("**Select the best response:**")
            user_input = st.radio("Options:", q_data['options'], key=f"radio_{widget_key}")
        else:
            st.markdown("**Your Response:**")
            st.caption("Provide your analysis, argument, or solution below.")
            user_input = st.text_area("Show your work/reasoning:", height=200, key=f"text_{widget_key}")
            
        submitted = st.form_submit_button("Submit Response")
        
        if submitted:
            # TIMER CHECK
            submit_time = time.time()
            if (submit_time - qs["q_start_timestamp"]) > 120:
                # Time Expired Logic
                qs["feedback"] = {
                    "is_correct": False,
                    "score_percentage": 0,
                    "explanation": "Time Limit Exceeded. You must submit your answer within 2 minutes.",
                    "model_answer": "N/A (Time Limit)",
                }
                # Penalty logic
                qs["elo"] = calculate_elo(qs["elo"], False, qs["elo"]) # Treat as loss against equal rating
                save_topic_data(qs["topic_name"], qs["elo"])
                qs["streak"] = 0
                st.rerun()
            
            elif not user_input:
                st.warning("Please provide a response.")
            else:
                client = get_openai_client(st.session_state.openai_key)
                with st.spinner("Analyzing your response..."):
                    result = evaluate_answer(client, q_data, user_input, qs["context"])
                    qs["feedback"] = result
                    
                    is_correct = result.get('is_correct', False)
                    score_pct = result.get('score_percentage', 0)
                    if score_pct > 70: is_correct = True
                    
                    score_base = score_pct 
                    if qs["hint_used"]: score_base -= 50
                    
                    _, _, q_diff_rating = get_difficulty_label(qs["elo"])
                    q_rating_actual = q_data.get('difficulty_rating_estimate', q_diff_rating)
                    
                    qs["elo"] = calculate_elo(qs["elo"], is_correct, q_rating_actual)
                    save_topic_data(qs["topic_name"], qs["elo"])
                    
                    qs["streak"] = qs["streak"] + 1 if is_correct else 0
                    qs["total_score"] += max(0, score_base)
                    
                    qs["history"].append({
                        "question": q_data['question'],
                        "user_answer": user_input,
                        "is_correct": is_correct,
                        "score_gained": max(0, score_base),
                        "elo_after": qs["elo"],
                        "streak": qs["streak"]
                    })
                    
                    st.rerun()

    # --- Feedback ---
    if qs["feedback"]:
        fb = qs["feedback"]
        score_display = fb.get('score_percentage', 0)
        
        # Check for timeout message specifically
        if "Time Limit Exceeded" in fb.get("explanation", ""):
             st.error(f"⏰ {fb['explanation']}")
        elif fb.get('is_correct', False) or score_display > 70:
            st.success(f"✅ Correct! (Score: {score_display}%)")
            st.balloons()
            st.markdown(f"**Feedback:** {fb['explanation']}")
        else:
            st.error(f"❌ Incorrect (Score: {score_display}%)")
            st.markdown(f"**Feedback:** {fb['explanation']}")
        
        missed = fb.get('key_concepts_missed', [])
        if missed:
            st.warning(f"⚠️ Concepts to Review: {', '.join(missed)}")
        
        with st.expander("Show Ideal Response/Solution"):
            # Use markdown for text heavy, latex for math heavy if detectable, 
            # but simple markdown is safer for mixed subjects
            st.markdown(fb.get('model_answer', 'N/A'))
        
        if st.button("Next Question ➡"):
            qs["current_q"] = None
            qs["feedback"] = None
            qs["q_count"] += 1
            if qs["q_count"] >= q_limit:
                qs["finished"] = True
            st.rerun()
            