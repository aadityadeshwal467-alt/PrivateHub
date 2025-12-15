# Deployment Guide for PrivateHub

This guide will help you publish your "PrivateHub" application to the web.

## Option 1: Render.com (Recommended for "Modern" setup)
**Note**: Render's free tier spins down after inactivity. For database persistence, you might need a managed database or a paid plan, but for testing, this setup handles the basics.

### 1. Push to GitHub
If you haven't already:
1.  Initialize git: `git init`
2.  Add files: `git add .`
3.  Commit: `git commit -m "Ready for deployment"`
4.  Create a new repository on GitHub.
5.  Link and push: `git remote add origin <your-repo-url>` then `git push -u origin main`

### 2. Create Service on Render
1.  Go to [dashboard.render.com](https://dashboard.render.com).
2.  Click **New +** -> **Web Service**.
3.  Connect your GitHub repository.
4.  **Runtime**: Python 3
5.  **Build Command**: `pip install -r requirements.txt`
6.  **Start Command**: `gunicorn --worker-class eventlet -w 1 app:app`
7.  **Environment Variables**:
    *   `SECRET_KEY`: (Generate a random string)
    *   `DATABASE_URL`: (Leave empty to use internal SQLite, or provide a Postgres URL if you add a database)
    *   `PORT`: `10000` (Render sets this automatically, but good to know)

### 3. Deploy
Click **Create Web Service**. Render will build and deploy your app.

---

## Option 2: PythonAnywhere (Easiest for SQLite)
Since your app uses SQLite (a file-based database), PythonAnywhere is often easier because it keeps your files (including the database) persistent across restarts.

1.  Sign up at [pythonanywhere.com](https://www.pythonanywhere.com).
2.  Go to **Web** tab -> **Add a new web app**.
3.  Select **Flask** -> **Python 3.9 (or newer)**.
4.  Path: Enter the path to your code (upload via "Files" tab or `git clone` in "Consoles").
5.  **WSGI Configuration File**:
    *   Edit the file linked in the Web tab.
    *   Comment out the "Hello World" default.
    *   Import your app:
        ```python
        import sys
        path = '/home/yourusername/PrivateHub' # check your actual path
        if path not in sys.path:
            sys.path.append(path)
        from app import app as application
        ```
6.  **Virtualenv**:
    *   Open a Bash console.
    *   Run: `mkvirtualenv myenv --python=/usr/bin/python3.9`
    *   Run: `pip install -r requirements.txt`
    *   In the Web tab, enter the path: `/home/yourusername/.virtualenvs/myenv`
7.  Reload the app.

## Important Note on Database
Your app uses **SQLite** (`database.db`).
-   **On Render/Heroku**: The file system is ephemeral. **Creating a new account or file upload will be lost** if the app restarts (which happens daily). To fix this, you should use a PostgreSQL database service.
-   **On PythonAnywhere**: The file system is persistent. Your `database.db` will be safe.
