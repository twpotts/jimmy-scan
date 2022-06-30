# App.py is the back-end for your webpage

# Import required packages

from flask import Flask, render_template, url_for, request, redirect, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError
import config
import requests
import json
import pandas as pd
import numpy as np
import datetime as dt
import pyrebase
import pytz
import time

# Create a Flask app

app = Flask(__name__)

# Define user login database

app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///database.db"
app.config['SECRET_KEY'] = "UYBBV8v1L7VuBjveOehvWFhGaHTRUNSz"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Create user login system

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    password = db.Column(db.String(80), nullable=False)

class RegisterForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(
        min=4, max=20)], render_kw={"placeholder": "Username"})
    password = PasswordField(validators=[InputRequired(), Length(
        min=4, max=20)], render_kw={"placeholder": "Password"})
    submit = SubmitField("Register")
    def validate_username(self, username):
        existing_user_username = User.query.filter_by(username=username.data).first()
        if existing_user_username:
            raise ValidationError(
                "That username already exists. Please choose a different one")

class LoginForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(
        min=4, max=20)], render_kw={"placeholder": "Username"})
    password = PasswordField(validators=[InputRequired(), Length(
        min=4, max=20)], render_kw={"placeholder": "Password"})
    submit = SubmitField("Login")

class ChangeUsernameForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(
        min=4, max=20)], render_kw={"placeholder": "Old Username"})
    new_username = StringField(validators=[InputRequired(), Length(
        min=4, max=20)], render_kw={"placeholder": "New Username"})
    password = PasswordField(validators=[InputRequired(), Length(
        min=4, max=20)], render_kw={"placeholder": "Password"})
    submit = SubmitField("Change username")

class ChangePasswordForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(
        min=4, max=20)], render_kw={"placeholder": "Username"})
    password = PasswordField(validators=[InputRequired(), Length(
        min=4, max=20)], render_kw={"placeholder": "Old Password"})
    new_password = PasswordField(validators=[InputRequired(), Length(
        min=4, max=20)], render_kw={"placeholder": "New Password"})
    submit = SubmitField("Change password")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Extract sensitive info from config

tradier_act_nbr = config.tradier_act_nbr
tradier_api = config.tradier_api
tradier_act_nbr_paper = config.tradier_act_nbr_paper
tradier_api_paper = config.tradier_api_paper

# Define function to connect to Tradier API

def auth_tradier(paper_trading=True):
    if paper_trading == True:
        tradier_base = 'https://sandbox.tradier.com/v1/'
        trad_account = tradier_act_nbr_paper
        trad_api = tradier_api_paper
    else:
        tradier_base = 'https://api.tradier.com/v1/'
        trad_account = tradier_act_nbr
        trad_api = tradier_api
    tradier_headers = {
        'Authorization': f'Bearer {trad_api}',
        'Accept': 'application/json'
    }
    auth_trad = {
        'tradier_base': tradier_base,
        'tradier_headers': tradier_headers,
        'tradier_act_nbr': trad_account
    }
    return auth_trad

# Grab ticker dictionary to set up listeners

with open("tickers_dict.txt", "r") as file:
    ticker_info = file.readlines()
    pairs = ticker_info[0].split(',')
    tickers = [item.split(':')[0].strip().replace('{','').replace("'",'') for item in pairs]
    companies = [item.split(':')[1].strip().replace('{','').replace("'",'') for item in pairs]
    tickers_dict = dict(zip(tickers, companies))
    file.close()

# Firebase

fire_config = config.db_config
db_name = "scanner"

# Create a route for the app: Whatever follows the slash how you access that page (jimmy-scan.herokuapp.com/)

@app.route('/', methods=["GET", "POST"])
@login_required
def home():    

    firebase = pyrebase.initialize_app(fire_config)
    fire_db = firebase.database()

    # If first time logging in as any user, create database

    sub_dbs = list(fire_db.get().val().keys())
    
    if db_name not in sub_dbs:
        watchlist_down = [{
            "option_symbol": "NA",
            "symbol": "NA",
            "strike": "NA",
            "expiration": "NA",
            "last": "NA",
            "delta": "NA"
        }]
        watchlist_up = [{
            "option_symbol": "NA",
            "symbol": "NA",
            "strike": "NA",
            "expiration": "NA",
            "last": "NA",
            "delta": "NA"
        }]
        db.child(db_name).child("down_list").set(watchlist_down)
        db.child(db_name).child("up_list").set(watchlist_up)
        local_timezone = local_timezone = pytz.timezone('US/Pacific')
        now = dt.datetime.now()
        db_time = now.astimezone(local_timezone).strftime("%c")
        json_info = {
            "time": db_time,
            "counter": 0,
            "symbols_length": 0,
            "progress_pct": 0,
            "length_up": 0,
            "length_down": 0,
        }
        fire_db.child(db_name).child("info").set(json_info)
        time.sleep(1)
        firebase = pyrebase.initialize_app(fire_config)
        fire_db = firebase.database()

    # Fetch data

    down_list = fire_db.child(db_name).child("down_list").get().val()
    up_list = fire_db.child(db_name).child("up_list").get().val()
    info = dict(fire_db.child(db_name).child("info").get().val())

    # Pass that data to the HTML front-end

    return render_template('home.html', heroku_api = config.heroku_api, heroku_name = config.heroku_name, 
                            script_name = config.script_name, current_user = current_user, down_list = down_list,
                            up_list = up_list, info = info, db_config = fire_config)

# Create positions page

@app.route('/positions', methods=["GET", "POST"])
@login_required
def positions():
    auth = auth_tradier()
    positions_url = '{}accounts/{}/positions'.format(auth['tradier_base'], auth['tradier_act_nbr'])
    positions_request = requests.get(positions_url, headers = auth['tradier_headers'])
    sample_positions = [
        {
            "cost_basis": 207.01,
            "date_acquired": "2018-08-08T14:41:11.405Z",
            "id": 130089,
            "quantity": 1.00000000,
            "symbol": "AAPL"
        }
    ]
    if positions_request.status_code != 200:
        print("Positions status code error")
        positions = sample_positions
    else:
        positions = json.loads(positions_request.content)
        if 'positions' not in positions:
            print(positions)
            print("Positions json error")
            positions = sample_positions
        else:
            positions = positions['positions']
            if 'position' not in positions:
                print(positions)
                print("Empty positions")
                positions = sample_positions
            else:
                positions = positions['position']

    return render_template('positions.html', positions=positions)

# Create orders page

@app.route('/orders', methods=["GET", "POST"])
@login_required
def orders():
    auth = auth_tradier()
    gainloss_url = '{}accounts/{}/gainloss'.format(auth['tradier_base'], auth['tradier_act_nbr'])
    gainloss_request = requests.get(gainloss_url, headers = auth['tradier_headers'])
    sample_gainloss = [
      {
        "close_date": "2018-10-31T00:00:00.000Z",
        "cost": 12.7,
        "gain_loss": -2.64,
        "gain_loss_percent": -20.7874,
        "open_date": "2018-06-19T00:00:00.000Z",
        "proceeds": 10.06,
        "quantity": 1.0,
        "symbol": "GE",
        "term": 134
      }
    ]
    if gainloss_request.status_code != 200:
        print("Gainloss status code error")
        orders = sample_gainloss
    else:
        orders = json.loads(gainloss_request.content)
        if 'gainloss' not in orders:
            print("Gainloss json error")
            orders = sample_gainloss
        else:
            orders = orders['gainloss']
            if 'closed_position' not in orders:
                print(orders)
                print("Empty gainlosses")
                orders = sample_gainloss
            else:
                orders = orders['closed_position']
    return render_template('orders.html', orders=orders)

# Create chart page

@app.route('/chart', methods=["GET", "POST"])
@login_required
def chart():
    page_ticker = "MSFT"
    return render_template('chart.html', page_ticker=page_ticker)

# Define login page

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            #if bcrypt.check_password_hash(user.password, form.password.data):
            if user.password == form.password.data:
                login_user(user)
                return redirect(url_for('home'))
            else:
                flash(f'Password {form.password.data} is incorrect for user {form.username.data}; try again', category="error")
                return render_template('login.html', form=form)
        else:
            flash(f'User {form.username.data} not found in database; try again', category="error")
            return render_template('login.html', form=form, current_user = current_user)
    return render_template('login.html', form=form)

# Define registration page

@app.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    form = RegisterForm()
    if current_user.id == 1:
        if form.validate_on_submit():
            form.validate_username(form.username)
            #hashed_password = bcrypt.generate_password_hash(form.password.data)
            #new_user = User(username=form.username.data, password=hashed_password)
            new_user = User(username=form.username.data, password=form.password.data)
            db.session.add(new_user)
            db.session.commit()
            flash(f"User {form.username.data} successfully registered with password = {form.password.data}", category="success")
            return redirect(url_for('login'))
        return render_template('register.html', form=form, current_user = current_user)
    else:
        flash("Only the administrator can register new users", category="error")
        return redirect(url_for('login'))

# Define logout page

@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    flash('User successfully logged out', category="success")
    return redirect(url_for('login'))

# Define change username page

@app.route('/change_username', methods=['GET', 'POST', 'PUT'])
def change_username():
    form = ChangeUsernameForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            if user.password == form.password.data:
                existing_user_username = User.query.filter_by(username=form.new_username.data).first()
                if not existing_user_username:
                    user.username = form.new_username.data
                    db.session.commit()
                    flash(f'Username {form.username.data} has been changed to {form.new_username.data}', category="success")
                    return render_template('change_username.html', form=form)
                else:
                    flash(f'Username {form.new_username.data} already exists. Usernames must be unique; try again.', category="error")
                    return render_template('change_username.html', form=form)
            else:
                flash(f'Password {form.password.data} is incorrect for user {form.username.data}; try again', category="error")
                return render_template('change_username.html', form=form)
        else:
            flash(f'User {form.username.data} not found in database; try again', category="error")
            return render_template('change_username.html', form=form, current_user = current_user)
    return render_template('change_username.html', form=form)

# Define change password page

@app.route('/change_password', methods=['GET', 'POST', 'PUT'])
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            if user.password == form.password.data:
                user.password = form.new_password.data
                db.session.commit()
                flash(f'User {form.username.data} has changed their password to {form.new_password.data}', category="success")
                return render_template('change_password.html', form=form)
            else:
                flash(f'Password {form.password.data} is incorrect for user {form.username.data}; try again', category="error")
                return render_template('change_password.html', form=form)
        else:
            flash(f'User {form.username.data} not found in database; try again', category="error")
            return render_template('change_password.html', form=form, current_user = current_user)
    return render_template('change_password.html', form=form)

# Run the app

if __name__ == '__main__':
    db.create_all()
    app.run(debug=True)