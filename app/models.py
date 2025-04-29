from datetime import datetime, timezone
from hashlib import md5
from time import time
from typing import Optional

import jwt
import sqlalchemy as sa
import sqlalchemy.orm as so
from werkzeug.security import check_password_hash, generate_password_hash

from app import app
from app import db
from app import login
from flask_login import UserMixin


# Followers is a self relationsal table representing a many-to-many relationship
# (i.e: each user can have many followers and can follow many users)
# Since this table has no NEW data (only foreign keys) it need not be a model class
# +-----------------------------+        +-----------------------------+
# |           users             |        |           followers         |
# +-----------------------------+        +-----------------------------+
# | id            INTEGER       |--+---> | follower_id       INTEGER   |
# | username      VARCHAR(64)   |  |---> | followed_id       INTEGER   |
# | email         VARCHAR(120)  |        +-----------------------------+
# | password_hash VARCHAR(128)  |
# +-----------------------------+
followers = sa.Table(
    "followers",
    db.metadata,  # Where SQLAlchemy stores info about all the tables in the database
    # Compound primary key means combination of these keys is unique (i.e: a user can only follow another one time)
    sa.Column("follower_id", sa.Integer, sa.ForeignKey("user.id"), primary_key=True),
    sa.Column("followed_id", sa.Integer, sa.ForeignKey("user.id"), primary_key=True),
)


# +-----------------------------+        +-----------------------------+
# |           users             |        |           posts             |
# +-----------------------------+        +-----------------------------+
# | id            INTEGER       |<--     | id            INTEGER       |
# | username      VARCHAR(64)   |  |     | body          VARCHAR(140)  |
# | email         VARCHAR(120)  |  |     | timestamp     DATETIME      |
# | password_hash VARCHAR(128)  |  |---> | user_id       INTEGER       |
# +-----------------------------+        +-----------------------------+
class User(UserMixin, db.Model):
    # These are the columns that will be stored in the database for each user
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True, unique=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True, unique=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    posts: so.WriteOnlyMapped["Post"] = so.relationship(back_populates="author")
    about_me: so.Mapped[Optional[str]] = so.mapped_column(sa.String(140))
    last_seen: so.Mapped[Optional[datetime]] = so.mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    following: so.WriteOnlyMapped["User"] = so.relationship(
        secondary=followers,  # Configures the association table used for this relationship
        primaryjoin=(
            followers.c.follower_id == id
        ),  # indicates the condition that links the user to the table (i.e: who is following)
        secondaryjoin=(
            followers.c.followed_id == id
        ),  # indicates the condition that links the table to the user on the other side of the relationship (i.e: who is being followed)
        back_populates="followers",  # When following is updated, followers are automatically updated as well
    )
    followers: so.WriteOnlyMapped["User"] = so.relationship(
        secondary=followers,
        primaryjoin=(followers.c.followed_id == id),  # .c is short for columns
        secondaryjoin=(followers.c.follower_id == id),
        back_populates="following",
    )

    def __repr__(self):
        return f"<User {self.username}>"

    def avatar(self, size):
        digest = md5(self.email.lower().encode("utf-8")).hexdigest()
        return f"https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}"

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
            {"reset_password": self.id, "exp": time() + expires_in},
            app.config["SECRET_KEY"],
            algorithm="HS256",
        )

    @staticmethod
    def verify_reset_password_token(token):
        try:
            # If the token is valid, the value of reset_password from the token's payload is the ID of the user
            id = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])[
                "reset_password"
            ]
        except:
            return
        return db.session.get(User, id)

    def follow(self, user):
        if not self.is_following(user):
            self.following.add(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.following.remove(user)

    def is_following(self, user):
        query = self.following.select().where(User.id == user.id)
        return db.session.scalar(query) is not None

    def followers_count(self):
        # select would generally return the entities, but here we just care about their count
        query = sa.select(sa.func.count()).select_from(
            # Whenever a query is included as part of a larger query, SQLAlchemy requires the inner query to be converted to a sub-query
            self.followers.select().subquery()
        )
        return db.session.scalar(query)

    def following_count(self):
        query = sa.select(sa.func.count()).select_from(
            self.following.select().subquery()
        )
        return db.session.scalar(query)

    def following_posts(self):
        Author = so.aliased(User)
        Follower = so.aliased(User)
        # A join is a an operation that combines the rows from two tables into a temporary table
        # (i.e: the cols containing tables of posts are appended with columns containing the post's author, which are appended with columns of the follower of these posts)
        #                     ALL POSTS                +          AUTHORS (User)         +       FOLLOWERS (User)
        #  =============================================================================================================
        #  | post.id |	post.text 	   |  post.user_id   |	author.id |	author.username  |follower.id |follower.username|
        #  =============================================================================================================
        #  |    1    | post from susan |	   2 	     |      2 	  |      susan 	     |     1      |   	john        |
        #  |    2    | post from mary  |	   3 	     |      3 	  |      mary 	     |     2      |     susan       |
        #  |    3    | post from david |	   4 	     |      4 	  |      david 	     |     1      |     john        |
        #  |    3    | post from david |	   4 	     |      4 	  |      david 	     |     3      |     mary        |
        #  =============================================================================================================
        # Note that post 3 is included twice because david has two followers
        # Note that posts written that don't have followers won't be included
        # Outer joins keep posts with no matches (no followers) on the right side of the join
        #  |    4    | post from john  |	   1 	     |      1	  |      john 	     |     null   |     null        |
        return (
            sa.select(Post)
            # Users added to the combined table from this join will be known as Author
            .join(Post.author.of_type(Author))
            # Users added to the combined table from this join will be known as Follower
            .join(Author.followers.of_type(Follower), isouter=True)
            # The resulting joins shows all posts followed by a user, we only care about those followed by the current user
            # Here we see the usefullness of the Follower Alias, else User.id could mean the Author User or the Follower User
            .where(sa.or_(Follower.id == self.id, Author.id == self.id))
            # Eliminate duplicates in the final list (for example the two entries with post id 3)
            .group_by(Post)
            # Most recent first
            .order_by(Post.timestamp.desc())
        )


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
