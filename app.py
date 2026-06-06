import streamlit as st
from ultralytics import YOLO
import cv2, sqlite3, tempfile, os, random, json, time
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.linear_model import LinearRegression
from fpdf import FPDF
import folium
from streamlit_folium import st_folium

# ================= CONFIG =================
st.set_page_config(
    page_title="IntelliTraffic AI",
    page_icon="🚦",
    layout="wide"
)

DB = "intellitraffic_ai.db"
VEHICLES = ["car", "bus", "truck", "motorcycle", "bicycle"]

USERS = {
    "admin": {"password": "admin123", "role": "Admin"},
    "officer": {"password": "officer123", "role": "Officer"},
    "viewer": {"password": "viewer123", "role": "Viewer"}
}

# ================= THEME =================
st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #050505 0%, #1a0505 45%, #3b0505 100%);
    color: #f8fafc;
}
.main-title {
    font-size: 44px;
    font-weight: 900;
    color: #facc15;
    text-align: center;
    text-shadow: 0px 0px 18px #dc2626;
}
.sub-title {
    text-align:center;
    color:#fef3c7;
    font-size:18px;
}
.card {
    background: linear-gradient(135deg,#111111,#2a0909);
    border: 1px solid #facc15;
    border-radius: 18px;
    padding: 18px;
    box-shadow: 0 0 18px rgba(250,204,21,0.18);
}
.stButton>button {
    background: linear-gradient(90deg,#991b1b,#facc15);
    color: black;
    border-radius: 10px;
    border: none;
    font-weight: 800;
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#050505,#3b0505);
}
</style>
""", unsafe_allow_html=True)

# ================= MODEL =================
@st.cache_resource
def load_model():
    return YOLO("yolov8n.pt")

model = load_model()

# ================= DATABASE =================
def init_db():
    con = sqlite3.connect(DB)
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS traffic_reports(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT,
        camera TEXT,
        location TEXT,
        total INTEGER,
        cars INTEGER,
        buses INTEGER,
        trucks INTEGER,
        motorcycles INTEGER,
        bicycles INTEGER,
        density TEXT,
        congestion INTEGER,
        green_time INTEGER,
        yellow_time INTEGER,
        red_time INTEGER,
        prediction INTEGER,
        emergency TEXT,
        plate TEXT,
        recommendation TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS feedback(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT,
        name TEXT,
        rating INTEGER,
        review TEXT
    )
    """)

    con.commit()
    con.close()

init_db()

def save_report(row):
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("""
    INSERT INTO traffic_reports(
        created_at,camera,location,total,cars,buses,trucks,motorcycles,bicycles,
        density,congestion,green_time,yellow_time,red_time,prediction,emergency,plate,recommendation
    )
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, row)
    con.commit()
    con.close()

def save_feedback(name, rating, review):
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO feedback(created_at,name,rating,review) VALUES(?,?,?,?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), name, rating, review)
    )
    con.commit()
    con.close()

def read_table(table):
    con = sqlite3.connect(DB)
    df = pd.read_sql_query(f"SELECT * FROM {table} ORDER BY id DESC", con)
    con.close()
    return df

# ================= AUTH =================
def login_page():
    st.markdown('<div class="main-title">🚦 IntelliTraffic AI</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Premium Smart Traffic Monitoring & Signal Optimization Platform</div>', unsafe_allow_html=True)
    st.write("")

    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        user = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            if user in USERS and USERS[user]["password"] == password:
                st.session_state.logged = True
                st.session_state.user = user
                st.session_state.role = USERS[user]["role"]
                st.rerun()
            else:
                st.error("Invalid username or password")

        st.info("Demo Login: admin/admin123 | officer/officer123 | viewer/viewer123")
        st.markdown('</div>', unsafe_allow_html=True)

if "logged" not in st.session_state:
    st.session_state.logged = False

if not st.session_state.logged:
    login_page()
    st.stop()

# ================= LOGIC =================
def traffic_density(total):
    if total <= 10:
        return "Low"
    if total <= 25:
        return "Medium"
    if total <= 40:
        return "Heavy"
    return "Critical"

def congestion_score(total):
    return min(100, total * 3)

def signal_times(total, emergency=False, peak=False, rain=False):
    if emergency:
        green = 90
    elif total <= 5:
        green = 15
    elif total <= 15:
        green = 30
    elif total <= 30:
        green = 45
    else:
        green = 60

    if peak:
        green += 15
    if rain:
        green += 10

    green = min(green, 120)
    yellow = 6 if rain else 4
    red = max(10, 90 - green)
    return green, yellow, red

def ml_prediction(total):
    x = np.array([[1], [2], [3], [4], [5]])
    y = np.array([max(1,total-8), max(1,total-4), total, total+4, total+8])
    m = LinearRegression()
    m.fit(x, y)
    return int(m.predict([[6]])[0])

def recommendation(total, emergency):
    if emergency:
        return "Emergency vehicle priority detected. Give immediate green signal."
    if total > 40:
        return "Critical congestion. Extend green time and notify traffic operator."
    if total > 25:
        return "Heavy traffic. Increase green signal duration."
    if total > 10:
        return "Moderate traffic. Optimized timing recommended."
    return "Traffic is smooth. Normal signal timing is enough."

def demo_plate():
    return f"TN-{random.randint(10,99)}-AI-{random.randint(1000,9999)}"

def analyze_frame(frame, conf):
    results = model(frame, conf=conf)
    stats = {v: 0 for v in VEHICLES}
    emergency = False

    for r in results:
        for box in r.boxes:
            cls = int(box.cls[0])
            name = model.names[cls]

            if name in stats:
                stats[name] += 1

            if name in ["ambulance", "fire truck", "police car"]:
                emergency = True

    total = sum(stats.values())
    annotated = results[0].plot()
    return annotated, stats, total, emergency

def build_row(camera, location, stats, total, emergency, peak, rain):
    green, yellow, red = signal_times(total, emergency, peak, rain)
    pred = ml_prediction(total)
    return (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        camera,
        location,
        total,
        stats["car"],
        stats["bus"],
        stats["truck"],
        stats["motorcycle"],
        stats["bicycle"],
        traffic_density(total),
        congestion_score(total),
        green,
        yellow,
        red,
        pred,
        "Yes" if emergency else "No",
        demo_plate(),
        recommendation(total, emergency)
    )

def clean_pdf_text(value, max_len=90):
    text = str(value)
    text = text.replace("🚦", "")
    text = text.replace("•", "-")
    text = text.replace("✅", "")
    text = text.replace("🚑", "")
    text = text.replace("🤖", "")
    text = text.replace("📋", "")
    text = text.replace("📊", "")
    text = text.replace("\n", " ")

    if len(text) > max_len:
        text = text[:max_len] + "..."

    return text


def create_pdf(df):
    path = "latest_traffic_report.pdf"

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "IntelliTraffic AI Report", ln=True, align="C")
    pdf.ln(6)

    pdf.set_font("Arial", "B", 11)
    pdf.cell(60, 8, "Field", border=1)
    pdf.cell(120, 8, "Value", border=1)
    pdf.ln()

    pdf.set_font("Arial", "", 9)

    row = df.iloc[0]

    for col in df.columns:
        field = clean_pdf_text(col, 25)
        value = clean_pdf_text(row[col], 75)

        pdf.cell(60, 8, field, border=1)
        pdf.cell(120, 8, value, border=1)
        pdf.ln()

    pdf.output(path)
    return path

# ================= SIDEBAR =================
st.sidebar.title("🚦 IntelliTraffic AI")
st.sidebar.success(f"{st.session_state.role} Mode")

role = st.session_state.role

ROLE_MENUS = {
    "Admin": [
        "📊 Dashboard",
        "📷 Camera Analysis",
        "🎥 Multi-Camera",
        "📡 Live RTSP/CCTV",
        "🗺️ Map View",
        "📋 Reports",
        "⭐ Feedback"
    ],
    "Officer": [
        "📊 Dashboard",
        "📷 Camera Analysis",
        "🎥 Multi-Camera",
        "📋 Reports",
        "⭐ Feedback"
    ],
    "Viewer": [
        "📊 Dashboard",
        "🗺️ Map View",
        "⭐ Feedback"
    ]
}

menu = st.sidebar.radio("Navigation", ROLE_MENUS[role])

menu = menu.split(" ", 1)[1]

conf = st.sidebar.slider("YOLO Confidence", 0.10, 0.90, 0.35, 0.05)
frame_skip = st.sidebar.slider("Video Frame Skip", 1, 15, 5)
peak_mode = st.sidebar.checkbox("Peak Hour Mode")
rain_mode = st.sidebar.checkbox("Rain Mode")

if st.sidebar.button("Logout"):
    st.session_state.logged = False
    st.rerun()

# ================= HEADER =================
st.markdown('<div class="main-title">🚦 IntelliTraffic AI</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Smart Traffic Monitoring • Signal Optimization • AI Reports</div>', unsafe_allow_html=True)
st.write("")

# ================= PAGES =================
if menu == "Dashboard":
    df = read_table("traffic_reports")

    if df.empty:
        st.info("No data yet. Start with Camera Analysis.")
    else:
        latest = df.iloc[0]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Vehicles", int(latest["total"]))
        c2.metric("Density", latest["density"])
        c3.metric("Green Time", f'{latest["green_time"]} sec')
        c4.metric("Prediction", int(latest["prediction"]))

        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Congestion", f'{latest["congestion"]}/100')
        c6.metric("Emergency", latest["emergency"])
        c7.metric("Plate Demo", latest["plate"])
        c8.metric("Reports", len(df))

        st.subheader("📈 Vehicle Trend")
        st.line_chart(df[["total", "prediction"]].head(20).sort_index())

        st.subheader("Recent Reports")
        st.dataframe(df.head(10), use_container_width=True)

elif menu == "Camera Analysis":
    camera = st.text_input("Camera Name", "CAM-01")
    location = st.text_input("Location", "Main Junction")
    uploaded = st.file_uploader("Upload Traffic Image / Video", type=["jpg", "jpeg", "png", "mp4"])

    if uploaded:
        ext = uploaded.name.split(".")[-1].lower()

        if ext in ["jpg", "jpeg", "png"]:
            data = np.asarray(bytearray(uploaded.read()), dtype=np.uint8)
            frame = cv2.imdecode(data, cv2.IMREAD_COLOR)

            annotated, stats, total, emergency = analyze_frame(frame, conf)
            row = build_row(camera, location, stats, total, emergency, peak_mode, rain_mode)
            save_report(row)

            st.image(annotated, channels="BGR")
            st.success("Analysis saved to database.")

            report_df = pd.DataFrame([row], columns=[
                "created_at","camera","location","total","cars","buses","trucks","motorcycles","bicycles",
                "density","congestion","green_time","yellow_time","red_time","prediction","emergency","plate","recommendation"
            ])
            st.dataframe(report_df, use_container_width=True)

        else:
            temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            temp.write(uploaded.read())
            temp.close()

            cap = cv2.VideoCapture(temp.name)
            best_total = 0
            best_stats = {v: 0 for v in VEHICLES}
            emergency_final = False
            frame_no = 0
            box = st.empty()
            progress = st.progress(0)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                frame_no += 1

                if frame_no % frame_skip == 0:
                    annotated, stats, total, emergency = analyze_frame(frame, conf)
                    box.image(annotated, channels="BGR")
                    if total > best_total:
                        best_total = total
                        best_stats = stats
                    if emergency:
                        emergency_final = True

                if total_frames:
                    progress.progress(min(frame_no / total_frames, 1.0))

            cap.release()

            row = build_row(camera, location, best_stats, best_total, emergency_final, peak_mode, rain_mode)
            save_report(row)
            st.success("Video analysis saved to database.")

elif menu == "Multi-Camera":
    cam_count = st.slider("Number of Cameras", 1, 4, 2)
    results = []

    for i in range(cam_count):
        st.subheader(f"Camera {i+1}")
        name = st.text_input(f"Camera Name {i+1}", f"CAM-{i+1}")
        loc = st.text_input(f"Location {i+1}", f"Junction {i+1}")
        file = st.file_uploader(f"Upload Image for Camera {i+1}", type=["jpg", "jpeg", "png"], key=i)

        if file:
            data = np.asarray(bytearray(file.read()), dtype=np.uint8)
            frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
            annotated, stats, total, emergency = analyze_frame(frame, conf)
            row = build_row(name, loc, stats, total, emergency, peak_mode, rain_mode)
            save_report(row)

            st.image(annotated, channels="BGR")
            results.append({
                "Camera": name,
                "Location": loc,
                "Vehicles": total,
                "Density": traffic_density(total),
                "Green Time": row[11],
                "Emergency": row[15]
            })

    if results:
        st.subheader("Multi-Camera Summary")
        st.dataframe(pd.DataFrame(results), use_container_width=True)

elif menu == "Live RTSP/CCTV":
    st.warning("Real CCTV RTSP URL irundha mattum work aagum.")
    rtsp = st.text_input("RTSP URL")
    camera = st.text_input("Camera Name", "LIVE-CAM")
    location = st.text_input("Location", "Live Junction")
    max_frames = st.slider("Frames to Process", 30, 300, 120)

    if st.button("Start RTSP Analysis"):
        if not rtsp:
            st.error("RTSP URL enter pannunga.")
        else:
            cap = cv2.VideoCapture(rtsp)
            best_total = 0
            best_stats = {v: 0 for v in VEHICLES}
            emergency_final = False
            frame_no = 0
            box = st.empty()

            while cap.isOpened() and frame_no < max_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                frame_no += 1

                if frame_no % frame_skip == 0:
                    annotated, stats, total, emergency = analyze_frame(frame, conf)
                    box.image(annotated, channels="BGR")
                    if total > best_total:
                        best_total = total
                        best_stats = stats
                    if emergency:
                        emergency_final = True

            cap.release()
            row = build_row(camera, location, best_stats, best_total, emergency_final, peak_mode, rain_mode)
            save_report(row)
            st.success("RTSP analysis saved.")

elif menu == "Map View":
    lat = st.number_input("Latitude", value=11.7401)
    lon = st.number_input("Longitude", value=78.9636)

    m = folium.Map(location=[lat, lon], zoom_start=14)
    folium.Marker([lat, lon], tooltip="AI Traffic Camera", popup="IntelliTraffic AI Camera").add_to(m)
    st_folium(m, width=1000, height=520)

elif menu == "Reports":
    df = read_table("traffic_reports")
    st.subheader("📋 Traffic Reports Database")
    st.dataframe(df, use_container_width=True)

    if not df.empty:
        st.download_button("Download CSV", df.to_csv(index=False), "traffic_reports.csv", "text/csv")
        st.download_button(
            "Download JSON",
            json.dumps(df.to_dict(orient="records"), indent=4),
            "traffic_reports.json",
            "application/json"
        )

        pdf_path = create_pdf(df.head(1))
        with open(pdf_path, "rb") as f:
            st.download_button("Download Latest PDF", f, "traffic_report.pdf", "application/pdf")

elif menu == "Feedback":
    st.subheader("⭐ Feedback & Review")

    name = st.text_input("Your Name")
    rating = st.slider("Rating", 1, 5, 5)
    review = st.text_area("Write your feedback / review")

    if st.button("Submit Feedback"):
        if name and review:
            save_feedback(name, rating, review)
            st.success("Feedback saved successfully.")
        else:
            st.error("Name and review required.")

    st.subheader("Saved Reviews")
    fb = read_table("feedback")
    st.dataframe(fb, use_container_width=True)
