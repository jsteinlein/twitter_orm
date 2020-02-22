from flask import Flask, render_template, redirect, request, flash, session
from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy.sql import func
from datetime import datetime, timedelta
import re

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///twitter_orm.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = "secretestestbizzz"
db=SQLAlchemy(app)
migrate=Migrate(app, db)
bcrypt=Bcrypt(app)

likes_table=db.Table('likes',
    db.Column("tweet_id", db.Integer, db.ForeignKey("tweets.id"), primary_key=True),
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column('created_at', db.DateTime, server_default=func.now())
)

followers_table=db.Table('followers',
    db.Column("follower_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("followed_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("created_at", db.DateTime, server_default=func.now())
)

class User(db.Model):
    __tablename__ = "users"
    id=db.Column(db.Integer, primary_key=True)
    first_name=db.Column(db.String(100))
    last_name=db.Column(db.String(100))
    email=db.Column(db.String(200))
    password_hash=db.Column(db.String(100))
    liked_tweets=db.relationship("Tweet", secondary=likes_table)
    followers=db.relationship("User", 
        secondary=followers_table, 
        primaryjoin=id==followers_table.c.followed_id, 
        secondaryjoin=id==followers_table.c.follower_id,
        backref="following")
    created_at=db.Column(db.DateTime, server_default=func.now())
    updated_at=db.Column(db.DateTime, server_default=func.now(),onupdate=func.now())

    def full_name(self):
        return "{} {}".format(self.first_name, self.last_name)

    @classmethod
    def add_new_user(cls,data):
        new_user = cls(
            first_name=data['first_name'],
            last_name=data['last_name'],
            email=data['email'],
            password_hash=bcrypt.generate_password_hash(data['password'])
        )
        db.session.add(new_user)
        db.session.commit()
        return new_user

    @classmethod
    def find_registration_errors(cls, form_data):
        errors=[]
        if len(form_data['first_name'])<3:
            errors.append("first name is not long enough")
        if len(form_data['last_name'])<3:
            errors.append("last name is not long enough")
        if not EMAIL_REGEX.match(form_data['email']):
            errors.append("invalid email")
        if form_data['password'] != request.form['confirm']:
            errors.append("password dont match")
        if len(form_data['password']) < 8:
            errors.append("password isn't long enough")
        return errors

    @classmethod
    def register_new_user(cls, form_data):
        errors = cls.find_registration_errors(form_data)
        valid = len(errors)==0
        data = cls.add_new_user(form_data) if valid else errors
        return {
            "status": "good" if valid else "bad",
            "data": data
        }


class Tweet(db.Model):
    __tablename__="tweets"
    id=db.Column(db.Integer, primary_key=True)
    message=db.Column(db.String(140))
    author_id=db.Column(db.Integer,db.ForeignKey("users.id"))
    author=db.relationship("User", backref="tweets", cascade="all")
    likers=db.relationship("User", secondary=likes_table)
    created_at=db.Column(db.DateTime, server_default=func.now())
    updated_at=db.Column(db.DateTime, server_default=func.now(),onupdate=func.now())

    @classmethod
    def add_new_tweet(cls,tweet):
        db.session.add(tweet)
        db.session.commit()
        return tweet
    
    def age(self):
        return self.created_at
        return age


class Follow(db.Model):
    __tablename__="follows"
    id=db.Column(db.Integer, primary_key=True)
    user_id=db.Column(db.Integer, db.ForeignKey("users.id"))
    user=db.relationship("User",backref="likes", cascade="all")
    user_id=db.Column(db.Integer, db.ForeignKey("users.id"))
    user=db.relationship("User",backref="likes", cascade="all")
    created_at=db.Column(db.DateTime, server_default=func.now())


# utilities and stuff
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9.+_-]+@[a-zA-Z0-9._-]+\.[a-zA-Z]+$')


@app.route("/")
def main():
    return render_template("main.html")

@app.route("/register", methods=["POST"])
def register():
    result=User.register_new_user(request.form)
    if result['status']=="good":
        user=result['data']
        session['cur_user'] = {
            "first": user.first_name,
            "last": user.last_name,
            "id": user.id
        }
        return redirect("/twitter")
    else:
        errors=result['data']
        for error in errors:
            flash(error)
        return redirect("/")

@app.route("/twitter")
def dashboard():
    if "cur_user" not in session:
        flash("Please Log In")
        return redirect("/")
    cur_user=User.query.get(session['cur_user']['id'])
    approved_users_ids = [user.id for user in cur_user.following]+[cur_user.id]
    all_tweets=Tweet.query.filter(Tweet.author_id.in_(approved_users_ids)).all()
    return render_template("twitter.html", tweets=all_tweets)

    return render_template("twitter.html", tweets=all_tweets) if "cur_user" in session else not_logged_in()

@app.route("/login", methods=['POST'])
def login():
    user=User.query.filter_by(email=request.form['email']).all()
    valid = True if len(user)==1 and bcrypt.check_password_hash(user[0].password_hash, request.form['password']) else False
    if valid:
        session['cur_user'] = {
            "first": user.first_name,
            "last": user.last_name,
            "id": user.id
        }
        return redirect("/twitter")
    else:
        flash("Invalid login credentials")
        return redirect("/")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/tweet", methods=["POST"])
def add_tweet():
    if "cur_user" not in session:
        flash("Please Log In")
        return redirect("/")
    new_tweet=Tweet(
        message=request.form['tweet'],
        author_id=int(session['cur_user']['id'])
    )
    if len(new_tweet.message) > 0:
        Tweet.add_new_tweet(new_tweet)
    else:
        flash("need more tweet length yo!")
    return redirect("/twitter")

@app.route("/tweets/<tweet_id>/delete", methods=['POST'])
def delete_tweet(tweet_id):
    if "cur_user" not in session:
        flash("Please Log In")
        return redirect("/")
    tweet_being_deleted=Tweet.query.get(tweet_id)
    tweets_author=tweet_being_deleted.author
    tweets_author.tweets.remove(tweet_being_deleted)
    db.session.commit()
    return redirect("/twitter")

@app.route("/tweets/<tweet_id>/like", methods=["POST"])
def add_like(tweet_id):
    if "cur_user" not in session:
        flash("Please Log In")
        return redirect("/")
    liked_tweet=Tweet.query.get(tweet_id)
    liker=User.query.get(session['cur_user']['id'])
    liker.liked_tweets.append(liked_tweet)
    db.session.commit()
    return redirect("/twitter")

@app.route("/tweets/<tweet_id>/edit")
def show_edit(tweet_id):
    if "cur_user" not in session:
        flash("Please Log In")
        return redirect("/")
    tweet=Tweet.query.get(tweet_id)
    return render_template("edit.html", tweet=tweet)

@app.route("/tweets/<tweet_id>/update", methods=["POST"])
def update_tweet(tweet_id):
    if "cur_user" not in session:
        flash("Please Log In")
        return redirect("/")
    tweet=Tweet.query.get(tweet_id)
    if len(request.form['tweet'])>0:
        tweet.message=request.form['tweet']
        db.session.commit()
        return redirect("/twitter")
    else:
        flash("need more tweet!")
        return render_template("edit.html", tweet=tweet)

@app.route("/users")
def show_users():
    if "cur_user" not in session:
        flash("Please Log In")
        return redirect("/")
    users_list=User.query.all()
    return render_template("users.html", users=users_list)

@app.route("/follow/<user_id>")
def follow_user(user_id):
    if "cur_user" not in session:
        flash("Please Log In")
        return redirect("/")
    logged_in_user=User.query.get(session['cur_user']['id'])
    followed_user=User.query.get(user_id)
    followed_user.followers.append(logged_in_user)
    db.session.commit()
    return redirect("/users")

if __name__ == "__main__":
    app.run(debug=True)