from flask import Flask, request, render_template, redirect, url_for, session, flash
from functools import wraps
from collections import defaultdict
import pandas as pd
import re
import os
import secrets
import json
import sys

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# Handle bundled app vs normal script
if getattr(sys, 'frozen', False):
    # Running from PyInstaller bundle
    BASE_DIR = sys._MEIPASS             # templates/static inside EXE
    REAL_DIR = os.path.dirname(sys.executable)  # location of .exe (external files)
else:
    BASE_DIR = os.path.dirname(__file__)
    REAL_DIR = BASE_DIR

TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
CONFIG_PATH = os.path.join(REAL_DIR, "config.json")
DATA_DIR = os.path.join(REAL_DIR, "data")

if not os.path.exists(CONFIG_PATH):
    raise FileNotFoundError("⚠️ ملف config.json مفقود! الرجاء نسخه إلى نفس مجلد البرنامج.")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = json.load(f)


### login funtion ###
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            # Store the original URL so we can redirect back after login
            session["next"] = request.url
            flash("🔐 الرجاء تسجيل الدخول أولاً")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


### logout funtion ###
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


### home page ###
@app.route("/")
@login_required
def home():
    username = session.get("username")
    role = session.get("role")
    room_ids = session.get("room_ids", [])
    
    room_files = [f for f in os.listdir(DATA_DIR) if re.match(r"room\d+\.xlsx", f)]
    num_rooms = len(room_files)

    return render_template("home.html",
                           username=username,
                           role=role,
                           room_ids=room_ids,
                           num_rooms=num_rooms)


### login page ###
@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = next((u for u in CONFIG["users"] if u["username"] == username and u["password"] == password), None)
        if user:
            session["logged_in"] = True
            session["username"] = user["username"]
            session["role"] = user["role"]
            session["room_ids"] = user.get("room_ids", [])

            next_page = session.pop("next", None)

            if next_page:
                return redirect(next_page)
            elif user["role"] == "admin":
                return redirect(url_for("dashboard"))
            elif user["role"] == "room":
                return redirect(url_for("room_view", room_id=user["room_ids"][0]))
            
        else:
            error = "❌ اسم المستخدم أو كلمة المرور غير صحيحة"

    return render_template("login.html", error=error)


### room page per id ###
@app.route("/room<int:room_id>", methods=["GET", "POST"])
@login_required
def room_view(room_id):

    # Restrict room users to only their assigned room
    # Only restrict if user is a room user
    if session.get("role") == "room":
        if room_id not in session.get("room_ids", []):
            flash("❌ غير مصرح لك بالدخول إلى هذه الغرفة")
            return redirect(url_for("login"))
        
    filename = f"room{room_id}.xlsx"
    filepath = os.path.join(DATA_DIR, filename)

    # Load Excel
    df = pd.read_excel(filepath)
    df = df.sort_values(by="رقم القيد", key=lambda col: col.astype(str).str.zfill(10))

    # Ensure 'صوّت؟' column exists and is of string type
    if 'صوّت؟' not in df.columns:
        df['صوّت؟'] = ""
    else:
        df['صوّت؟'] = df['صوّت؟'].astype(str)

    # Replace empty/NaN or invalid values with ❌
    df['صوّت؟'] = df['صوّت؟'].replace(["", "nan", "NaN", "None", "null"], "❌")
    df['صوّت؟'] = df['صوّت؟'].fillna("❌")

    # Save if newly added column
    if 'صوّت؟' not in pd.read_excel(filepath).columns:
        df.to_excel(filepath, index=False)
        

    message = ""
    message_class = ""
    if request.method == "POST":
        action = request.form.get("action")
        if action == "vote":
            reg_number = str(request.form.get("reg_number")).strip()
            full_name = str(request.form.get("full_name")).strip()
            current_status = request.form.get("current_status") or ""
            current_status = current_status.strip()

            match = df[
                (df["رقم القيد"].astype(str) == reg_number) &
                (df["الإسم الثلاثي"].astype(str).str.strip() == full_name)
            ]
            if not match.empty:
                # Toggle logic
                new_status = "" if current_status == "✅" else "✅"
                df.loc[match.index, "صوّت؟"] = new_status
                df.to_excel(filepath, index=False)
                action_text = "إلغاء التصويت" if current_status == "✅" else "تسجيل التصويت"
                voter_info = match.iloc[0].to_dict()
                voter_info.pop("صوّت؟", None)  # Remove voting status from display

                info_str = " | ".join(f"{k}: {v}" for k, v in voter_info.items())
                message = f"{action_text}:\n{info_str}"

                # Set a CSS class to color the message
                message_class = "success" if new_status == "✅" else "error"

            else:
                message = f"المطابقة غير موجودة: {full_name} / {reg_number}"

        elif action == "delete":
            reg_number = str(request.form.get("reg_number")).strip()
            full_name = str(request.form.get("full_name")).strip()
            row_index = request.form.get("row_index")

            if row_index is not None:
                row_index = int(row_index)
                if 0 <= row_index < len(df):
                    df = df.drop(index=row_index)
                    df.reset_index(drop=True, inplace=True)
                    df.to_excel(filepath, index=False)
                    message = f"✅ تم حذف السجل: {full_name} / {reg_number}"
                    message_class = "success"
                else:
                    message = "❌ فشل الحذف: رقم الصف غير صحيح"
                    message_class = "error"
            else:
                message = "❌ فشل الحذف: لم يتم إرسال رقم الصف"
                message_class = "error"

        elif action == "edit":
            row_index = request.form.get("row_index")
            new_name = request.form.get("new_name")

            if row_index is not None:
                row_index = int(row_index)
                if 0 <= row_index < len(df):
                    df.at[row_index, "الإسم الثلاثي"] = new_name
                    df.to_excel(filepath, index=False)
                    message = f"✅ تم تعديل الاسم إلى: {new_name}"
                    message_class = "success"
                else:
                    message = "❌ رقم الصف غير صالح"
                    message_class = "error"

    # Refresh after POST
    df = pd.read_excel(filepath)

    if 'صوّت؟' not in df.columns:
        df['صوّت؟'] = ""
    else:
        df['صوّت؟'] = df['صوّت؟'].astype(str)

    df['صوّت؟'] = df['صوّت؟'].replace(["", "nan", "NaN", "None", "null"], "❌")
    df['صوّت؟'] = df['صوّت؟'].fillna("❌")

    voted = df["صوّت؟"].notna().sum()
    total = len(df)
    percent = (voted / total) * 100 if total else 0

    # Detect duplicates excluding the vote column
    columns_to_check = df.columns[:-2]  # Exclude the last two columns
    duplicate_mask = df.duplicated(subset=columns_to_check, keep=False)
    duplicates = df[duplicate_mask]
    duplicate_count = len(duplicates)

    # Set of duplicate keys for template use (joined string of values excluding 'صوّت؟')
    duplicate_keys = set(
        "|".join([str(row[col]) for col in columns_to_check])
        for _, row in duplicates.iterrows()
    )

    # Duplicate rows for display (with row index)
    duplicate_rows = [
        {**row.to_dict(), "الرقم": idx}
        for idx, row in df.iterrows()
        if duplicate_mask.iloc[idx]
    ]

    all_full_names = df["الإسم الثلاثي"].astype(str).tolist()
    unique_families = sorted(df["العائلة"].dropna().astype(str).unique())
    unique_registrations = sorted(df["رقم القيد"].dropna().astype(str).unique())

    return render_template(
        "room.html",
        all_full_names=all_full_names,
        df=df.to_dict(orient="records"),
        duplicate_count=duplicate_count,
        duplicate_keys=duplicate_keys,
        duplicate_rows=duplicate_rows,
        room_id=room_id,
        message=message,
        message_class=message_class,
        voted=voted,
        total=total,
        percent=round(percent, 1),
        unique_families=unique_families,
        unique_registrations=unique_registrations,
        role=session.get("role")
    )


### dashboard page ###
@app.route("/dashboard")
@login_required
def dashboard():
    if session.get("role") != "admin":
        flash("❌ غير مصرح لك بالدخول إلى لوحة التحكم")
        return redirect(url_for("login"))

    summary = []
    total_voters = 0
    total_voted = 0

    # Detect room files dynamically
    room_files = sorted([
        f for f in os.listdir(DATA_DIR) if re.match(r"room\d+\.xlsx", f)
    ])

    family_stats = defaultdict(lambda: {"voted": 0, "not_voted": 0})

    for filename in room_files:
        match = re.match(r"room(\d+)\.xlsx", filename)
        if not match:
            continue

        room_id = int(match.group(1))
        filepath = os.path.join(DATA_DIR, filename)

        try:
            df = pd.read_excel(filepath)
        except:
            continue  # Skip broken files

        if 'صوّت؟' not in df.columns:
            df['صوّت؟'] = ""  # Create empty column
        else:
            df['صوّت؟'] = df['صوّت؟'].astype(str).fillna("")  # Ensure it's string type


        voted = df["صوّت؟"].astype(str).str.strip().eq("✅").sum()
        total = len(df)
        percent = (voted / total) * 100 if total else 0

        summary.append({
            "room_id": room_id,
            "total": total,
            "voted": voted,
            "percent": round(percent, 1)
        })

        total_voters += total
        total_voted += voted

        for _, row in df.iterrows():
            family = row["العائلة"]
            voted = str(row["صوّت؟"]).strip() == "✅"
            if voted:
                family_stats[family]["voted"] += 1
            else:
                family_stats[family]["not_voted"] += 1

            # ✅ Correct: update total inside the loop for each family
            family_stats[family]["total"] = (
                family_stats[family]["voted"] + family_stats[family]["not_voted"]
            )
            
    # Add percentage
    for stats in family_stats.values():
        total = stats["voted"] + stats["not_voted"]
        stats["percent"] = round((stats["voted"] / total) * 100, 1) if total else 0.0

    # Convert to list of dicts to send to template
    family_stats_list = [
        {"family": k, **v} for k, v in sorted(family_stats.items(), key=lambda item: item[0])
    ]

    overall_percent = (total_voted / total_voters) * 100 if total_voters else 0

    return render_template("dashboard.html",
                           summary=summary,
                           total_voters=total_voters,
                           total_voted=total_voted,
                           overall_percent=round(overall_percent, 1),
                           family_stats=family_stats_list)


### room details page ###
@app.route("/room-details/<int:room_id>")
@login_required
def room_details(room_id):

    # Restrict room users to only their assigned room
    if session.get("role") != "admin":
        flash("❌ غير مصرح لك بالدخول إلى هذه الغرفة")
        return redirect(url_for("login"))  # or redirect to their allowed room

    filename = f"room{room_id}.xlsx"
    filepath = os.path.join(DATA_DIR, filename)

    if not os.path.exists(filepath):
        return f"Room {room_id} not found", 404

    df = pd.read_excel(filepath)

    df["العائلة"] = df["العائلة"].astype(str).str.strip()
    df["صوّت؟"] = df["صوّت؟"].fillna("").astype(str).str.strip()

    family_stats = []

    for family, group in df.groupby("العائلة"):
        fam_total = len(group)
        fam_voted = group["صوّت؟"].eq("✅").sum()
        fam_not_voted = fam_total - fam_voted
        percent = round((fam_voted / fam_total) * 100, 1) if fam_total else 0

        family_stats.append({
            "name": family,
            "total": fam_total,
            "voted": fam_voted,
            "not_voted": fam_not_voted,
            "percent": percent
        })

    reg_number_stats = []

    for reg_number, group in df.groupby("رقم القيد"):
        reg_total = len(group)
        reg_voted = group["صوّت؟"].eq("✅").sum()
        reg_not_voted = reg_total - reg_voted
        percent = round((reg_voted / reg_total) * 100, 1) if reg_total else 0

        reg_number_stats.append({
            "reg_number": reg_number,
            "total": reg_total,
            "voted": reg_voted,
            "not_voted": reg_not_voted,
            "percent": percent
        })

    if 'صوّت؟' not in df.columns:
        df['صوّت؟'] = ""  # Create empty column
    else:
        df['صوّت؟'] = df['صوّت؟'].astype(str).fillna("")  # Ensure it's string type


    total = len(df)
    voted = df["صوّت؟"].eq("✅").sum()
    not_voted = total - voted

    return render_template(
        "room_details.html",
        room_id=room_id,
        total=int(total),
        voted=int(voted),
        not_voted=int(not_voted),
        family_stats=family_stats,
        reg_number_stats=reg_number_stats,
        role=session.get("role")
    )

### all combined rooms page ###
@app.route("/all-rooms", methods=["GET", "POST"])
@login_required
def all_rooms_view():

    if session.get("role") != "admin":
        flash("❌ غير مصرح لك بالدخول إلى هذه الصفحة", "error")
        return redirect(url_for("login"))
    
    import pandas as pd
    import re

    combined_data = []
    room_files = sorted([
        f for f in os.listdir(DATA_DIR) if re.match(r"room\d+\.xlsx", f)
    ])

    for filename in room_files:
        room_id = int(re.findall(r"\d+", filename)[0])
        df = pd.read_excel(os.path.join(DATA_DIR, filename))
        df["الغرفة"] = room_id  # add room column
        combined_data.append(df)

    if not combined_data:
        return "⚠️ لا توجد بيانات.", 404

    full_df = pd.concat(combined_data, ignore_index=True)
    full_df["صوّت؟"] = full_df["صوّت؟"].astype(str).str.strip()
    full_df["صوّت؟"] = full_df["صوّت؟"].replace(["", "nan", "NaN", "None", "null"], "❌")
    full_df["صوّت؟"] = full_df["صوّت؟"].fillna("❌")
    full_df["العائلة"] = full_df["العائلة"].astype(str).str.strip()
    full_df["الإسم الثلاثي"] = full_df["الإسم الثلاثي"].astype(str).str.strip()
    full_df["رقم القيد"] = full_df["رقم القيد"].astype(str).str.strip()

    # Detect duplicates excluding the vote column
    columns_to_check = full_df.columns[:-2]  # Exclude the last two columns
    duplicate_mask = full_df.duplicated(subset=columns_to_check, keep=False)
    duplicates = full_df[duplicate_mask]
    duplicate_count = len(duplicates)

    # Set of duplicate keys for template use (joined string of values excluding 'صوّت؟')
    duplicate_keys = set(
        "|".join([str(row[col]) for col in columns_to_check])
        for _, row in duplicates.iterrows()
    )

    # Duplicate rows for display (with row index)
    duplicate_rows = [
        {**row.to_dict(), "الرقم": idx}
        for idx, row in full_df.iterrows()
        if duplicate_mask.iloc[idx]
    ]

    # Unique filters
    unique_families = sorted(full_df["العائلة"].unique())
    unique_regs = sorted(full_df["رقم القيد"].unique())

    total_all = len(full_df)
    voted_all = full_df["صوّت؟"].eq("✅").sum()
    not_voted_all = total_all - voted_all
    percent_all = round((voted_all / total_all) * 100, 1) if total_all else 0

    if request.method == "POST":
        action = request.form.get("action")
        room_id_raw = request.form.get("room_id")
        if not room_id_raw:
            flash("❌ لم يتم إرسال رقم الغرفة", "error")
            return redirect(url_for("all_rooms_view"))

        room_id = int(room_id_raw)
        filepath = os.path.join(DATA_DIR, f"room{room_id}.xlsx")

        if not os.path.exists(filepath):
            flash("⚠️ الملف غير موجود", "error")
            return redirect(url_for("all_rooms_view"))

        df = pd.read_excel(filepath)

        if action == "vote":
            reg_number = str(request.form.get("reg_number")).strip()
            full_name = str(request.form.get("full_name")).strip()
            current_status = request.form.get("current_status")

            match_idx = df[
                (df["رقم القيد"].astype(str).str.strip() == reg_number) &
                (df["الإسم الثلاثي"].astype(str).str.strip() == full_name)
            ].index

            if not match_idx.empty:
                new_status = "" if current_status == "✅" else "✅"
                df.loc[match_idx[0], "صوّت؟"] = new_status
                df.to_excel(filepath, index=False)
                flash("✅ تم تحديث التصويت بنجاح", "success")
            else:
                flash("⚠️ لم يتم العثور على السجل للتحديث", "error")

        elif action == "delete":
            row_index = request.form.get("row_index")
            if row_index is not None:
                row_index = int(row_index)
                if 0 <= row_index < len(df):
                    df = df.drop(index=row_index)
                    df.reset_index(drop=True, inplace=True)
                    df.to_excel(filepath, index=False)
                    flash("🗑️ تم حذف السجل بنجاح", "success")
                else:
                    flash("❌ فشل الحذف: رقم الصف غير صحيح", "error")
            else:
                flash("❌ فشل الحذف: لم يتم إرسال رقم الصف", "error")

        elif action == "edit":
            row_index = request.form.get("row_index")
            new_name = request.form.get("new_name")
            if row_index is not None:
                row_index = int(row_index)
                if 0 <= row_index < len(df):
                    df.at[row_index, "الإسم الثلاثي"] = new_name
                    df.to_excel(filepath, index=False)
                    flash(f"✏️ تم تعديل الاسم إلى: {new_name}", "success")
                else:
                    flash("❌ رقم الصف غير صالح", "error")

        return redirect(url_for("all_rooms_view"))

    return render_template("all_rooms.html",
                           df=full_df.to_dict(orient="records"),
                           unique_families=unique_families,
                           unique_registrations=unique_regs,
                           duplicate_count=duplicate_count,
                           duplicate_keys=duplicate_keys,
                           duplicate_rows=duplicate_rows,
                           all_full_names=full_df["الإسم الثلاثي"].tolist(),
                           total=total_all,
                           voted=voted_all,
                           not_voted=not_voted_all,
                           percent=percent_all,
                           role=session.get("role"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5555)
