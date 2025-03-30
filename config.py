import os
from pathlib import Path

# Path(__file__) wraps the current filepath in a path object
# resolve() turns that path into an absolute one
# parent gives the directory
basedir = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "you-will-never-guess")
    # URI is a Uniform Resource Identifier -- it answers "What resource are you talking about"
    # URL is a Uniform Resource Locator is a type of URI that also locates the resource
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{basedir / 'app.db'}"
    )
