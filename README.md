# 🗳️ Elections Program - Voter Tracking System

This application helps manage and track voters across multiple rooms using a web interface powered by Flask and Excel files.

---

## 🖥️ Requirements

- Python 3.10.11
- Required Libraries:
  - Flask
  - pandas
  - openpyxl
  - matplotlib
  - pyinstaller (for building executables if needed)

---

## 🚀 Running the Application

1. Ensure there's a `data/` folder that contains Excel files such as `room1.xlsx`, `room2.xlsx`, etc.
2. To start the server:

```bash
python main_server.py
```

3. Open your browser and visit:

```
http://127.0.0.1:7777/
```

---

## 🔐 Login Information

- **Admin user**:
  - Has full access to all rooms
  - Can add, edit, delete records
  - Can view duplicate entries

- **Room user**:
  - Can only update the voting status of voters

---

## ✍️ How to Use

### ✅ To record a vote:
Click the ✅ button next to the voter's name. To undo, click ❌.

### ✏️ To edit a row:
- Modify values directly in the text fields
- Click "✏️ Edit"
- A confirmation dialog will appear

### ➕ To add a new record:
- Use the form at the top of the page
- Fill in all required fields and click ✔️ Add

### 🗑️ To delete a record:
- Click "🗑️ Delete"
- A confirmation prompt will appear

---

## ⚠️ Important Notes

- **Do NOT manually edit the Excel files while the server is running**
- Ensure all field values match the expected data types (especially numeric columns)
- Duplicate detection is done automatically (ignoring the "Voted?" column)
- Room Excel filenames **must be named as `room1.xlsx`, `room2.xlsx`, etc.**

### Required Excel Columns (in Arabic):
Make sure your Excel sheet contains the following column names (right-to-left order):

- الإسم الثلاثي
- الإسم
- إسم الأب
- العائلة
- إسم الأم والشهرة
- الجنس
- تاريخ الولادة
- رقم القيد

---

## 📁 Project Structure

```
elections_program/
├── data/
│   ├── room1.xlsx
│   ├── room2.xlsx
├── templates/
│   ├── all_rooms.html
│   ├── room.html
├── static/
├── main_server.py
├── README.md
```

---

## 📞 Support

For issues or questions, contact the developer.

---

📝 This application was built to help track local elections efficiently and securely.
