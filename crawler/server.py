"""
StockPulse Web Server
Flask-based web server with authentication and admin API.
"""

import os
import json
import logging
import argparse
from datetime import datetime
from functools import wraps

import bcrypt
from flask import (
    Flask, request, jsonify, redirect, url_for,
    send_from_directory, abort, session
)
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)

from .database import db as db_manager
from .database import User
from .config import DATA_DIR, BASE_DIR

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Flask app setup
# ---------------------------------------------------------------------------

app = Flask(
    __name__,
    static_folder=BASE_DIR,
    static_url_path="/static",
)
app.secret_key = os.environ.get("STOCKPULSE_SECRET") or os.urandom(32)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login_page"


# ---------------------------------------------------------------------------
# Flask-Login user wrapper
# ---------------------------------------------------------------------------

class SessionUser(UserMixin):
    """Thin wrapper around the SQLAlchemy User model for Flask-Login."""

    def __init__(self, user_row):
        self.id = user_row.id
        self.username = user_row.username
        self.email = user_row.email
        self.is_admin = user_row.is_admin
        self.is_active_user = user_row.is_active

    def get_id(self):
        return str(self.id)

    @property
    def is_active(self):
        return self.is_active_user


@login_manager.user_loader
def load_user(user_id):
    """Reload user object from the user ID stored in the session."""
    session_db = db_manager.get_session()
    try:
        user_row = session_db.query(User).filter_by(id=int(user_id)).first()
        if user_row and user_row.is_active:
            return SessionUser(user_row)
        return None
    finally:
        session_db.close()


# ---------------------------------------------------------------------------
# Custom decorators
# ---------------------------------------------------------------------------

def admin_required(f):
    """Decorator that requires the current user to be an admin."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            return jsonify({"error": "Admin privileges required"}), 403
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# CORS middleware for local development
# ---------------------------------------------------------------------------

@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin", "")
    if origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1"):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response


@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = app.make_default_options_response()
        origin = request.headers.get("Origin", "")
        if origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1"):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        return response


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _check_password(password: str, password_hash: str) -> bool:
    """Verify a password against its bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def _user_to_dict(user_row) -> dict:
    """Serialize a User row to a JSON-safe dict (no password hash)."""
    return {
        "id": user_row.id,
        "username": user_row.username,
        "email": user_row.email,
        "is_admin": user_row.is_admin,
        "is_active": user_row.is_active,
        "created_at": user_row.created_at.isoformat() if user_row.created_at else None,
        "last_login": user_row.last_login.isoformat() if user_row.last_login else None,
    }


def _read_json_file(filename: str):
    """Read a JSON file from DATA_DIR and return its contents."""
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.isfile(filepath):
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


# ===================================================================
# AUTH ROUTES
# ===================================================================

@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    """Authenticate a user with username and password."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    db_session = db_manager.get_session()
    try:
        user_row = db_session.query(User).filter_by(username=username).first()

        if not user_row or not _check_password(password, user_row.password_hash):
            return jsonify({"error": "Invalid username or password"}), 401

        if not user_row.is_active:
            return jsonify({"error": "Account is deactivated"}), 403

        # Update last login timestamp
        user_row.last_login = datetime.utcnow()
        db_session.commit()

        session_user = SessionUser(user_row)
        login_user(session_user, remember=True)

        return jsonify({
            "message": "Login successful",
            "user": _user_to_dict(user_row),
        })
    except Exception as e:
        db_session.rollback()
        logger.exception("Login error")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        db_session.close()


@app.route("/api/auth/logout", methods=["POST"])
@login_required
def auth_logout():
    """Log the current user out."""
    logout_user()
    return jsonify({"message": "Logged out successfully"})


@app.route("/api/auth/status", methods=["GET"])
def auth_status():
    """Return current authentication status."""
    if current_user.is_authenticated:
        return jsonify({
            "authenticated": True,
            "user": {
                "id": current_user.id,
                "username": current_user.username,
                "email": current_user.email,
                "is_admin": current_user.is_admin,
            },
        })
    return jsonify({"authenticated": False})


@app.route("/api/auth/change-password", methods=["POST"])
@login_required
def auth_change_password():
    """Allow a logged-in user to change their own password."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")

    if not current_password or not new_password:
        return jsonify({"error": "Current and new password are required"}), 400

    if len(new_password) < 8:
        return jsonify({"error": "New password must be at least 8 characters"}), 400

    db_session = db_manager.get_session()
    try:
        user_row = db_session.query(User).filter_by(id=current_user.id).first()
        if not user_row:
            return jsonify({"error": "User not found"}), 404

        if not _check_password(current_password, user_row.password_hash):
            return jsonify({"error": "Current password is incorrect"}), 401

        user_row.password_hash = _hash_password(new_password)
        db_session.commit()

        return jsonify({"message": "Password changed successfully"})
    except Exception as e:
        db_session.rollback()
        logger.exception("Change password error")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        db_session.close()


# ===================================================================
# ADMIN API ROUTES
# ===================================================================

@app.route("/api/admin/users", methods=["GET"])
@admin_required
def admin_list_users():
    """List all users (without password hashes)."""
    db_session = db_manager.get_session()
    try:
        users = db_session.query(User).order_by(User.created_at.asc()).all()
        return jsonify({"users": [_user_to_dict(u) for u in users]})
    finally:
        db_session.close()


@app.route("/api/admin/users", methods=["POST"])
@admin_required
def admin_create_user():
    """Create a new user."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")
    is_admin = bool(data.get("is_admin", False))

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    db_session = db_manager.get_session()
    try:
        # Check for duplicate username
        if db_session.query(User).filter_by(username=username).first():
            return jsonify({"error": "Username already exists"}), 409

        # Check for duplicate email (if provided)
        if email and db_session.query(User).filter_by(email=email).first():
            return jsonify({"error": "Email already in use"}), 409

        new_user = User(
            username=username,
            email=email,
            password_hash=_hash_password(password),
            is_admin=is_admin,
            is_active=True,
            created_at=datetime.utcnow(),
        )
        db_session.add(new_user)
        db_session.commit()

        return jsonify({
            "message": "User created",
            "user": _user_to_dict(new_user),
        }), 201
    except Exception as e:
        db_session.rollback()
        logger.exception("Create user error")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        db_session.close()


@app.route("/api/admin/users/<int:user_id>", methods=["PUT"])
@admin_required
def admin_update_user(user_id):
    """Update user fields (email, is_admin, is_active)."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    db_session = db_manager.get_session()
    try:
        user_row = db_session.query(User).filter_by(id=user_id).first()
        if not user_row:
            return jsonify({"error": "User not found"}), 404

        if "email" in data:
            new_email = data["email"].strip()
            # Check uniqueness if email is changing
            if new_email and new_email != user_row.email:
                existing = db_session.query(User).filter_by(email=new_email).first()
                if existing:
                    return jsonify({"error": "Email already in use"}), 409
            user_row.email = new_email

        if "is_admin" in data:
            user_row.is_admin = bool(data["is_admin"])

        if "is_active" in data:
            user_row.is_active = bool(data["is_active"])

        db_session.commit()

        return jsonify({
            "message": "User updated",
            "user": _user_to_dict(user_row),
        })
    except Exception as e:
        db_session.rollback()
        logger.exception("Update user error")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        db_session.close()


@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@admin_required
def admin_delete_user(user_id):
    """Delete a user. Admins cannot delete themselves."""
    if user_id == current_user.id:
        return jsonify({"error": "Cannot delete your own account"}), 400

    db_session = db_manager.get_session()
    try:
        user_row = db_session.query(User).filter_by(id=user_id).first()
        if not user_row:
            return jsonify({"error": "User not found"}), 404

        username = user_row.username
        db_session.delete(user_row)
        db_session.commit()

        return jsonify({"message": f"User '{username}' deleted"})
    except Exception as e:
        db_session.rollback()
        logger.exception("Delete user error")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        db_session.close()


@app.route("/api/admin/stats", methods=["GET"])
@admin_required
def admin_stats():
    """Return system statistics."""
    db_session = db_manager.get_session()
    try:
        db_stats = db_manager.get_db_stats(db_session)
        user_count = db_session.query(User).count()

        # Check for crawler status files
        crawler_status = {
            "live_data_exists": os.path.isfile(os.path.join(DATA_DIR, "live_data.json")),
            "recommendations_exists": os.path.isfile(os.path.join(DATA_DIR, "recommendations.json")),
            "stocks_exists": os.path.isfile(os.path.join(DATA_DIR, "stocks.json")),
            "news_exists": os.path.isfile(os.path.join(DATA_DIR, "news.json")),
        }

        # Get file modification times for crawler status
        for key in ["live_data", "recommendations", "stocks", "news"]:
            filepath = os.path.join(DATA_DIR, f"{key}.json")
            if os.path.isfile(filepath):
                mtime = os.path.getmtime(filepath)
                crawler_status[f"{key}_updated"] = datetime.utcfromtimestamp(mtime).isoformat()

        return jsonify({
            "user_count": user_count,
            "database": db_stats,
            "crawler": crawler_status,
        })
    finally:
        db_session.close()


# ===================================================================
# DATA API ROUTES (require login)
# ===================================================================

@app.route("/api/data/live", methods=["GET"])
@login_required
def data_live():
    """Serve live_data.json."""
    data = _read_json_file("live_data.json")
    if data is None:
        return jsonify({"error": "Live data not available yet"}), 404
    return jsonify(data)


@app.route("/api/data/recommendations", methods=["GET"])
@login_required
def data_recommendations():
    """Serve recommendations.json."""
    data = _read_json_file("recommendations.json")
    if data is None:
        return jsonify({"error": "Recommendations not available yet"}), 404
    return jsonify(data)


@app.route("/api/data/stocks", methods=["GET"])
@login_required
def data_stocks():
    """Serve stocks.json."""
    data = _read_json_file("stocks.json")
    if data is None:
        return jsonify({"error": "Stock data not available yet"}), 404
    return jsonify(data)


@app.route("/api/data/news", methods=["GET"])
@login_required
def data_news():
    """Serve news.json."""
    data = _read_json_file("news.json")
    if data is None:
        return jsonify({"error": "News data not available yet"}), 404
    return jsonify(data)


# ===================================================================
# PAGE ROUTES
# ===================================================================

@app.route("/")
def index_page():
    """Serve the main dashboard. Redirect to login if not authenticated."""
    if not current_user.is_authenticated:
        return redirect(url_for("login_page"))
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/login")
def login_page():
    """Serve the login page."""
    return send_from_directory(BASE_DIR, "login.html")


@app.route("/admin")
@login_required
def admin_page():
    """Serve the admin panel. 403 if not admin."""
    if not current_user.is_admin:
        abort(403)
    return send_from_directory(BASE_DIR, "admin.html")


# Serve static assets (css, js, img) from the project root
@app.route("/css/<path:filename>")
def serve_css(filename):
    return send_from_directory(os.path.join(BASE_DIR, "css"), filename)


@app.route("/js/<path:filename>")
def serve_js(filename):
    return send_from_directory(os.path.join(BASE_DIR, "js"), filename)


@app.route("/img/<path:filename>")
def serve_img(filename):
    return send_from_directory(os.path.join(BASE_DIR, "img"), filename)


# ===================================================================
# Unauthorized handler
# ===================================================================

@login_manager.unauthorized_handler
def unauthorized():
    """Handle unauthorized access attempts."""
    if request.path.startswith("/api/"):
        return jsonify({"error": "Authentication required"}), 401
    return redirect(url_for("login_page"))


# ===================================================================
# Server startup
# ===================================================================

def run_server(host: str = "0.0.0.0", port: int = 5000, debug: bool = False):
    """Initialize the database, create default admin, and start the Flask server."""
    # Ensure tables exist (including the User table)
    db_manager.init_db()

    # Create default admin user if no users exist
    db_session = db_manager.get_session()
    try:
        user_count = db_session.query(User).count()
        if user_count == 0:
            default_admin = User(
                username="admin",
                email="admin@stockpulse.local",
                password_hash=_hash_password("admin123"),
                is_admin=True,
                is_active=True,
                created_at=datetime.utcnow(),
            )
            db_session.add(default_admin)
            db_session.commit()
            logger.info("Default admin user created (username: admin, password: admin123)")
        else:
            logger.info("Found %d existing user(s), skipping default admin creation", user_count)
    except Exception:
        db_session.rollback()
        logger.exception("Error creating default admin user")
    finally:
        db_session.close()

    logger.info("Starting StockPulse server on %s:%d (debug=%s)", host, port, debug)
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="StockPulse Web Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5000, help="Bind port (default: 5000)")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    args = parser.parse_args()

    run_server(host=args.host, port=args.port, debug=args.debug)
