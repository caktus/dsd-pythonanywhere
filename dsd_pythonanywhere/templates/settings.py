{{current_settings}}

# PythonAnywhere settings.
import os  # noqa: E402

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

if os.getenv("ON_PYTHONANYWHERE"):
    import dj_database_url

    DEBUG = os.getenv("DEBUG") == "TRUE"
    SECRET_KEY = os.getenv("SECRET_KEY")

    try:
        ALLOWED_HOSTS.append("*")
    except NameError:
        ALLOWED_HOSTS = ["*"]

    DATABASES = {
        "default": dj_database_url.config(),
    }

    STATIC_ROOT = os.path.join(BASE_DIR, "static")
