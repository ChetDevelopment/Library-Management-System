# LibraryPNC

**LibraryPNC** is a modern, responsive homepage for a library management system built for *Passerelles numériques Cambodia (PNC)*. This repository contains the front-end template for the homepage (HTML/CSS/JS) with example Flask route placeholders for backend integration.

---

## 🚀 Features

* Clean, modern hero section with call-to-action (Register).
* Navigation for Home, Admin Login, Register, Login.
* Features section highlighting the library's benefits (Extensive Collection, Easy Search, Personal Dashboard).
* Floating background elements and scroll animations.
* Footer with quick links and branding.

---

## 📁 Project Structure

```
LibraryPNC/
│
├── templates/
│   └── home.html          # Main HTML page (provided)
│
├── static/
│   ├── css/
│   │   └── main.css       # Custom styling
│   ├── js/
│   │   └── main.js        # Optional separate JS (or inline in home.html)
│   └── images/
│       └── (assets)
│
├── app.py                 # Example Flask app (see Usage)
└── README.md              # This file
```

---

## 🛠️ Technologies

* HTML5, CSS3, JavaScript
* Flask (Python) for server-side routing examples
* Google Fonts: Inter
* Remix Icon library for icons
* Unsplash (sample image)

---

## 💡 Installation & Quick Start (Flask example)

1. Create a virtual environment and install Flask:

```bash
python -m venv venv
source venv/bin/activate      # macOS / Linux
venv\Scripts\activate       # Windows
pip install Flask
```

2. Place the provided `home.html` into `templates/` and CSS into `static/css/main.css`.

3. Example `app.py` (simple Flask app):

```python
from flask import Flask, render_template, url_for

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/admin')
def admin_login():
    return "Admin login page placeholder"

@app.route('/register')
def register():
    return "Register page placeholder"

@app.route('/login')
def login():
    return "Login page placeholder"

if __name__ == '__main__':
    app.run(debug=True)
```

4. Run the app:

```bash
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

---

## 🧩 HTML Snippet (home.html)

> Put the full HTML provided in `templates/home.html`. It uses `url_for()` for dynamic links to `home`, `admin_login`, `register`, and `login` routes.

---

## 🎨 Styling & Assets

* The HTML references `/static/css/main.css`. Add your CSS rules there or keep the inline JS in the HTML as-is.
* Replace the Unsplash image URL with your local asset under `static/images/` for production.

---

## ✅ To Do / Future Improvements

* Implement search and book listing with database (SQLite / MySQL / PostgreSQL).
* Add authentication for users and admin (Flask-Login / OAuth).
* Create user dashboard for borrowed books and history.
* Add pagination, filters, and full-text search.
* Improve accessibility and mobile responsiveness.

---

## 🧾 License

This project is MIT-licensed by default. Replace the license text below with your project license if different.

```
MIT License

Copyright (c) 2023 LibraryPNC

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions: ...
```

---

## 👩‍💻 Contributors

* Your Name – Project setup and template
* (Add additional contributors here)

---

## 📬 Contact

For questions or contributions, open an issue or contact the maintainer.

---

*Generated README for LibraryPNC.*
