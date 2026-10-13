import streamlit as st
import sqlite3
import random
import re
import json
from pathlib import Path
from datetime import date, datetime, timedelta
from collections import Counter

# Optional document readers
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    from docx import Document
except ImportError:
    Document = None

st.set_page_config(
    page_title="LearnMate AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = BASE_DIR / "uploads"
DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "learnmate.db"


def connect_db():
    return sqlite3.connect(DB_PATH, timeout=15)


def query(sql, params=(), fetch=False):
    with connect_db() as conn:
        cur = conn.execute(sql, params)
        rows = cur.fetchall() if fetch else None
        conn.commit()
        return rows


def initialize_database():
    with connect_db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            semester TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(name COLLATE NOCASE, semester)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            saved_path TEXT NOT NULL,
            material_type TEXT NOT NULL DEFAULT 'Notes',
            extracted_text TEXT NOT NULL DEFAULT '',
            uploaded_at TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            topic TEXT NOT NULL DEFAULT 'Mixed',
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            attempted_at TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS flashcards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT ''
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )""")
        # Migrate databases created by an earlier version.
        material_cols = [r[1] for r in conn.execute("PRAGMA table_info(materials)").fetchall()]
        if "material_type" not in material_cols:
            conn.execute("ALTER TABLE materials ADD COLUMN material_type TEXT NOT NULL DEFAULT 'Notes'")
        if "extracted_text" not in material_cols:
            conn.execute("ALTER TABLE materials ADD COLUMN extracted_text TEXT NOT NULL DEFAULT ''")
        flash_cols = [r[1] for r in conn.execute("PRAGMA table_info(flashcards)").fetchall()]
        if "created_at" not in flash_cols:
            conn.execute("ALTER TABLE flashcards ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")
        conn.commit()


initialize_database()


def get_subjects():
    return query("SELECT id, name, semester FROM subjects ORDER BY name COLLATE NOCASE", fetch=True)


def get_subject_name(subject_id):
    rows = query("SELECT name FROM subjects WHERE id=?", (subject_id,), fetch=True)
    return rows[0][0] if rows else "Unknown subject"


def get_performance(subject_id=None):
    if subject_id is None:
        rows = query("SELECT score,total FROM quiz_attempts", fetch=True)
    else:
        rows = query("SELECT score,total FROM quiz_attempts WHERE subject_id=?", (subject_id,), fetch=True)
    total = sum(int(r[1]) for r in rows)
    score = sum(int(r[0]) for r in rows)
    return {
        "attempts": len(rows),
        "correct": score,
        "total": total,
        "accuracy": (score / total * 100) if total else 0.0,
    }


def save_setting(key, value):
    query("""INSERT INTO settings(key,value) VALUES(?,?)
             ON CONFLICT(key) DO UPDATE SET value=excluded.value""", (key, str(value)))


def read_setting(key, default=""):
    rows = query("SELECT value FROM settings WHERE key=?", (key,), fetch=True)
    return rows[0][0] if rows else default


def get_materials(subject_id):
    return query("""SELECT id, filename, saved_path, material_type, extracted_text, uploaded_at
                    FROM materials WHERE subject_id=? ORDER BY id DESC""",
                 (subject_id,), fetch=True)


# Built-in demo questions: useful immediately, even before uploading files.
QUESTION_BANK = {
    "Machine Learning": [
        ("Basics", "What is supervised learning?", ["Learning from labelled examples", "Learning without examples", "Learning only through rewards", "Deleting data"], 0, "Supervised learning uses labelled examples."),
        ("Basics", "What is overfitting?", ["A model generalizes perfectly", "A model learns training data too specifically", "A model has no parameters", "A model has no training data"], 1, "Overfitting occurs when a model fits training data too closely and generalizes poorly."),
        ("Algorithms", "Which algorithm can be used for classification?", ["Decision tree", "Bubble sort", "Binary search", "Merge sort"], 0, "Decision trees can be used for classification and regression."),
        ("Algorithms", "K-means is mainly used for:", ["Clustering", "Encryption", "Sorting", "Compilation"], 0, "K-means groups data into clusters."),
        ("Evaluation", "What does accuracy measure?", ["Correct predictions divided by all predictions", "Training time", "Number of features only", "Memory use only"], 0, "Accuracy is the fraction of predictions that are correct."),
    ],
    "Database Management Systems": [
        ("SQL", "What does SQL stand for?", ["Structured Query Language", "Simple Question List", "System Quality Logic", "Sequential Queue Language"], 0, "SQL stands for Structured Query Language."),
        ("Keys", "Which key uniquely identifies a row?", ["Foreign key", "Primary key", "Duplicate key", "Temporary key"], 1, "A primary key uniquely identifies a row."),
        ("SQL", "Which SQL command retrieves data?", ["SELECT", "REMOVE", "CHANGE", "DISPLAY EVERYTHING"], 0, "SELECT retrieves data from a table."),
        ("Normalization", "Database normalization primarily helps reduce:", ["Redundancy", "Security", "All tables", "Queries to zero"], 0, "Normalization structures data to reduce redundancy and anomalies."),
        ("Transactions", "What does ACID stand for in databases?", ["Atomicity, Consistency, Isolation, Durability", "Access, Control, Index, Data", "Add, Create, Insert, Delete", "None of these"], 0, "ACID describes key transaction properties."),
    ],
    "Computer Networks": [
        ("OSI Model", "How many layers are in the OSI model?", ["4", "5", "7", "9"], 2, "The OSI reference model has seven layers."),
        ("Protocols", "Which system resolves domain names?", ["DNS", "USB", "HTML", "JPEG"], 0, "DNS maps domain names to network records."),
        ("Devices", "Which device forwards packets between networks?", ["Router", "Keyboard", "Monitor", "Printer"], 0, "Routers forward packets between networks."),
        ("Transport Layer", "Which protocol is connection-oriented and reliable?", ["TCP", "UDP", "IP", "ARP"], 0, "TCP provides reliable, ordered delivery."),
        ("Transport Layer", "UDP is best described as:", ["Connectionless", "Always reliable", "A routing device", "A web language"], 0, "UDP is connectionless and does not guarantee delivery."),
    ],
    "Python Programming": [
        ("Basics", "Which keyword defines a Python function?", ["func", "define", "def", "function"], 2, "Python functions are defined with def."),
        ("Operators", "What is the result of 3 ** 2?", ["6", "9", "5", "8"], 1, "The ** operator performs exponentiation."),
        ("Types", "Which type represents True or False?", ["str", "bool", "list", "dict"], 1, "bool represents Boolean values."),
        ("Collections", "Which structure stores key-value pairs?", ["List", "Tuple", "Dictionary", "String"], 2, "A dictionary stores key-value pairs."),
        ("Loops", "Which keyword skips to the next loop iteration?", ["stop", "continue", "exit", "skip"], 1, "continue moves to the next iteration."),
    ],
    "Operating Systems": [
        ("Processes", "What is a process?", ["A program in execution", "A keyboard", "A database row", "A network cable"], 0, "A process is a program in execution."),
        ("Scheduling", "Which is a CPU scheduling algorithm?", ["Round Robin", "Binary Search", "Bubble Sort", "Hashing"], 0, "Round Robin assigns CPU time slices."),
        ("Memory", "Which memory is typically volatile?", ["RAM", "ROM", "DVD", "Flash drive"], 0, "RAM typically loses its contents when power is removed."),
        ("Concurrency", "A deadlock is a situation where:", ["Processes wait indefinitely for resources", "CPU is always fast", "Files are compressed", "Data is sorted"], 0, "Deadlock can occur when processes wait on one another in a cycle."),
    ],
    "Data Structures and Algorithms": [
        ("Stacks", "Which data structure follows LIFO?", ["Queue", "Stack", "Tree", "Graph"], 1, "A stack follows Last In, First Out."),
        ("Queues", "Which data structure follows FIFO?", ["Stack", "Queue", "Heap", "Tree"], 1, "A queue follows First In, First Out."),
        ("Searching", "Binary search on a sorted array has which time complexity?", ["O(n)", "O(log n)", "O(n²)", "Always O(1)"], 1, "Binary search halves the search interval each step."),
        ("Trees", "Which traversal visits left subtree, root, then right subtree?", ["Preorder", "Postorder", "Inorder", "Level order"], 2, "Inorder traversal visits left, root, and right."),
    ],
    "Software Engineering": [
        ("Testing", "What is a main goal of software testing?", ["Find defects and check requirements", "Increase file size", "Remove all documentation", "Avoid reviews"], 0, "Testing helps find defects and assess requirements."),
        ("Models", "Which development model has sequential phases?", ["Waterfall", "Random model", "No-planning model", "Hardware model"], 0, "Waterfall follows a sequence of development phases."),
        ("Requirements", "A functional requirement describes:", ["A system behavior or feature", "Desk colour", "Lunch break", "Computer brand"], 0, "Functional requirements describe what the system should do."),
    ],
    "Computer Organization": [
        ("CPU", "What does CPU stand for?", ["Central Processing Unit", "Computer Personal Utility", "Central Program User", "Control Power Unit"], 0, "CPU stands for Central Processing Unit."),
        ("Memory", "Which memory is generally volatile?", ["RAM", "ROM", "DVD", "Flash drive"], 0, "RAM is generally volatile."),
        ("Number Systems", "What is decimal 2 in binary?", ["01", "10", "11", "100"], 1, "Decimal 2 is binary 10."),
    ],
    "Web Development": [
        ("HTML", "What is HTML primarily used for?", ["Structuring web content", "Managing hardware", "Routing packets", "Database backup"], 0, "HTML structures web content."),
        ("CSS", "What is CSS primarily used for?", ["Styling web pages", "Storing database rows", "Compiling Python", "Routing packets"], 0, "CSS controls presentation and layout."),
        ("JavaScript", "JavaScript is commonly used to:", ["Add interactivity to web pages", "Replace all HTML", "Format hard drives", "Route internet packets"], 0, "JavaScript adds interactive behavior to web pages."),
    ],
    "Computer Science": [
        ("Basics", "Which component executes program instructions?", ["CPU", "Monitor", "Mouse", "Printer"], 0, "The CPU executes program instructions."),
        ("Data", "Which is an example of an input device?", ["Keyboard", "Monitor", "Speaker", "Projector"], 0, "A keyboard is an input device."),
    ],
}


def extract_text(filename, raw_bytes):
    ext = Path(filename).suffix.lower()
    try:
        if ext == ".txt":
            return raw_bytes.decode("utf-8", errors="ignore")
        if ext == ".pdf":
            if fitz is None:
                return ""
            doc = fitz.open(stream=raw_bytes, filetype="pdf")
            return "\n".join(page.get_text("text") for page in doc)
        if ext == ".docx":
            if Document is None:
                return ""
            import io
            doc = Document(io.BytesIO(raw_bytes))
            return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        return ""
    return ""


def normalize_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def get_subject_text(subject_id):
    rows = query("SELECT extracted_text FROM materials WHERE subject_id=?", (subject_id,), fetch=True)
    return "\n".join(r[0] for r in rows if r and r[0])


def split_sentences(text):
    text = re.sub(r"[\r\t]+", " ", text or "")
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [normalize_text(p).strip(" •-\t") for p in parts if len(normalize_text(p)) >= 35]


def important_questions(subject_id):
    rows = query("""SELECT filename, material_type, extracted_text FROM materials
                    WHERE subject_id=? ORDER BY id""", (subject_id,), fetch=True)
    if not rows:
        return [], "Upload textbook/notes and PYQs to build a document-based list."
    all_text = "\n".join(r[2] or "" for r in rows)
    pyq_text = "\n".join((r[2] or "") for r in rows if "pyq" in (r[1] or "").lower() or "previous" in (r[1] or "").lower())
    # Preserve question-like lines from extracted papers.
    candidates = []
    for line in re.split(r"[\n\r]+", all_text):
        line = normalize_text(line).strip(" •*-")
        if len(line) < 15 or len(line) > 260:
            continue
        if re.search(r"\b(explain|define|describe|discuss|compare|differentiate|derive|illustrate|what is|why|how|write a note|list the|state the|advantages|disadvantages)\b", line, re.I):
            candidates.append(line)
    counts = Counter(candidates)
    # Add useful textbook sentences as topics if no question-like lines were found.
    if not candidates:
        for s in split_sentences(all_text):
            if len(s) < 180:
                candidates.append("Explain: " + s.rstrip(".") + ".")
    ranked = []
    pyq_lines = set(normalize_text(x) for x in re.split(r"[\n\r]+", pyq_text) if normalize_text(x))
    for q, count in counts.most_common():
        score = 3 * count + (3 if q in pyq_lines else 0)
        ranked.append((q, score, count))
    if not ranked and candidates:
        ranked = [(q, 1, 1) for q in candidates]
    ranked.sort(key=lambda x: (-x[1], x[0].lower()))
    # Deduplicate nearly identical question text.
    result, seen = [], set()
    for q, score, count in ranked:
        key = re.sub(r"[^a-z0-9]+", "", q.lower())[:90]
        if key in seen:
            continue
        seen.add(key)
        result.append({"question": q, "priority": "High" if score >= 6 else "Medium", "mentions": count})
        if len(result) >= 30:
            break
    note = "Priority is a heuristic based on repeated question-like lines in the extracted documents. It is not a guarantee of exam appearance."
    return result, note


def topic_keywords(text):
    words = re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", (text or "").lower())
    stop = set("that this with from have were will your into than then them they their about which what when where how why also used use using based each other such more most some very can could should would these those there being been were".split())
    counts = Counter(w for w in words if w not in stop)
    return [w for w, _ in counts.most_common(30)]


def generate_document_mcqs(subject_id, topic, limit=10):
    text = get_subject_text(subject_id)
    if not text.strip():
        return []
    sentences = split_sentences(text)
    if topic and topic != "All extracted content":
        key = topic.lower()
        matching = [s for s in sentences if key in s.lower()]
        if matching:
            sentences = matching
    # Generate cautious, simple recall questions from statements. Distractors are extracted keywords.
    keywords = topic_keywords(text)
    result = []
    for sentence in sentences:
        words = re.findall(r"\b[A-Za-z][A-Za-z0-9-]{3,}\b", sentence)
        useful = [w for w in words if w.lower() not in {"which", "where", "there", "their", "about", "these", "those", "because", "should", "would", "could"}]
        if len(useful) < 5:
            continue
        answer = max(useful, key=lambda w: (len(w), w.lower()))
        if answer.lower() not in sentence.lower():
            continue
        masked = re.sub(re.escape(answer), "________", sentence, count=1, flags=re.I)
        distractors = []
        for w in keywords:
            if w.lower() != answer.lower() and w.lower() not in [d.lower() for d in distractors] and len(w) > 3:
                distractors.append(w)
            if len(distractors) == 3:
                break
        if len(distractors) < 3:
            continue
        opts = distractors + [answer]
        random.shuffle(opts)
        result.append({
            "topic": topic if topic != "All extracted content" else "Uploaded material",
            "question": f"Complete the statement based on your uploaded material: {masked}",
            "options": opts,
            "answer": opts.index(answer),
            "explanation": f"Source statement: {sentence}",
        })
        if len(result) >= limit:
            break
    return result


def all_questions_for_subject(subject_id):
    name = get_subject_name(subject_id)
    builtins = []
    for item in QUESTION_BANK.get(name, []):
        topic, question, options, answer, explanation = item
        builtins.append({"topic": topic, "question": question, "options": options, "answer": answer, "explanation": explanation, "source": "Built-in demo bank"})
    return builtins


def save_quiz_result(subject_id, topic, score, total):
    query("""INSERT INTO quiz_attempts(subject_id,topic,score,total,attempted_at)
             VALUES(?,?,?,?,?)""",
          (subject_id, topic or "Mixed", score, total, datetime.now().isoformat(timespec="seconds")))


def begin_quiz(subject_id, topic, number, use_uploaded):
    questions = []
    if use_uploaded:
        questions = generate_document_mcqs(subject_id, topic, max(number, 10))
    if not questions:
        name = get_subject_name(subject_id)
        for item in QUESTION_BANK.get(name, []):
            qtopic, question, options, answer, explanation = item
            questions.append({"topic": qtopic, "question": question, "options": options, "answer": answer, "explanation": explanation, "source": "Built-in demo bank"})
    if topic not in ("All topics", "All extracted content", ""):
        filtered = [q for q in questions if q.get("topic") == topic or topic.lower() in q.get("question", "").lower()]
        if filtered:
            questions = filtered
    if not questions:
        return False
    selected = random.sample(questions, min(number, len(questions)))
    st.session_state.quiz_questions = selected
    st.session_state.quiz_answers = {}
    st.session_state.quiz_index = 0
    st.session_state.quiz_started = True
    st.session_state.quiz_finished = False
    st.session_state.quiz_subject_id = subject_id
    st.session_state.quiz_topic = topic
    st.session_state.quiz_saved = False
    return True


def score_quiz():
    qs = st.session_state.quiz_questions
    answers = st.session_state.quiz_answers
    return sum(answers.get(i) == q["answer"] for i, q in enumerate(qs))


def reset_quiz():
    st.session_state.quiz_questions = []
    st.session_state.quiz_answers = {}
    st.session_state.quiz_index = 0
    st.session_state.quiz_started = False
    st.session_state.quiz_finished = False
    st.session_state.quiz_subject_id = None
    st.session_state.quiz_topic = ""
    st.session_state.quiz_saved = False


# Sidebar navigation
st.sidebar.title("🎓 LearnMate AI")
st.sidebar.caption("Your personal study companion")
page = st.sidebar.radio("Navigation", [
    "🏠 Dashboard", "📚 My Subjects", "📂 Upload Materials", "⭐ Important Questions",
    "📝 Take a Quiz", "📊 Performance", "🗓️ Study Planner", "🃏 Flashcards",
    "🤖 AI Study Advisor", "📖 Textbook Question Generator",
    "📝 PYQ Analyzer", "⚙️ Settings"
])
st.sidebar.divider()
st.sidebar.caption("Learn smarter, one topic at a time.")

# Dashboard
if page == "🏠 Dashboard":
    st.title("🎓 Welcome to LearnMate AI")
    st.write("Your personalized study space starts here.")
    subjects = get_subjects()
    perf = get_performance()
    cols = st.columns(4)
    cols[0].metric("📚 Subjects", len(subjects))
    cols[1].metric("📝 Quiz attempts", perf["attempts"])
    cols[2].metric("🎯 Questions answered", perf["total"])
    cols[3].metric("📈 Accuracy", f"{perf['accuracy']:.1f}%")
    st.divider()
    st.subheader("Your study workspace")
    cols = st.columns(3)
    cols[0].info("📚 **Subjects**\n\nAdd your semester subjects.")
    cols[1].info("📝 **Practice**\n\nTake quizzes and review explanations.")
    cols[2].info("📊 **Improve**\n\nTrack scores and find topics to revise.")
    st.subheader("My subjects")
    if not subjects:
        st.info("Open My Subjects to add your first subject.")
    else:
        for sid, name, sem in subjects:
            p = get_performance(sid)
            with st.container(border=True):
                st.write(f"**{name}** — {sem}")
                st.write(f"Quiz accuracy: {p['accuracy']:.1f}% · Attempts: {p['attempts']}")
                st.progress(min(1.0, p["accuracy"] / 100))

# Subjects
elif page == "📚 My Subjects":
    st.title("📚 My Subjects")
    st.caption("Add each subject once. Names should match common built-in banks for immediate demo questions.")
    with st.form("add_subject_form", clear_on_submit=True):
        name = st.text_input("Subject name", placeholder="e.g. Computer Networks")
        semester = st.selectbox("Semester", [f"Semester {i}" for i in range(1, 9)] + ["Other"])
        submitted = st.form_submit_button("➕ Add subject")
    if submitted:
        if not name.strip():
            st.error("Enter a subject name.")
        else:
            try:
                query("INSERT INTO subjects(name,semester,created_at) VALUES(?,?,?)",
                      (name.strip(), semester, datetime.now().isoformat(timespec="seconds")))
                st.success(f"Added {name.strip()}.")
                st.rerun()
            except sqlite3.IntegrityError:
                st.warning("That subject already exists for this semester.")
    st.divider()
    subjects = get_subjects()
    if not subjects:
        st.info("No subjects yet.")
    for sid, name, sem in subjects:
        c1, c2 = st.columns([5, 1])
        c1.write(f"**{name}** — {sem}")
        if c2.button("Delete", key=f"delete_subject_{sid}"):
            # Delete associated records too.
            for table in ("materials", "quiz_attempts", "flashcards"):
                query(f"DELETE FROM {table} WHERE subject_id=?", (sid,))
            query("DELETE FROM subjects WHERE id=?", (sid,))
            st.rerun()

# Upload materials
elif page == "📂 Upload Materials":
    st.title("📂 Upload Study Materials")
    st.write("Upload textbook chapters, notes, syllabus, and PYQs. PDF text extraction works for text-based PDFs; scanned PDFs need OCR and are not automatically readable in this demo.")
    subjects = get_subjects()
    if not subjects:
        st.warning("Add a subject first.")
    else:
        mapping = {f"{n} ({sem})": sid for sid, n, sem in subjects}
        selected = st.selectbox("Choose subject", list(mapping))
        material_type = st.selectbox("Material type", ["Textbook", "Notes", "Syllabus", "PYQ / Previous-year paper", "Other"])
        files = st.file_uploader("Choose files", type=["pdf", "txt", "docx"], accept_multiple_files=True)
        if st.button("💾 Save materials"):
            if not files:
                st.warning("Choose at least one PDF, TXT, or DOCX file.")
            else:
                count = 0
                for f in files:
                    original_name = Path(f.name).name
                    unique = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{random.randint(1000,9999)}_{original_name}"
                    dest = UPLOAD_DIR / unique
                    raw = f.getvalue()
                    dest.write_bytes(raw)
                    extracted = extract_text(original_name, raw)
                    query("""INSERT INTO materials(subject_id,filename,saved_path,material_type,extracted_text,uploaded_at)
                             VALUES(?,?,?,?,?,?)""",
                          (mapping[selected], original_name, str(dest), material_type, extracted,
                           datetime.now().isoformat(timespec="seconds")))
                    count += 1
                st.success(f"Saved {count} file(s).")
                st.rerun()
    st.divider()
    st.subheader("Saved materials")
    for sid, name, sem in get_subjects():
        mats = get_materials(sid)
        if mats:
            with st.expander(f"{name} ({sem}) — {len(mats)} file(s)"):
                for mid, filename, path, kind, extracted, uploaded_at in mats:
                    st.write(f"**{filename}** · {kind} · {uploaded_at}")
                    if extracted.strip():
                        st.caption(f"Extracted {len(extracted.split())} words.")
                    else:
                        st.warning("No text extracted. If this is a scanned PDF, OCR is needed.")
                    if Path(path).exists():
                        st.download_button("Download", Path(path).read_bytes(), file_name=filename, key=f"mat_download_{mid}")
                    if st.button("Delete file", key=f"delete_material_{mid}"):
                        try:
                            Path(path).unlink(missing_ok=True)
                        except Exception:
                            pass
                        query("DELETE FROM materials WHERE id=?", (mid,))
                        st.rerun()

# Important questions
elif page == "⭐ Important Questions":
    st.title("⭐ Important Questions & Passing Package")
    st.write("Choose a subject to review question-like lines from uploaded documents. Repeated PYQ lines receive higher priority when they are extracted clearly.")
    subjects = get_subjects()
    if not subjects:
        st.warning("Add a subject first.")
    else:
        mapping = {f"{n} ({sem})": sid for sid, n, sem in subjects}
        selected = st.selectbox("Subject", list(mapping), key="important_subject")
        sid = mapping[selected]
        mats = get_materials(sid)
        if not mats:
            st.info("Upload textbook/notes and PYQs in Upload Materials to build a document-based list.")
        questions, note = important_questions(sid)
        if questions:
            st.caption(note)
            st.subheader("High-priority / passing package")
            st.write("Start with High priority, then cover Medium priority. This is a study aid, not a guarantee of exam questions.")
            for i, q in enumerate(questions, 1):
                with st.container(border=True):
                    st.markdown(f"**{i}. [{q['priority']}] {q['question']}**")
                    st.caption(f"Question-like line occurrences in extracted material: {q['mentions']}")
            st.download_button("⬇️ Download question list (.txt)",
                               "\n".join(f"{i}. [{q['priority']}] {q['question']}" for i, q in enumerate(questions, 1)),
                               file_name=f"{get_subject_name(sid).replace(' ','_')}_important_questions.txt")
        elif mats:
            st.warning("Files are saved, but no usable question text was extracted. Try a text-based PDF, TXT, or DOCX file.")
        st.divider()
        st.subheader("Built-in practice topics")
        builtin = all_questions_for_subject(sid)
        if builtin:
            for i, q in enumerate(builtin, 1):
                st.write(f"{i}. {q['question']}")
        else:
            st.info("No built-in bank for this exact subject name. You can still use document-based questions after uploading readable material.")

# Quiz
elif page == "📝 Take a Quiz":
    st.title("📝 Take a Quiz")
    subjects = get_subjects()
    if not subjects:
        st.warning("Add a subject first.")
    else:
        mapping = {f"{n} ({sem})": sid for sid, n, sem in subjects}
        selected = st.selectbox("Choose subject", list(mapping), key="quiz_subject_select")
        sid = mapping[selected]
        builtin = all_questions_for_subject(sid)
        doc_text = get_subject_text(sid)
        source_choice = st.radio("Question source", ["Uploaded materials first", "Built-in demo questions"], horizontal=True)
        use_uploaded = source_choice == "Uploaded materials first"
        if use_uploaded and not doc_text.strip():
            st.info("No readable extracted text for this subject yet. The quiz will use built-in questions if available.")
        topics = ["All topics", "All extracted content"]
        topics += sorted({q["topic"] for q in builtin})
        topic = st.selectbox("Topic", list(dict.fromkeys(topics)), key="quiz_topic_select")
        max_available = max(1, len(builtin), 10 if doc_text.strip() else 1)
        number = st.slider("Number of questions", 1, min(20, max_available), min(5, min(20, max_available)))
        if st.button("🚀 Start / Restart quiz"):
            ok = begin_quiz(sid, topic, number, use_uploaded)
            if ok:
                st.rerun()
            else:
                st.warning("No questions could be made. Upload readable notes/PYQs or choose a subject with a built-in bank.")
    if st.session_state.get("quiz_started"):
        qs = st.session_state.quiz_questions
        total = len(qs)
        if not st.session_state.quiz_finished:
            idx = st.session_state.quiz_index
            q = qs[idx]
            st.divider()
            st.subheader(f"Question {idx + 1} of {total}")
            st.progress((idx + 1) / total)
            st.write(f"**{q['question']}**")
            if q.get("source"):
                st.caption(q["source"])
            previous = st.session_state.quiz_answers.get(idx)
            choice = st.radio("Choose an answer", q["options"],
                              index=previous if previous is not None else 0,
                              key=f"quiz_choice_{idx}_{len(qs)}")
            c1, c2 = st.columns(2)
            if c1.button("Save answer and continue", key=f"save_answer_{idx}"):
                st.session_state.quiz_answers[idx] = q["options"].index(choice)
                if idx < total - 1:
                    st.session_state.quiz_index += 1
                else:
                    st.session_state.quiz_finished = True
                st.rerun()
            if c2.button("Previous", disabled=idx == 0, key=f"previous_{idx}"):
                st.session_state.quiz_answers[idx] = q["options"].index(choice)
                st.session_state.quiz_index = max(0, idx - 1)
                st.rerun()
        else:
            score = score_quiz()
            if not st.session_state.get("quiz_saved", False):
                save_quiz_result(st.session_state.quiz_subject_id, st.session_state.quiz_topic, score, len(qs))
                st.session_state.quiz_saved = True
            st.success(f"Quiz complete! Score: {score}/{len(qs)} ({score/len(qs)*100:.1f}%)")
            st.write("### Review answers")
            for i, q in enumerate(qs):
                chosen = st.session_state.quiz_answers.get(i)
                correct = q["answer"]
                with st.expander(f"{'✅' if chosen == correct else '❌'} {i+1}. {q['question']}"):
                    st.write(f"Your answer: {q['options'][chosen] if chosen is not None else 'Not answered'}")
                    st.write(f"Correct answer: {q['options'][correct]}")
                    st.write(q.get("explanation", ""))
            if st.button("Take another quiz"):
                reset_quiz()
                st.rerun()

# Performance
elif page == "📊 Performance":
    st.title("📊 Performance Analysis")
    subjects = get_subjects()
    perf = get_performance()
    c1, c2, c3 = st.columns(3)
    c1.metric("Quiz attempts", perf["attempts"])
    c2.metric("Questions scored", perf["total"])
    c3.metric("Overall accuracy", f"{perf['accuracy']:.1f}%")
    st.divider()
    st.subheader("Subject-wise performance")
    if not subjects:
        st.info("Add subjects and complete quizzes to see performance.")
    else:
        rows = []
        for sid, name, sem in subjects:
            p = get_performance(sid)
            rows.append({"Subject": name, "Semester": sem, "Attempts": p["attempts"], "Correct": p["correct"], "Questions": p["total"], "Accuracy (%)": round(p["accuracy"], 1)})
        st.dataframe(rows, use_container_width=True, hide_index=True)
        for row in rows:
            st.write(f"**{row['Subject']}** — {row['Accuracy (%)']}%")
            st.progress(min(1.0, row["Accuracy (%)"] / 100))
    attempts = query("""SELECT subjects.name, quiz_attempts.topic, quiz_attempts.score, quiz_attempts.total, quiz_attempts.attempted_at
                        FROM quiz_attempts JOIN subjects ON subjects.id=quiz_attempts.subject_id
                        ORDER BY quiz_attempts.id DESC LIMIT 30""", fetch=True)
    st.subheader("Recent quiz attempts")
    if attempts:
        st.dataframe([{"Subject": a[0], "Topic": a[1], "Score": f"{a[2]}/{a[3]}", "Date": a[4]} for a in attempts], use_container_width=True, hide_index=True)
    else:
        st.info("Your quiz history will appear here after your first quiz.")

# Planner
elif page == "🗓️ Study Planner":
    st.title("🗓️ Personalized Study Planner")
    subjects = get_subjects()
    if not subjects:
        st.warning("Add subjects first to build a plan.")
    else:
        default_exam = read_setting("exam_date", (date.today() + timedelta(days=30)).isoformat())
        try:
            default_exam_date = date.fromisoformat(default_exam)
        except ValueError:
            default_exam_date = date.today() + timedelta(days=30)
        try:
            exam_date = st.date_input("Exam date", value=max(default_exam_date, date.today()))
        except Exception:
            exam_date = st.date_input("Exam date", value=date.today() + timedelta(days=30))
        hours = st.slider("Study hours per day", 1, 12, int(read_setting("study_hours", "3")))
        if st.button("Save plan settings"):
            save_setting("exam_date", exam_date.isoformat())
            save_setting("study_hours", hours)
            st.success("Plan settings saved.")
        days_left = max(0, (exam_date - date.today()).days)
        st.metric("Days until exam", days_left)
        st.subheader("Suggested daily plan")
        weak = []
        for sid, name, sem in subjects:
            p = get_performance(sid)
            priority = "High" if p["attempts"] and p["accuracy"] < 60 else "Normal"
            weak.append((name, p["accuracy"], priority))
        weights = [2 if item[2] == "High" else 1 for item in weak]
        total_weight = sum(weights) or 1
        for item, weight in zip(weak, weights):
            mins = round(hours * 60 * weight / total_weight)
            st.write(f"**{item[0]}** — about {mins} minutes/day · {item[2]} priority")
        st.info("After taking quizzes, low-scoring subjects are assigned more study time. Adjust the plan to your real syllabus and exam timetable.")

# Flashcards
elif page == "🃏 Flashcards":
    st.title("🃏 Flashcards")
    subjects = get_subjects()
    if not subjects:
        st.warning("Add a subject first.")
    else:
        mapping = {f"{n} ({sem})": sid for sid, n, sem in subjects}
        selected = st.selectbox("Subject", list(mapping), key="flashcard_subject")
        sid = mapping[selected]
        with st.form("new_flashcard_form", clear_on_submit=True):
            question = st.text_input("Front / question")
            answer = st.text_area("Back / answer")
            saved = st.form_submit_button("Save flashcard")
        if saved:
            if question.strip() and answer.strip():
                query("INSERT INTO flashcards(subject_id,question,answer,created_at) VALUES(?,?,?,?)",
                      (sid, question.strip(), answer.strip(), datetime.now().isoformat(timespec="seconds")))
                st.success("Flashcard saved.")
                st.rerun()
            else:
                st.error("Enter both a question and an answer.")
        cards = query("SELECT id,question,answer FROM flashcards WHERE subject_id=? ORDER BY id", (sid,), fetch=True)
        st.divider()
        st.subheader(f"Saved cards ({len(cards)})")
        if not cards:
            st.info("Create your first flashcard above.")
        else:
            idx = st.selectbox("Choose card", list(range(len(cards))), format_func=lambda i: f"Card {i+1}: {cards[i][1][:55]}")
            st.markdown(f"### {cards[idx][1]}")
            if st.button("Show answer", key=f"show_card_{cards[idx][0]}"):
                st.session_state[f"show_card_{cards[idx][0]}"] = True
            if st.session_state.get(f"show_card_{cards[idx][0]}", False):
                st.success(cards[idx][2])
            if st.button("Delete this card", key=f"delete_card_{cards[idx][0]}"):
                query("DELETE FROM flashcards WHERE id=?", (cards[idx][0],))
                st.rerun()

# Advisor
elif page == "🤖 AI Study Advisor":
    st.title("🤖 Study Advisor")
    st.caption("This demo uses your saved scores and uploaded material; it does not call an external AI service.")
    subjects = get_subjects()
    if not subjects:
        st.info("Add subjects and take a quiz to receive personalized advice.")
    else:
        scored = []
        for sid, name, sem in subjects:
            p = get_performance(sid)
            scored.append((sid, name, sem, p))
        tried = [x for x in scored if x[3]["attempts"]]
        if not tried:
            st.info("Take at least one quiz to get score-based recommendations.")
        else:
            tried.sort(key=lambda x: x[3]["accuracy"])
            weakest = tried[0]
            st.subheader("Your current focus")
            st.warning(f"Prioritize **{weakest[1]}**: current accuracy is {weakest[3]['accuracy']:.1f}%.")
            for sid, name, sem, p in tried:
                with st.container(border=True):
                    st.write(f"**{name}** — {p['accuracy']:.1f}% accuracy")
                    if p["accuracy"] < 50:
                        st.write("Recommendation: revise fundamentals, create flashcards, and attempt a short quiz after each topic.")
                    elif p["accuracy"] < 75:
                        st.write("Recommendation: practice medium questions and review every incorrect answer.")
                    else:
                        st.write("Recommendation: maintain this subject with mixed practice and timed mock quizzes.")
                    text = get_subject_text(sid)
                    if text:
                        st.caption(f"Uploaded materials available: {len(text.split())} extracted words.")
            st.divider()
            st.subheader("Quick study routine")
            st.markdown("1. Review one weak topic for 25 minutes.\n2. Write a short summary from memory.\n3. Attempt 5–10 MCQs.\n4. Review mistakes and repeat the difficult questions tomorrow.")

# Textbook question generator
elif page == "📖 Textbook Question Generator":
    st.title("📖 Textbook Question Generator")
    st.write("Create local, rule-based practice prompts from readable textbook/notes text. These are revision prompts, not guaranteed exam questions.")
    subjects = get_subjects()
    if not subjects:
        st.warning("Add a subject first.")
    else:
        mapping = {f"{n} ({sem})": sid for sid, n, sem in subjects}
        selected = st.selectbox("Choose subject", list(mapping), key="textbook_subject")
        sid = mapping[selected]
        mats = [m for m in get_materials(sid) if "textbook" in (m[3] or "").lower()]
        if not mats:
            st.info("No materials labelled Textbook for this subject yet. Go to Upload Materials and upload a readable PDF, TXT, or DOCX with material type Textbook.")
        else:
            st.caption(f"Found {len(mats)} textbook file(s).")
            names = [m[1] for m in mats]
            chosen_names = st.multiselect("Choose textbook file(s)", names, default=names, key="textbook_files")
            selected_mats = [m for m in mats if m[1] in chosen_names]
            text = "\n".join(m[4] or "" for m in selected_mats)
            if not text.strip():
                st.warning("No readable text was extracted. Scanned/image-only PDFs need OCR.")
            else:
                sentences = split_sentences(text)
                # Rank sentences by useful content words and sentence length.
                stop = set("this that with from have were will your into than then them they their about which what when where how why also used use using based each other such more most some very can could should would these those there being been".split())
                scored = []
                seen = set()
                for sentence in sentences:
                    words = re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", sentence.lower())
                    useful = [w for w in words if w not in stop]
                    key = re.sub(r"[^a-z0-9]+", "", sentence.lower())
                    if len(useful) >= 5 and key not in seen:
                        seen.add(key)
                        scored.append((len(set(useful)) + min(len(sentence) / 80, 3), sentence, useful))
                scored.sort(key=lambda x: (-x[0], x[1].lower()))
                limit = st.slider("Number of practice prompts", 5, 50, 20, key="textbook_limit")
                if not scored:
                    st.warning("Not enough readable sentence text was found to create prompts.")
                else:
                    prompts = []
                    for _, sentence, words in scored[:limit]:
                        key_terms = list(dict.fromkeys(words))[:4]
                        prompts.append({
                            "question": f"Explain the concept(s): {', '.join(key_terms)}.",
                            "source": sentence,
                            "keywords": ", ".join(key_terms),
                        })
                    st.success(f"Created {len(prompts)} practice prompts from the selected textbook text.")
                    for i, item in enumerate(prompts, 1):
                        with st.expander(f"{i}. {item['question']}"):
                            st.write("**Reference sentence from your material:**")
                            st.write(item["source"])
                            st.caption(f"Keywords: {item['keywords']}")
                    export_text = "\n\n".join(
                        f"{i}. {item['question']}\nKeywords: {item['keywords']}\nReference: {item['source']}"
                        for i, item in enumerate(prompts, 1)
                    )
                    st.download_button("⬇️ Download practice prompts (.txt)", export_text,
                                       file_name=f"{get_subject_name(sid).replace(' ', '_')}_textbook_practice.txt",
                                       key="download_textbook_prompts")

# Previous-year question paper analyzer
elif page == "📝 PYQ Analyzer":
    st.title("📝 Previous Year Question Paper (PYQ) Analyzer")
    st.write("Compare question-like lines extracted from uploaded PYQs. Repeats are based on text matching, so differently worded versions may not be grouped.")
    subjects = get_subjects()
    if not subjects:
        st.warning("Add a subject first.")
    else:
        mapping = {f"{n} ({sem})": sid for sid, n, sem in subjects}
        selected = st.selectbox("Choose subject", list(mapping), key="pyq_subject")
        sid = mapping[selected]
        mats = [m for m in get_materials(sid) if "pyq" in (m[3] or "").lower() or "previous" in (m[3] or "").lower()]
        if not mats:
            st.info("No materials labelled PYQ / Previous-year paper for this subject. Go to Upload Materials, choose that material type, and upload at least two papers.")
        else:
            st.caption(f"Found {len(mats)} PYQ file(s).")
            def find_questions(raw_text):
                found = []
                for line in re.split(r"[\n\r]+", raw_text or ""):
                    line = normalize_text(line).strip(" •*-")
                    if len(line) < 12 or len(line) > 500:
                        continue
                    if re.search(r"\b(?:define|explain|describe|discuss|compare|differentiate|derive|illustrate|what is|why|how|write|list|state|mention|calculate|identify|enumerate|short note)\b", line, re.I) or line.endswith("?") or re.match(r"^(?:Q(?:uestion)?\s*)?\d{1,3}\s*[.)]", line, re.I):
                        found.append(line)
                # Remove exact duplicates inside one paper.
                return list(dict.fromkeys(found))
            papers = {m[1]: find_questions(m[4] or "") for m in mats}
            all_questions = [q for questions in papers.values() for q in questions]
            if not any(papers.values()):
                st.warning("No question-like lines found. This works best with text-based PDFs where each question is on its own line. Scanned PDFs need OCR.")
            else:
                st.subheader("Paper summary")
                cols = st.columns(3)
                cols[0].metric("Papers analyzed", len(papers))
                cols[1].metric("Question-like lines", len(all_questions))
                cols[2].metric("Papers with extracted questions", sum(bool(v) for v in papers.values()))
                st.subheader("Questions found in each paper")
                for paper_name, questions in papers.items():
                    with st.expander(f"{paper_name} — {len(questions)} question(s)"):
                        if questions:
                            st.write("\n".join(f"{i}. {q}" for i, q in enumerate(questions, 1)))
                        else:
                            st.caption("No question-like lines detected in this paper.")
                # Group identical normalized question strings across different papers.
                def question_key(q):
                    q = re.sub(r"^(?:q(?:uestion)?\s*)?\d{1,3}\s*[.)]\s*", "", q.lower())
                    q = re.sub(r"[^a-z0-9 ]", " ", q)
                    q = re.sub(r"\s+", " ", q).strip()
                    return q
                grouped = {}
                for paper_name, questions in papers.items():
                    seen_in_paper = set()
                    for question in questions:
                        key = question_key(question)
                        if len(key.split()) < 3 or key in seen_in_paper:
                            continue
                        seen_in_paper.add(key)
                        grouped.setdefault(key, {"question": question, "papers": []})["papers"].append(paper_name)
                repeated = [v for v in grouped.values() if len(v["papers"]) >= 2]
                repeated.sort(key=lambda item: (-len(item["papers"]), item["question"].lower()))
                st.subheader("Repeated questions")
                if repeated:
                    st.caption("These are exact/near-exact text matches after removing punctuation and question numbering.")
                    for i, item in enumerate(repeated, 1):
                        with st.container(border=True):
                            st.markdown(f"**{i}. {item['question']}**")
                            st.write(f"Appears in {len(item['papers'])} papers: {', '.join(item['papers'])}")
                    repeated_export = "\n".join(
                        f"{i}. {item['question']}\nAppears in: {', '.join(item['papers'])}"
                        for i, item in enumerate(repeated, 1)
                    )
                    st.download_button("⬇️ Download repeated questions (.txt)", repeated_export,
                                       file_name=f"{get_subject_name(sid).replace(' ', '_')}_repeated_pyqs.txt",
                                       key="download_repeated_pyqs")
                else:
                    st.info("No repeated question text was detected across these papers. Similar questions with different wording may not be recognized.")
                st.subheader("Frequently occurring keywords")
                words = topic_keywords("\n".join(all_questions))[:15]
                if words:
                    st.write(", ".join(f"**{word}**" for word in words))
                st.download_button(
                    "⬇️ Download extracted questions (.txt)",
                    "\n\n".join(f"{paper}\n" + "\n".join(f"{i}. {q}" for i, q in enumerate(questions, 1))
                               for paper, questions in papers.items()),
                    file_name=f"{get_subject_name(sid).replace(' ', '_')}_extracted_pyqs.txt",
                    key="download_all_pyqs",
                )

# Settings
elif page == "⚙️ Settings":
    st.title("⚙️ Settings")
    st.write("Configure your study preferences.")
    try:
        existing_date = date.fromisoformat(read_setting("exam_date", (date.today() + timedelta(days=30)).isoformat()))
    except ValueError:
        existing_date = date.today() + timedelta(days=30)
    exam_date = st.date_input("Target exam date", value=max(existing_date, date.today()), key="settings_exam_date")
    study_hours = st.slider("Preferred study hours per day", 1, 12, int(read_setting("study_hours", "3")), key="settings_hours")
    if st.button("Save settings"):
        save_setting("exam_date", exam_date.isoformat())
        save_setting("study_hours", study_hours)
        st.success("Settings saved.")
    st.divider()
    st.subheader("Storage status")
    st.write(f"Database: `{DB_PATH}`")
    st.write(f"Uploads folder: `{UPLOAD_DIR}`")
    st.write(f"Subjects: {len(get_subjects())}")
    material_count = query("SELECT COUNT(*) FROM materials", fetch=True)[0][0]
    st.write(f"Saved materials: {material_count}")
    st.caption("Your subjects, quiz scores, flashcards, and upload metadata are stored locally in SQLite.")
