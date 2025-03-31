from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
import sqlalchemy.orm as so
from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from app import login
from flask_login import UserMixin


# +-----------------------------+        +-----------------------------+
# |           users            |        |           posts            |
# +-----------------------------+        +-----------------------------+
# | id            INTEGER       |<--     | id            INTEGER       |
# | username      VARCHAR(64)   |  |     | body          VARCHAR(140) |
# | email         VARCHAR(120)  |  |     | timestamp     DATETIME     |
# | password_hash VARCHAR(128)  |  |---> | user_id       INTEGER       |
# +-----------------------------+        +-----------------------------+
class User(UserMixin, db.Model):
    # These are the columns that will be stored in the database for each user
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True, unique=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True, unique=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    posts: so.WriteOnlyMapped["Post"] = so.relationship(back_populates="author")

    def __repr__(self):
        return f"<User {self.username}>"

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Post(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    body: so.Mapped[str] = so.mapped_column(sa.String(140))
    # When you pass a function as default, SQLAlchemy sets the field to the return value of that function
    timestamp: so.Mapped[datetime] = so.mapped_column(
        index=True, default=lambda: datetime.now(timezone.utc)
    )
    # A foreign key references a primary key of another table
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)
    author: so.Mapped[User] = so.relationship(back_populates="posts")

    def __repr__(self):
        return f"<Post {self.body}>"


@login.user_loader
def load_user(id: str):
    return db.session.get(User, int(id))
