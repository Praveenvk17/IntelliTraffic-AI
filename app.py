import streamlit as st
from ultralytics import YOLO
import cv2, sqlite3, tempfile, random, json
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.linear_model import LinearRegression
from fpdf import FPDF
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt

# ================= CONFIG =================
st.set_page_config(page_title="IntelliTraffic AI", page_icon="🚦", layout="wide")

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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS app_users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        role TEXT,
        status TEXT,
        created_at TEXT
    )
    """)

    con.commit()
    con.close()

def init_default_users():
    con = sqlite3.connect(DB)
    cur = con.cursor()

    for username, data in USERS.items():
        cur.execute("""
        INSERT OR IGNORE INTO app_users(username, role, status, created_at)
        VALUES(?,?,?,?)
        """, (
            username,
            data["role"],
            "Active",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

    con.commit()
    con.close()

init_db()
init_default_users()

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

def add_user(username, role):
    con = sqlite3.connect(DB)
    cur = con.cursor()
    try:
        cur.execute("""
        INSERT INTO app_users(username, role, status, created_at)
        VALUES(?,?,?,?)
        """, (
            username,
            role,
            "Active",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        con.commit()
        st.success("User added successfully.")
    except sqlite3.IntegrityError:
        st.error("Username already exists.")
    con.close()

def update_user_status(username, status):
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("UPDATE app_users SET status=? WHERE username=?", (status, username))
    con.commit()
    con.close()
    st.success("User status updated.")

# ================= AUTH =================
def login_page():
    st.markdown('<div class="main-title">🚦 IntelliTraffic AI</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-title">Premium Smart Traffic Monitoring & Signal Optimization Platform</div>',
        unsafe_allow_html=True
    )
    st.write("")

    c1, c2, c3 = st.columns([1, 1.3, 1])

    with c2:
        st.markdown("""
        <div style="
            background: rgba(10,10,10,0.88);
            border: 2px solid #facc15;
            border-radius: 24px;
            padding: 28px;
            box-shadow: 0 0 28px rgba(250,204,21,0.35);
        ">
            <div style="
                text-align:center;
                background: linear-gradient(90deg,#991b1b,#facc15);
                padding: 12px;
                border-radius: 16px;
                font-weight: 900;
                color: black;
                margin-bottom: 18px;
            ">
                🏆 AI Powered Smart Traffic Management System
            </div>
        </div>
        """, unsafe_allow_html=True)

        user = st.text_input("👤 Username")
        password = st.text_input("🔒 Password", type="password")

        if st.button("🚀 Login"):
            if user in USERS and USERS[user]["password"] == password:
                users_df = read_table("app_users")
                user_row = users_df[users_df["username"] == user]

                if not user_row.empty and user_row.iloc[0]["status"] != "Active":
                    st.error("This user is disabled by admin.")
                else:
                    st.session_state.logged = True
                    st.session_state.user = user
                    st.session_state.role = USERS[user]["role"]
                    st.rerun()
            else:
                st.error("Invalid username or password")

        st.info("Demo Login: admin/admin123 | officer/officer123 | viewer/viewer123")
       

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
    if frame is None:
        return frame, {v: 0 for v in VEHICLES}, 0, False

    results = model.predict(frame, conf=conf, verbose=False)
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

def get_project_stats():
    reports = read_table("traffic_reports")
    feedback = read_table("feedback")

    total_reports = len(reports)
    total_vehicles = int(reports["total"].sum()) if not reports.empty else 0
    avg_congestion = round(reports["congestion"].mean(), 2) if not reports.empty else 0
    total_feedback = len(feedback)
    avg_rating = round(feedback["rating"].mean(), 1) if not feedback.empty else 0

    return total_reports, total_vehicles, avg_congestion, total_feedback, avg_rating

def get_vehicle_distribution():
    df = read_table("traffic_reports")

    if df.empty:
        return pd.DataFrame({
            "Vehicle Type": ["Cars", "Buses", "Trucks", "Motorcycles", "Bicycles"],
            "Count": [0, 0, 0, 0, 0]
        })

    return pd.DataFrame({
        "Vehicle Type": ["Cars", "Buses", "Trucks", "Motorcycles", "Bicycles"],
        "Count": [
            int(df["cars"].sum()),
            int(df["buses"].sum()),
            int(df["trucks"].sum()),
            int(df["motorcycles"].sum()),
            int(df["bicycles"].sum())
        ]
    })

def clean_pdf_text(value, max_len=90):
    text = str(value)
    for item in ["🚦", "•", "✅", "🚑", "🤖", "📋", "📊", "⭐", "🌍"]:
        text = text.replace(item, "")
    text = text.replace("\n", " ")
    return text[:max_len] + "..." if len(text) > max_len else text

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
        pdf.cell(60, 8, clean_pdf_text(col, 25), border=1)
        pdf.cell(120, 8, clean_pdf_text(row[col], 75), border=1)
        pdf.ln()

    pdf.output(path)
    return path

def export_excel():
    reports = read_table("traffic_reports")
    feedback = read_table("feedback")
    users = read_table("app_users")

    path = "intellitraffic_full_report.xlsx"

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        reports.to_excel(writer, index=False, sheet_name="Traffic Reports")
        feedback.to_excel(writer, index=False, sheet_name="Feedback")
        users.to_excel(writer, index=False, sheet_name="Users")

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
        "🌍 Map View",
        "📋 Reports",
        "⭐ Feedback",
        "🔥 Traffic Heatmap",
        "⚠️ Accident Detection",
        "🔢 ANPR Records",
        "👥 User Management"
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
        "🌍 Map View",
        "⭐ Feedback"
    ]
}

MENU_MAP = {
    "📊 Dashboard": "Dashboard",
    "📷 Camera Analysis": "Camera Analysis",
    "🎥 Multi-Camera": "Multi-Camera",
    "📡 Live RTSP/CCTV": "Live RTSP/CCTV",
    "🌍 Map View": "Map View",
    "📋 Reports": "Reports",
    "⭐ Feedback": "Feedback",
    "🔥 Traffic Heatmap": "Traffic Heatmap",
    "⚠️ Accident Detection": "Accident Detection",
    "🔢 ANPR Records": "ANPR Records",
    "👥 User Management": "User Management"
}

selected_menu = st.sidebar.radio("Navigation", ROLE_MENUS[role])
menu = MENU_MAP[selected_menu]

conf = st.sidebar.slider("YOLO Confidence", 0.10, 0.90, 0.20, 0.05)
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
    total_reports, total_vehicles, avg_congestion, total_feedback, avg_rating = get_project_stats()

    st.subheader("📊 Project Statistics")
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("📋 Total Reports", total_reports)
    a2.metric("🚗 Total Vehicles", total_vehicles)
    a3.metric("⚠️ Avg Congestion", f"{avg_congestion}/100")
    a4.metric("⭐ Feedback Count", total_feedback)

    st.metric("⭐ Average Rating", f"{avg_rating}/5")

    if df.empty:
        st.info("No data yet. Start with Camera Analysis.")
    else:
        latest = df.iloc[0]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Latest Vehicles", int(latest["total"]))
        c2.metric("Density", latest["density"])
        c3.metric("Green Time", f'{latest["green_time"]} sec')
        c4.metric("Prediction", int(latest["prediction"]))

        st.subheader("📈 Vehicle Trend")
        st.line_chart(df[["total", "prediction"]].head(20).sort_index())

        st.subheader("🥧 Vehicle Distribution")
        vehicle_dist = get_vehicle_distribution()
        st.dataframe(vehicle_dist, use_container_width=True)
        st.bar_chart(vehicle_dist.set_index("Vehicle Type"))
        st.subheader("🥧 Vehicle Distribution Pie Chart")

        pie_data = vehicle_dist[vehicle_dist["Count"] > 0]

        if pie_data.empty:
            st.info("Pie chart ku data illa. First traffic image/video analysis pannunga.")
        else:
            fig = (
                pie_data.set_index("Vehicle Type")["Count"]
                .plot.pie(
                    autopct="%1.1f%%",
                    figsize=(4,4),
                    startangle=90,
                    wedgeprops={"edgecolor":"white","linewidth":2},
                    ylabel=""
                )
                .get_figure()
            )

            st.pyplot(fig)
            plt.close(fig)

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

            if frame is None:
                st.error("Image read panna mudiyala. Proper JPG/PNG upload pannunga.")
            else:
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

            if frame is not None:
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
    st.subheader("🌍 Map View")
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

        excel_path = export_excel()
        with open(excel_path, "rb") as f:
            st.download_button(
                "Download Excel Report",
                f,
                "intellitraffic_full_report.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

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

    fb = read_table("feedback")

    if not fb.empty:
        avg_rating = round(fb["rating"].mean(), 1)

        c1, c2 = st.columns(2)
        c1.metric("⭐ Average Rating", f"{avg_rating}/5")
        c2.metric("📝 Total Reviews", len(fb))

        st.subheader("🏆 Top Reviews")
        top_reviews = fb.sort_values(by="rating", ascending=False).head(5)
        st.dataframe(top_reviews, use_container_width=True)

        st.subheader("Saved Reviews")
        st.dataframe(fb, use_container_width=True)
    else:
        st.info("No feedback yet.")

elif menu == "User Management":
    if st.session_state.role != "Admin":
        st.error("Access denied. Admin only.")
        st.stop()

    st.subheader("👥 Admin User Management")

    users_df = read_table("app_users")
    st.dataframe(users_df, use_container_width=True)

    st.subheader("Add New User")
    new_username = st.text_input("New Username")
    new_role = st.selectbox("Role", ["Admin", "Officer", "Viewer"])

    if st.button("Add User"):
        if new_username:
            add_user(new_username, new_role)
        else:
            st.error("Username required.")

    st.subheader("Update User Status")
    if not users_df.empty:
        selected_user = st.selectbox("Select User", users_df["username"].tolist())
        new_status = st.selectbox("Status", ["Active", "Disabled"])

        if st.button("Update Status"):
            update_user_status(selected_user, new_status)

    st.info("Note: Demo login passwords are controlled from USERS dictionary in code.")

elif menu == "Traffic Heatmap":
    st.subheader("🔥 Traffic Congestion Heatmap")

    df = read_table("traffic_reports")

    if df.empty:
        st.info("No traffic data available.")
    else:
        heat_df = df[["camera", "location", "total", "congestion"]].head(30)
        st.dataframe(heat_df, use_container_width=True)

        pivot = heat_df.pivot_table(
            values="congestion",
            index="location",
            columns="camera",
            aggfunc="mean",
            fill_value=0
        )

        st.subheader("Camera-wise Congestion Heatmap")
        st.dataframe(
            pivot.style.background_gradient(cmap="Reds"),
            use_container_width=True
        )

        st.subheader("Congestion Ranking")
        rank_df = heat_df.sort_values(by="congestion", ascending=False)
        st.bar_chart(rank_df.set_index("camera")["congestion"])


elif menu == "Accident Detection":
    st.subheader("⚠️ Accident Risk Detection")

    df = read_table("traffic_reports")

    if df.empty:
        st.info("No traffic data available.")
    else:
        latest = df.iloc[0]

        risk_score = 0

        if int(latest["total"]) > 35:
            risk_score += 40

        if int(latest["congestion"]) > 70:
            risk_score += 35

        if latest["emergency"] == "Yes":
            risk_score += 25

        risk_score = min(risk_score, 100)

        c1, c2, c3 = st.columns(3)
        c1.metric("🚗 Vehicle Count", int(latest["total"]))
        c2.metric("⚠️ Congestion", f'{latest["congestion"]}/100')
        c3.metric("🛡️ Accident Risk", f"{risk_score}%")

        if risk_score >= 75:
            st.error("🚨 High Accident Risk Detected")
            st.write("Action: Reduce vehicle flow, increase signal control, alert operator.")
        elif risk_score >= 45:
            st.warning("⚠️ Medium Accident Risk")
            st.write("Action: Monitor camera feed and optimize signal timing.")
        else:
            st.success("✅ Low Accident Risk")
            st.write("Action: Normal monitoring is enough.")

        st.subheader("Risk Reasoning")
        st.write(f"Latest Camera: {latest['camera']}")
        st.write(f"Location: {latest['location']}")
        st.write(f"Emergency Status: {latest['emergency']}")
        st.write(f"AI Recommendation: {latest['recommendation']}")


elif menu == "ANPR Records":
    st.subheader("🔢 ANPR Number Plate Records")

    df = read_table("traffic_reports")

    if df.empty:
        st.info("No ANPR records available.")
    else:
        anpr_df = df[["created_at", "camera", "location", "plate", "total", "density"]]
        st.dataframe(anpr_df, use_container_width=True)

        st.download_button(
            "Download ANPR CSV",
            anpr_df.to_csv(index=False),
            "anpr_records.csv",
            "text/csv"
        )

        st.info("Note: This is demo ANPR. Real ANPR needs EasyOCR/custom number plate model.")
