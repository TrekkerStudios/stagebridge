# client_web_server.py
import os
from flask import Flask, render_template, send_from_directory

def create_client_app():
    """Creates and configures the Flask application for the client frontend."""

    # Define paths relative to this file
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    PUBLIC_FOLDER = os.path.join(CURRENT_DIR, "templates", "public")
    CLIENT_TEMPLATES_FOLDER = os.path.join(CURRENT_DIR, "templates", "client")

    # Initialize Flask app
    # static_folder is set to PUBLIC_FOLDER to serve JS/CSS/etc. from /
    # static_url_path='/' makes files in PUBLIC_FOLDER accessible directly at the root,
    # e.g., /app.js will serve public/app.js.
    app = Flask(
        __name__,
        static_folder=PUBLIC_FOLDER,
        static_url_path="/",  # Serves files from public_folder directly at root /
        template_folder=CLIENT_TEMPLATES_FOLDER,  # For client's index.html
    )

    # Route for the main client application page
    @app.route("/")
    def serve_client_index():
        # Flask's render_template looks in the configured template_folder
        # so it will look for templates/client/index.html
        return render_template("index.html")

    # This catch-all route is important for Single Page Applications (SPAs)
    # If the user navigates directly to a client-side route (e.g., /settings)
    # and the server doesn't have a specific route for it, it should serve
    # the main index.html so the client-side router can handle the path.
    @app.errorhandler(404)
    def not_found(e):
        return render_template("index.html"), 200

    return app