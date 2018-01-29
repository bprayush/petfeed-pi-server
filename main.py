#! /usr/bin/python3
from flask import Flask
from flask import request
from flask import jsonify
from threading import Thread
import RPi.GPIO as GPIO
import pusherclient as PusherClient
from pusher import Pusher as PusherEvent
import ast
import os
import sys
import time
import pymysql.cursors
from datetime import datetime
import signal


##########################################################
# SETTING UP RASPBERRY PI PINS
# SETUP THE GPIO PINS TO BE USED
GPIO.setmode(GPIO.BOARD)
GPIO.setup(11, GPIO.OUT)
# SET PWM PIN syntax: GIOP.PWM(pinNo, frequency)
pwm = GPIO.PWM(11, 50)

# SETTING UP VARIABLES TO USE AS SERVO POSITIONS
# 2, 11 GIVES 180 DEGREE
# 2, 6 GIVES 90 DEGREE
servo_default_position = 2
servo_feeding_position = 6

# SET INITIAL POSITION OF THE SERVO TO DEFAULT
pwm.start(5)
pwm.ChangeDutyCycle(servo_default_position)

def device_feed():
    # MOVE THE SERVO TO FEEDING POSITION
    pwm.ChangeDutyCycle(servo_feeding_position)
    time.sleep(0.5)

    # MOVE THE SERVO TO DEFAULT POSITION
    pwm.ChangeDutyCycle(servo_default_position)
##########################################################


##########################################################
# DATABASE INITIALIZATION AND SETUP

connection = pymysql.connect(
                host="localhost",
                user="root",
                password="karkhana",
                db='raspberry_petfeed',
                cursorclass=pymysql.cursors.DictCursor
)
##########################################################


##########################################################
# DEFINING FLASK THREAD FUNCTION THAT WILL HOLD THE FLASK
def flask_server():
    # INITIALIZATOIN OF FLASK APP
    app = Flask(__name__)

    # ERROR RESPONSES
    request_method_error = {
        'connection': 'local',
        'status': 'error',
        'message': 'Error request type.'
    }

    @app.route('/', methods=['GET', 'POST'])
    def index():
        response = {
            'connection': 'local',
            'status': 'online'
        }
        if request.method == 'GET' or request.method == 'POST':
            return jsonify(response)

    # SETTING UP THE FEEDING ROUTE
    @app.route('/feed', methods=['GET', 'POST'])
    def feed():
        if request.method == 'GET' or request.method == 'POST':

            device_feed()

            response = {
                'connection': 'local',
                'status': 'success',
                'message': 'Feeding completed successfully.'
            }

            return jsonify(response)

        else:
            response = request_method_error
            return jsonify(response)

    # SETTING UP WIFI SETUP ROUTE
    @app.route('/wifisetup', methods=['GET', 'POST'])
    def wifiSetup():
        # ERROR FLAG IS SET SO THAT WPA SUPPLICANT FILE ISN'T WRITTEN DURING ERROR
        error_flag = False

        ssid = ''
        key = ''

        if request.method == 'GET':
            ssid = request.args.get('ssid')
            key = request.args.get('key')

        elif request.method == 'POST':
            ssid = request.form['ssid']
            key = request.form['key']

        else:
            response = request_method_error
            return jsonify(response)

        # CHECK IF SSID IS EMPTY OR NOT, IF EMPTY RETURN ERROR
        if str(ssid) == 'None' or ssid == '':
            response = {
                'connection': 'local',
                'status': 'error',
                'message': 'SSID can\'t be empty.'
            }
            error_flag = True

            return jsonify(response)

        # CHECK IF KEY IS EMPTY OR NOT, IF EMPTY SET PASSWORD FLAG TRUE
        if str(key) == 'None' or key == '':
            password_flag = False
        else:
            password_flag = True

        # IF NO ERROR OPEN THE WPA SUPPLICANT FILE AND ADD THE WIFI NETWORK
        if error_flag is False:
            # CHANGE DIRECTORY TO /etc/wpa_supplicant WHERE THE SUPPLICANT FILE IS PLACED
            os.chdir('/etc/wpa_supplicant')
            wpa_file = open("wpa_supplicant.conf", 'a')

            print(wpa_file)

            # IF PASSWORD IS NONE key_mgmt IS SET TO NONE
            if password_flag is True:
                new_network = """
network={
	ssid=\"%s\"
	psk=\"%s\"
}
				""" % (ssid, key)
            else:
                new_network = """
network={
	ssid=\"%s\"
	key_mgmt=none
}
				""" % (ssid)

            try:
                wpa_file.write(new_network)
                wpa_file.close()

                response = {
                    'connection': 'local',
                    'status': 'success',
                    'message': 'WIFI set successfully. Please restart device.'
                }

                return jsonify(response)

            except:
                response = {
                    'connection': 'local',
                    'status': 'error',
                    'message': 'There was an error trying to add wifi.'
                }

                return jsonify(response)

    @app.route('/delete/wifi')
    def deleteWifi():
        os.chdir('/etc/wpa_supplicant/')
        # os.chdir('/var/petfeed/')
        wpa_file = open("wpa_supplicant.conf", 'w')

        default_wpa = """
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
ap_scan=1
update_config=1

network={
        ssid=\"PetFeed\"
        psk=\"petfeed123\"
        priority=1
}

        """
        wpa_file.write(default_wpa)
        wpa_file.close()
        response = {
            'connection': 'local',
            'status': 'success',
            'message': 'WIFI set to default.'
        }

        return jsonify(response)

    @app.route('/set/user', methods=['GET', 'POST'])
    def setupUser():

        if request.method == 'GET':
            email = request.args.get('email')
            if email is None:
                return {
                    'status': 'error',
                    'message': 'email field is required'
                }
        elif request.method == 'post':
            email = (request.form['email'])
            if email is None:
                return {
                    'status': 'error',
                    'message': 'email field is required'
                }
        else:
            response = request_method_error
            return jsonify(response)

        with connection.cursor() as cursor:

            try:
                query = "DROP FROM users"
                cursor.execute(query)

                query = "DROP FROM schedules"
                cursor.execute(query)

                query = "INSERT INTO users(email) VALUES('%s')"
                cursor.execute(query, email)
                connection.commit()

                response = {
                    'connection': 'local',
                    'status': 'success',
                    'message': 'User registered to the device successfully.'
                }

                return jsonify(response)

            except:
                connection.rollback()

                response = {
                    'connection': 'local',
                    'status': 'error',
                    'message': 'There was an error trying to register user to the device.'
                }

                return jsonify(response)

    @app.route('/restart')
    def restart():
        os.system("sudo reboot")

    @app.route('/shutdown')
    def shutdown():
        os.system("sudo poweroff")

    app.run('0.0.0.0', 80)
##########################################################


##########################################################
# PUSHER SERVER THREAD FUNCTION
def pusher_server():
    # SETTING THE CHANNEL AND EVENT TO TRIGGER EACH TIME
    event = 'App\Events\eventTrigger'
    channel = 'petfeed'

    # THE CALLBACK FUNCTION THAT WILL RUN AFTER EACH TRIGGER
    def callback_function(data):
        data = ast.literal_eval(data)

        # IF THE KEY GET HAS STATUS RETURN THE STATUS OF DEVICE
        if 'get' in data.keys():
            with connection.cursor() as cursor:
                query = "SELECT DISTINCT id, email FROM users WHERE email=%s"
                try:
                    cursor.execute(query, data['user'])
                    user = cursor.fetchone()


                except:
                    user = None

            if user is not None:

                if data['get'] == 'status':

                    pusherEvent.trigger(channel, event, {
                        'connection': 'global',
                        'user': user['email'],
                        'message': 'Device is running perfectly fine.',
                        'status': 'online'
                    })

                elif data['get'] == 'schedule':

                    with connection.cursor() as cursor:
                        try:
                            query = "SELECT * FROM schedules WHERE user_id=%s"

                            cursor.execute(query, user['id'])
                            schedules_result = cursor.fetchall()
                            schedules = []

                            for s in schedules_result:
                                scheduled_day = s['day']
                                scheduled_time = datetime.strftime(s['time'], "%H:%M")

                                schedules.append({
                                    "day": scheduled_day,
                                    "time": scheduled_time
                                })

                            pusherEvent.trigger(channel, event, {
                                'connection': 'global',
                                'user': user['email'],
                                'data': schedules,
                                'status': 'Success'
                            })

                        except:
                            schedules = []

                            pusherEvent.trigger(channel, event, {
                                'connection': 'global',
                                'user': user['email'],
                                'data': schedules,
                                'status': 'error',
                                'message': 'Could not find schedules for specified user. (Schedules not set yet)'
                            })

                elif data['get'] == 'restart':
                    pusherEvent.trigger(channel, event, {
                        'connection': 'global',
                        'user': user['email'],
                        'status': 'restarting',
                        'message': 'Restarting your device.'
                    })
                    os.system('sudo restart')

                elif data['get'] == 'shutdown':
                    pusherEvent.trigger(channel, event, {
                        'connection': 'global',
                        'user': user['email'],
                        'status': 'shuttingdown',
                        'message': 'Shutting down your device.'
                    })
                    os.system('sudo shutdown')

                else:
                    pusherEvent.trigger(channel, event, {
                        'connection': 'global',
                        'status': 'error',
                        'message': 'invalid get'
                    })

            else:
                pusherEvent.trigger(channel, event, {
                    'status': 'error',
                    'message': 'No device bound to the specified user.'
                })

        # IF THE KEY FEED HAS THE VALUE FEED, FEED THE PET AND RETURN THE STATUS
        elif 'feed' in data.keys():

            try:
                user = data['user']

                with connection.cursor() as cursor:
                    query = "SELECT DISTINCT id, email FROM users WHERE email=%s"
                    cursor.execute(query, user)

                    user_result = cursor.fetchone()

                    if user_result is None:
                        pusherEvent.trigger(channel, event, {
                            'connection': 'global',
                            'status': 'error',
                            'message': 'Specified user not registered to the device.'
                        })

                    else:
                        if data['feed'] == 'treat':
                            pusherEvent.trigger(channel, event, {
                                'connection': 'global',
                                'status': 'online',
                                'user': user_result['email'],
                                'message': 'Feeding your pet, please wait.'
                            })
                            device_feed()
                            pusherEvent.trigger(channel, event, {
                                'connection': 'global',
                                'status': 'online',
                                'user': user_result['email'],
                                'message': 'Feeding completed successfully.'
                            })
                        else:
                            pusherEvent.trigger(channel, event, {
                                'connection': 'global',
                                'status': 'error',
                                'message': 'invalid value for feed:[]'
                            })

            except:
                pusherEvent.trigger(channel, event, {
                    'connection': 'global',
                    'status': 'error',
                    'message': 'The user field isn\'t set'
                })

        elif 'set' in data.keys():
            if data['set'] == 'schedule':
                try:
                    user = data['user']

                    with connection.cursor() as cursor:

                        query = "SELECT DISTINCT id, email FROM users WHERE email=%s"
                        cursor.execute(query, user)
                        user_result = cursor.fetchone()

                        if len(user_result) <= 0:
                            pusherEvent.trigger(channel, event, {
                                'connection': 'global',
                                'status': 'error',
                                'message': 'Specified user not registered to the device.'
                            })

                        else:
                            if len(data['data']) > 0:
                                for schedule in data['data']:
                                    day = schedule['day']
                                    feed_time = schedule['time']
                                    feed_time = datetime.strptime(feed_time, "%H:%M")

                                    sql = "INSERT INTO schedules (day, time, user_id) VALUES (%s, %s, %s)"
                                    cursor.execute(sql, (day, feed_time, user_result['id']))
                                connection.commit()

                                pusherEvent.trigger(channel, event, {
                                    'connection': 'global',
                                    'status': 'success',
                                    'message': 'Your schedule was added successfully.'
                                })
                            else:
                                pusherEvent.trigger(channel, event, {
                                    'connection': 'global',
                                    'status': 'error',
                                    'message': 'Empty data recieved.'
                                })

                except:
                    with connection.cursor as cursor:
                        cursor.rollback()

                    pusherEvent.trigger(channel, event, {
                        'connection': 'global',
                        'status': 'error',
                        'message': 'Internal error occurred while adding schedule'
                    })

            elif data['schedule'] == 'update':

                with connection.cursor() as cursor:
                    try:
                        user = data['user']

                        query = "SELECT DISTINCT id, email FROM users WHERE email=%s"
                        cursor.execute(query, user)
                        user_result = cursor.fetchone()

                        if user_result is None:
                            pusherEvent.trigger(channel, event, {
                                'connection': 'global',
                                'status': 'error',
                                'message': 'Specified user not registered to the device.'
                            })

                        else:
                            query = "DELETE FROM schedules"
                            cursor.execute(query)

                            for schedule in data['data']:
                                day = schedule['day']
                                feed_time = schedule['time']
                                feed_time = datetime.strptime(feed_time, "%H:%M")

                                sql = "INSERT INTO schedules (day, time, user_id) VALUES (%s, %s, %s)"
                                cursor.execute(sql, (day, feed_time, user_result['id']))

                            connection.commit()

                            pusherEvent.trigger(channel, event, {
                                'connection': 'global',
                                'status': 'success',
                                'message': 'Your schedule was updated successfully.'
                            })

                    except:
                        connection.rollback()

                    pusherEvent.trigger(channel, event, {
                        'connection': 'global',
                        'status': 'error',
                        'message': 'Internal error occurred while updating schedule'
                    })


    def connect_handler(data):
        petfeed_channel = pusherClient.subscribe(channel)
        petfeed_channel.bind(event, callback_function)

    pusherClient = PusherClient.Pusher(key='0053280ec440a78036bc', secret='7bbae18dfe3989d432a6')
    pusherClient.connection.bind('pusher:connection_established', connect_handler)
    pusherClient.connect()

    pusherEvent = PusherEvent(app_id="440480", key="0053280ec440a78036bc", secret="7bbae18dfe3989d432a6",
                              cluster="mt1")

    while True:
        time.sleep(1)

##########################################################


##########################################################
# THREAD THAT RUNS SCHEDULING TASKS
# NEED TO ADD LOGIC WHICH RUNS THE DEVICE ON SCHEDULE
def scheduled_task():

    channel = "petfeed"
    event = "Need to add one later"

    with connection.cursor() as cursor:
        pusherEvent = PusherEvent(app_id="440480", key="0053280ec440a78036bc",
                                  secret="7bbae18dfe3989d432a6", cluster="mt1")
        try:
            today_day = datetime.now().strftime("%A")
            today_time = datetime.now().strftime("%H:%M:%S")

            query = "SELECT * FROM schedules WHERE day=%s AND time=%s"
            cursor.execute(query, today_day, today_time)

            schedules = cursor.fetchall()

            if len(schedules) > 0:
                for schedule in schedules:
                    scheduled_time = schedule['time'].strftime('%H:%M:%S')

                    # CALL THE DEVICE FEED FUNCTION THAT CONTROLS THE PI SERVO
                    device_feed()
                    user_id = schedule['user_id']

                    query = "SELECT DISTINCT email, id FROM users WHERE id = '%s'"
                    cursor.execute(query, user_id)

                    user = cursor.fetchone()

                    pusherEvent.trigger(channel, event, {
                        'user': user['email'],
                        'status': 'success',
                        'data': {
                            'feeding_date': scheduled_time,
                            'user': user['email'],
                        }
                    })

        except:
            pusherEvent.trigger(channel, event, {
                'connection': 'global',
                'status': 'error',
                'message': 'Internal error occurred while adding schedule'
            })


##########################################################


##########################################################
# MAIN SCRIPT RUNS HERE
if __name__ == '__main__':
    flask_thread = Thread(target=flask_server)
    flask_thread.start()
    pusher_thread = Thread(target=pusher_server)
    pusher_thread.start()
    pusher_thread.join()
    flask_thread.join()

    signal.signal(signal.SIGTERM, pwm.cleanup())
##########################################################


