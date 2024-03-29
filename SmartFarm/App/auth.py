import paho.mqtt.client as mqtt
import time
import functools
from pickle import GLOBAL
import sqlite3
from re import A
from threading import local
import requests
import pandas as pd
import random  # Import for Test#
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash
from App.db import get_db, get_db2
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
bp = Blueprint('auth', __name__, url_prefix='/auth')

########## HOME PAGE ROUTE ##########


@bp.route("/", methods=('GET', 'POST'))
def Home():

    return render_template('auth/Home.html')

########## REGISTER ROUTE ##########


@bp.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None

        if not username:
            error = 'Username is required.'
        elif not password:
            error = 'Password is required.'

        if error is None:
            try:
                db.execute(
                    "INSERT INTO user (username, password) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )
                db.commit()
            except db.IntegrityError:
                error = f"User {username} is already registered."
            else:
                return redirect(url_for("auth.login"))

        flash(error)

    return render_template('auth/register.html')

########## LOGIN ROUTE ##########


@bp.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None
        user = db.execute(
            'SELECT * FROM user WHERE username = ?', (username,)
        ).fetchone()

        if user is None:
            error = 'Incorrect username.'

        elif not check_password_hash(user['password'], password):
            error = 'Incorrect password.'

        if error is None:
            session.clear()
            session['user_id'] = user['id']
            return redirect(url_for('auth.Home'))

        flash(error)

    return render_template('auth/login.html')

########## CHECK USER ID ##########


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        g.user = get_db().execute(
            'SELECT * FROM user WHERE id = ?', (user_id,)
        ).fetchone()

########## LOGOUT ROUTE ##########


@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.Home'))

########## REQUEST LOGIN ##########


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))

        return view(**kwargs)

    return wrapped_view

########## PROFILE ROUTE ##########


@bp.route('/profile', methods=('GET', 'POST'))
def profile():
    db = get_db()
    user = db.execute('SELECT * FROM pfile WHERE p_id = ?;', (g.user['id'],)
                      ).fetchone()

    if user is not None:
        database = get_db2()
        con = sqlite3.connect(database)
        cur = con.cursor()
        row = cur.execute('SELECT * FROM pfile WHERE p_id = ?',
                          (g.user['id'],)).fetchone()

        fullname = row[2]
        adress = row[3]
        zipcode = row[4]
    else:
        fullname = "----------------------"
        adress = "โปรดกรอกข้อมูลส่วนบุคคล"
        zipcode = "----------------------"

    return render_template('auth/profile.html',
                           data={"fullname": fullname,
                                 "adress": adress,
                                 "zipcode": zipcode})

########## EDITPROFILE ROUTE ##########


@bp.route('/editprofile', methods=('GET', 'POST'))
def editprofile():
    if request.method == 'POST':
        fullname = request.form['fullname']
        adress = request.form['adress']
        zipcode = request.form['zipcode']
        user_id = session.get('user_id')
        db = get_db()

        if user_id is not None:
            pro_user = db.execute(
                'SELECT * FROM pfile WHERE p_id = ?', (user_id,)).fetchone()
            if pro_user is not None:
                db.execute(
                    'UPDATE pfile SET fullname = ?, adress = ?, zipcode = ?, p_id = ?'
                    ' WHERE p_id = ?',
                    (fullname, adress, zipcode, g.user['id'], g.user['id'])
                )
                db.commit()
                return redirect(url_for("auth.profile"))
            else:
                db.execute(
                    "INSERT INTO pfile (fullname, adress, zipcode, p_id) VALUES (?, ?, ?, ?)",
                    (fullname, adress, zipcode, g.user['id']),
                )
                db.commit()
                return redirect(url_for("auth.profile"))

    return render_template('auth/editprofile.html')


########## PROGRAM ROUTE ##########
### SECTION PREDICTMODEL ####
data = pd.read_csv("App/dataset/data_rambutan.csv")
X = data.iloc[:, [0, 1, 2, 3]].values
y = data.iloc[:, 4].values
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.1, random_state=22)
clf = MLPClassifier(hidden_layer_sizes=(100),
                    max_iter=300,
                    activation='logistic',
                    solver='adam',
                    random_state=1)
history = clf.fit(X_train, y_train)
ypred = clf.predict(X_test)


@bp.route('/program', methods=('GET', 'POST'))
def program():
    ### SECTION GET FOR MQTT ####
    # Callback Function on Connection with MQTT Server
    def on_connect(client, userdata, flags, rc):
        print("Connected with Code :" + str(rc))
        # Subscribe Topic from here
        client.subscribe("/auto_redue/mqtt/status")

    # Callback Function on Receiving the Subscribed Topic/Message
    def on_message(client, userdata, msg):
        # print the message received from the subscribed topic
        print(str(msg.payload))

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect("broker.hivemq.com", 1883, 60)

### SECTION SELECT LOCATION WITH ZIPCODE ####
    db = get_db()
    user = db.execute('SELECT * FROM pfile WHERE p_id = ?;', (g.user['id'],)
                      ).fetchone()

    if user is not None:
        database = get_db2()
        con = sqlite3.connect(database)
        cur = con.cursor()
        row = cur.execute('SELECT * FROM pfile WHERE p_id = ?',
                          (g.user['id'],)).fetchone()
        Zipcode = row[4]  # ZIPCODE FOR SELECT LOCATION
    else:
        Zipcode = "22000"  # DEFUALT LACATION

### SECTION API WEATHER ####
    # https://api.openweathermap.org/data/2.5/weather?zip=94040,us&appid={API key}
    user_api = "7b9a86d2006cc3e7c4c1c2d4bc38d743"
    complete_api_link = "https://api.openweathermap.org/data/2.5/weather?zip=" + \
        Zipcode+",th&appid="+user_api
    api_link = requests.get(complete_api_link)
    api_data = api_link.json()
    temp_city = ((api_data['main']['temp']) - 273.15)
    hmdt = api_data['main']['humidity']
    weather_desc = api_data['weather'][0]['description']
    ftemp_city = "{:.2f}".format(float(temp_city))

    def prediction(Moisture, temp_city, hmdt, weather_desc):
        if weather_desc.find("rain") == True:
            weather_desc = 1
        else:
            weather_desc = 0
        inpredict = [[Moisture, temp_city, hmdt, weather_desc]]
        opredict = clf.predict(inpredict)

        return opredict

    Moisture = random.randrange(40, 100)
    Status = prediction(Moisture, temp_city, hmdt, weather_desc)
    if Status == 0:
        Status = "ไม่เหมาะสมกับการรดน้ำ"
    else:
        Status = "เหมาะสมกับการรดน้ำ"

    # def looping(pipeline):
    #     while pipeline == "9":
    #         Moisture = random.randrange(40, 100)
    #         Status = prediction(Moisture, temp_city, hmdt, weather_desc)
    #         if Status == 0:
    #             cStatus = "0"
    #             pipeline = "0"
    #             client.publish("/auto_redue/mqtt/control/motor", cStatus)
    #             print(">>>>>>", cStatus, "<<<<<<")
    #             return pipeline
    #         else:
    #             cStatus = "9"
    #             pipeline = "9"
    #             client.publish("/auto_redue/mqtt/control/motor", cStatus)
    #             print(cStatus)
    #             time.sleep(1)

    if request.method == 'POST':
        pipeline = request.form['pipeline']
        client.username_pw_set("", "")
        client.publish("/auto_redue/mqtt/control/motor", pipeline)

        user_id = session.get('user_id')
        if user_id is not None:

            db.execute(
                "INSERT INTO datatrain (d_id, moisture, temperature, humidity, weather, watering) VALUES (?, ?, ?, ?, ?, ?)",
                (g.user['id'], Moisture, temp_city, hmdt, weather_desc, 1),
            )
            db.commit()

        print(pipeline)

    return render_template('auth/program.html',
                           data={"temp": ftemp_city,
                                 "weather": weather_desc,
                                 "Status": Status,
                                 "Moisture": Moisture,
                                 "humidity": hmdt})
