from flask import Flask, render_template, request, redirect, url_for, flash , session
import mysql.connector
from mysql.connector import Error
from datetime import datetime

app = Flask(__name__)
app.secret_key = "adbms_demo_secret_2025"

# ---------- DATABASE CONFIG ----------
DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = "root"         
DB_AIRPORT = "Airport_Management"
DB_LOGIN = "airportdb"       

import mysql.connector

connection = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="Airport_Management"
)


def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",       
        database="Airport_Management"
        
    )


# helper: airport DB connection
def airport_conn():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_AIRPORT,
        autocommit=True
    )


# helper: login DB connection (for authentication)
def login_conn():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_LOGIN
    )

# ---------- AUTH ----------
@app.route('/')
def home_redirect():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')

        try:
            conn = mysql.connector.connect(
                host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_LOGIN
            )
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT * FROM users 
                WHERE username=%s AND password=%s AND role=%s
            """, (username, password, role))
            user = cursor.fetchone()
            conn.close()

            if user:
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']

                if role == 'admin':
                    return redirect(url_for('admin_dashboard'))
                elif role == 'passenger':
                    return redirect(url_for('passenger_dashboard'))
            else:
                return render_template('login.html', error="Invalid credentials. Try again.")
        except mysql.connector.Error as e:
            return render_template('login.html', error=f"Database error: {e}")

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash("You’ve been logged out successfully!", "info")
    return redirect(url_for('login'))


# --------------------------
# ADMIN DASHBOARD
# --------------------------
@app.route('/admin_dashboard')
def admin():   # <-- fixed name to match url_for('admin_dashboard')
    if 'role' not in session or session['role'] != 'admin':
        flash("Unauthorized access!", "danger")
        return redirect(url_for('login'))
    return render_template('admin.html', username=session.get('username'))


# --------------------------
# PASSENGER DASHBOARD
# --------------------------
@app.route('/passenger_dashboard')
def passenger_dashboard():
    if 'role' not in session or session['role'] != 'passenger':
        flash("Unauthorized access!", "danger")
        return redirect(url_for('login'))
    return render_template('passenger_dashboard.html', username=session.get('username'))


# --------------------------
# Passenger: View Bookings
# --------------------------
@app.route('/passenger/bookings', methods=['GET', 'POST'])
def passenger_bookings():
    if session.get('role') != 'passenger':
        flash("Unauthorized access!", "danger")
        return redirect(url_for('login'))

    results = []
    query_done = False
    error = None

    if request.method == 'POST':
        # Fetch what user entered
        search_type = request.form.get('search_type')  # passenger_id / booking_id / flight_id
        search_value = request.form.get('search_value', '').strip()

        if not search_type or not search_value:
            error = "Please choose a search type and enter an ID."
        else:
            try:
                conn = airport_conn()
                cur = conn.cursor(dictionary=True)

                if search_type == 'passenger_id':
                    cur.execute("""
                        SELECT b.Booking_ID, b.Passenger_ID, b.Flight_ID, b.Class, b.Price, b.SeatNo, b.Booking_Date,
                               f.Departure_Airport, f.Arrival_Airport, f.Departure_Time
                        FROM Booking b
                        LEFT JOIN Flight f ON b.Flight_ID = f.Flight_ID
                        WHERE b.Passenger_ID = %s
                        ORDER BY b.Booking_Date DESC
                    """, (search_value,))

                elif search_type == 'booking_id':
                    cur.execute("""
                        SELECT b.Booking_ID, b.Passenger_ID, b.Flight_ID, b.Class, b.Price, b.SeatNo, b.Booking_Date,
                               f.Departure_Airport, f.Arrival_Airport, f.Departure_Time
                        FROM Booking b
                        LEFT JOIN Flight f ON b.Flight_ID = f.Flight_ID
                        WHERE b.Booking_ID = %s
                    """, (search_value,))

                elif search_type == 'flight_id':
                    cur.execute("""
                        SELECT b.Booking_ID, b.Passenger_ID, b.Flight_ID, b.Class, b.Price, b.SeatNo, b.Booking_Date,
                               f.Departure_Airport, f.Arrival_Airport, f.Departure_Time
                        FROM Booking b
                        LEFT JOIN Flight f ON b.Flight_ID = f.Flight_ID
                        WHERE b.Flight_ID = %s
                        ORDER BY b.Booking_Date DESC
                    """, (search_value,))

                results = cur.fetchall()
                query_done = True

            except Exception as e:
                error = f"Error fetching bookings: {e}"
            finally:
                try:
                    cur.close()
                    conn.close()
                except:
                    pass

    return render_template('passenger_bookings.html',
                           results=results,
                           query_done=query_done,
                           error=error,
                           username=session.get('username'))


@app.route('/feedback', methods=['GET','POST'])
def feedback():
    # passenger-only
    if session.get('role') != 'passenger':
        flash("Unauthorized access!", "danger")
        return redirect(url_for('login'))

    msg = None
    err = None

    # Try to locate passenger_id using session username (best-effort)
    passenger_id = None
    try:
        conn = airport_conn()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT Passenger_ID FROM Passenger WHERE Name = %s LIMIT 1", (session.get('username'),))
        row = cur.fetchone()
        if row:
            passenger_id = row.get('Passenger_ID')
    except Exception as e:
        # don't crash the page — we'll allow manual entry if lookup fails
        err = f"Lookup warning: {e}"
    finally:
        try: cur.close(); conn.close()
        except: pass

    if request.method == 'POST':
        # Allow passenger to enter their id manually if lookup failed or they prefer:
        form_pid = request.form.get('passenger_id', '').strip()
        chosen_pid = None
        if form_pid:
            # validate numeric
            if not form_pid.isdigit():
                flash("Passenger ID must be a number.", "danger")
                return redirect(url_for('feedback'))
            chosen_pid = int(form_pid)
        elif passenger_id:
            chosen_pid = passenger_id
        else:
            flash("Could not find your Passenger_ID automatically — please enter your Passenger ID.", "warning")
            return redirect(url_for('feedback'))

        comment = request.form.get('comment','').strip()
        rating = request.form.get('rating','').strip()

        if not comment or not rating:
            flash("Please provide both comment and rating.", "danger")
            return redirect(url_for('feedback'))

        try:
            # compute next Feedback_ID (you said schema doesn't use AUTO_INCREMENT)
            conn = airport_conn()
            cur = conn.cursor()
            cur.execute("SELECT COALESCE(MAX(Feedback_ID), 0) + 1 AS next_id FROM Feedback")
            next_id = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO Feedback (Feedback_ID, Passenger_ID, Comment, Rating, Feedback_Date)
                VALUES (%s, %s, %s, %s, CURDATE())
            """, (next_id, chosen_pid, comment, rating))
            conn.commit()
            flash("Feedback submitted. Thank you!", "success")
        except Exception as e:
            flash(f"Error submitting feedback: {e}", "danger")
        finally:
            try: cur.close(); conn.close()
            except: pass

        return redirect(url_for('feedback'))

    # GET -> render form. show previous feedbacks if we have passenger_id
    previous = []
    try:
        if passenger_id:
            conn = airport_conn()
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT Feedback_ID, Comment, Rating, Feedback_Date FROM Feedback WHERE Passenger_ID=%s ORDER BY Feedback_Date DESC", (passenger_id,))
            previous = cur.fetchall()
    except:
        previous = []
    finally:
        try: cur.close(); conn.close()
        except: pass

    return render_template('feedback_form.html',
                           message=msg,
                           error=err,
                           previous=previous,
                           detected_passenger_id=passenger_id,
                           username=session.get('username'))



@app.route('/admin')
def admin_dashboard():
    try:
        conn = airport_conn()
        cur = conn.cursor(dictionary=True)

        # Flights
        cur.execute("SELECT * FROM Flight ORDER BY Departure_Time DESC LIMIT 10;")
        flights = cur.fetchall()

        # Bookings
        cur.execute("SELECT * FROM Booking ORDER BY Booking_Date DESC LIMIT 10;")
        bookings = cur.fetchall()

        # Passengers
        cur.execute("SELECT * FROM Passenger ORDER BY Passenger_ID DESC LIMIT 10;")
        passengers = cur.fetchall()

        # Staff
        try:
            cur.execute("SELECT * FROM Staff ORDER BY Staff_ID DESC LIMIT 5;")
            staff = cur.fetchall()
        except:
            staff = []

        # Emergencies
        try:
            cur.execute("SELECT * FROM Emergency ORDER BY Emergency_ID DESC LIMIT 5;")
            emergencies = cur.fetchall()
        except:
            emergencies = []

        # Counts
        cur.execute("SELECT COUNT(*) AS cnt FROM Flight;")
        flights_cnt = cur.fetchone()['cnt']
        cur.execute("SELECT COUNT(*) AS cnt FROM Booking;")
        bookings_cnt = cur.fetchone()['cnt']
        cur.execute("SELECT COUNT(*) AS cnt FROM Passenger;")
        passengers_cnt = cur.fetchone()['cnt']
        cur.execute("SELECT COUNT(*) AS cnt FROM Staff;")
        staff_cnt = cur.fetchone()['cnt']
        cur.execute("SELECT COUNT(*) AS cnt FROM Emergency;")
        emergency_cnt = cur.fetchone()['cnt']
        cur.execute("SELECT COUNT(*) AS unresolved_count FROM Emergency WHERE Resolution_Status != 'Resolved'")
        unresolved_count = cur.fetchone()['unresolved_count']

        cur.close(); conn.close()
    except Error as e:
        flash(f"Database error: {e}", "error")
        flights = bookings = passengers = staff = emergencies = []
        flights_cnt = bookings_cnt = passengers_cnt = staff_cnt = emergency_cnt = 0

    return render_template(
        'admin.html',
        flights=flights,
        bookings=bookings,
        passengers=passengers,
        staff=staff,
        emergencies=emergencies,
        flights_cnt=flights_cnt,
        bookings_cnt=bookings_cnt,
        passengers_cnt=passengers_cnt,
        unresolved_count=unresolved_count,
        staff_cnt=staff_cnt,
        emergency_cnt=emergency_cnt
    )









# ---------- FULL LIST PAGES ----------
@app.route('/flights')
def flights_page():
    try:
        conn = airport_conn()
        cur = conn.cursor(dictionary=True)
        

        cur.execute("SELECT * FROM Flight ORDER BY Departure_Time DESC;")
        flights = cur.fetchall()
        cur.close(); conn.close()
    except Error as e:
        flash(f"DB error: {e}", "error")
        flights = []
    return render_template("admin_flight.html", flights=flights)


@app.route('/bookings')
def bookings_page():
    try:
        conn = airport_conn()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM Booking ORDER BY Booking_Date DESC;")
        bookings = cur.fetchall()
        cur.close(); conn.close()
    except Error as e:
        flash(f"DB error: {e}", "error")
        bookings = []
    return render_template('admin_booking.html', bookings=bookings)



@app.route('/emergencies')
def emergencies_page():
    emergencies = []        # Always defined
    unresolved_count = 0    # Always defined
    conn = None
    cur = None

    try:
        conn = airport_conn()
        if conn.is_connected():
            cur = conn.cursor(dictionary=True)

            # Fetch all emergencies
            cur.execute("SELECT * FROM Emergency ORDER BY Emergency_ID DESC;")
            emergencies = cur.fetchall()

            # Count unresolved emergencies
            cur.execute("SELECT COUNT(*) AS count FROM Emergency WHERE Resolution_Status != 'Resolved';")
            unresolved_count = cur.fetchone()['count']

    except Error as e:
        flash(f"DB error: {e}", "error")

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return render_template('admin_emergency.html', emergencies=emergencies, unresolved_count=unresolved_count)




@app.route('/feedbacks')
def feedbacks_page():
    try:
        conn = airport_conn()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT f.*, p.Name as PassengerName FROM Feedback f LEFT JOIN Passenger p ON f.Passenger_ID = p.Passenger_ID ORDER BY f.Feedback_ID DESC;")
        feedbacks = cur.fetchall()
        cur.close(); conn.close()
    except Error as e:
        flash(f"DB error: {e}", "error")
        feedbacks = []
    return render_template('feedbacks.html', feedbacks=feedbacks)

# ---------- ADD PASSENGER ----------
@app.route('/passenger/add', methods=['POST'])
def passenger_add():
   
    name = request.form.get('name')
    gender = request.form.get('gender')
    dob = request.form.get('date_of_birth')  
    contact = request.form.get('contact')
    nationality = request.form.get('nationality')
    passport_no = request.form.get('passport_no')
    flight_id = request.form.get('flight_id') or None

    # Compute Age from DOB if provided
    age = None
    if dob:
        try:
            d = datetime.strptime(dob, "%Y-%m-%d").date()
            today = datetime.today().date()
            age = today.year - d.year - ((today.month, today.day) < (d.month, d.day))
        except Exception:
            age = None

    try:
        conn = airport_conn()
        cur = conn.cursor()

       
        try:
            cur.execute("""
                INSERT INTO Passenger (Name, Age, Contact, Nationality, Passport_No, Date_of_Birth, Gender)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (name, age, contact, nationality, passport_no, dob, gender))
            conn.commit()
            cur.close()
            conn.close()
        except mysql.connector.Error as e_inner:
          
            cur.execute("SELECT COALESCE(MAX(Passenger_ID),0) + 1 AS next_id FROM Passenger;")
            next_id = cur.fetchone()[0]
            cur.execute("""
                INSERT INTO Passenger (Passenger_ID, Name, Age, Contact, Nationality, Passport_No, Date_of_Birth, Gender)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (next_id, name, age, contact, nationality, passport_no, dob, gender))
            conn.commit()

        
        cur.close(); conn.close()
        flash("Passenger added successfully.", "success")
    except Error as e:
        flash(f"Error adding passenger: {e}", "error")
    return redirect(url_for('admin_dashboard'))

# ---------- ADD FLIGHT ----------
@app.route('/flight/add', methods=['POST'])
def flight_add():
    flight_id = request.form.get('Flight_ID')
    departure_airport = request.form.get('Departure_Airport') or request.form.get('origin')
    arrival_airport = request.form.get('Arrival_Airport') or request.form.get('destination')
    departure_time = request.form.get('Departure_Time')
    arrival_time = request.form.get('Arrival_Time')
    status = request.form.get('status') or request.form.get('Flight_Status')
    

    try:
        conn = airport_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO Flight (Flight_ID, Departure_Airport, Arrival_Airport, Departure_Time, Arrival_Time, Flight_Status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (flight_id, departure_airport, arrival_airport, departure_time, arrival_time, status))

        conn.commit()
        cur.close()
        conn.close()
        flash("Flight added successfully.", "success")
    except Error as e:
        flash(f"Error adding flight: {e}", "error")
    return redirect(url_for('admin_dashboard'))


@app.route('/admin_passengers')
def admin_passengers_page():
    try:
        conn = airport_conn()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM Passenger ORDER BY Passenger_ID;")
        passengers = cur.fetchall()
        cur.close(); conn.close()
    except Error as e:
        flash(f"Error loading passengers: {e}", "error")
        passengers = []
    return render_template('admin_passenger.html', passengers=passengers)


@app.route('/passenger_update/<int:pid>', methods=['GET', 'POST'])
def passenger_update(pid):
    conn = airport_conn()
    cur = conn.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form.get('name')
        nationality = request.form.get('nationality')
        contact = request.form.get('contact')
        gender = request.form.get('gender')
        dob = request.form.get('date_of_birth')
        passport_no = request.form.get('passport_no')

        try:
            cur.execute("""
                UPDATE Passenger 
                SET Name=%s, Nationality=%s, Contact=%s, Gender=%s, Date_of_Birth=%s, Passport_No=%s
                WHERE Passenger_ID=%s
            """, (name, nationality, contact, gender, dob, passport_no, pid))
            conn.commit()
            flash("✅ Passenger updated successfully!", "success")

        except mysql.connector.IntegrityError as e:
            flash(f"⚠️ Integrity Error: {str(e)}", "error")

        except Exception as e:
            flash(f"❌ Error updating passenger: {str(e)}", "error")

        finally:
            cur.close()
            conn.close()
        
        return redirect(url_for('admin_passengers_page'))

    # GET — display existing record for editing
    try:
        cur.execute("SELECT * FROM Passenger WHERE Passenger_ID=%s", (pid,))
        passenger = cur.fetchone()
        if not passenger:
            flash("⚠️ Passenger not found!", "error")
            return redirect(url_for('admin_passengers_page'))
    except Exception as e:
        flash(f"❌ Error fetching passenger: {str(e)}", "error")
        passenger = None
    finally:
        cur.close()
        conn.close()

    return render_template('passenger_edit.html', passenger=passenger)





@app.route('/passenger_delete/<int:pid>')
def passenger_delete(pid):
    try:
        conn = airport_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM Passenger WHERE Passenger_ID=%s", (pid,))
        conn.commit()
        cur.close(); conn.close()
        flash("Passenger deleted successfully!", "success")
    except Error as e:
        flash(f"Error deleting passenger: {e}", "error")
    return redirect(url_for('admin_passengers_page'))

# ---------- ADMIN FLIGHTS ----------
@app.route('/admin_flights')
def admin_flights_page():
    try:
        conn = airport_conn()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM Flight ORDER BY Flight_ID;")
        flights = cur.fetchall()
        cur.close(); conn.close()
    except Error as e:
        flash(f"Error loading flights: {e}", "error")
        flights = []
    return render_template('admin_flight.html', flights=flights)


@app.route('/flight_update/<string:fid>', methods=['GET', 'POST'])
def flight_update(fid):
    conn = airport_conn()
    cur = conn.cursor(dictionary=True)
    if request.method == 'POST':
        departure_airport = request.form.get('departure_airport')
        arrival_airport = request.form.get('arrival_airport')
        departure_time = request.form.get('departure_time')
        arrival_time = request.form.get('arrival_time')
        status = request.form.get('status')
        try:
            cur.execute("""
                UPDATE Flight
                SET Departure_Airport=%s, Arrival_Airport=%s, 
                    Departure_Time=%s, Arrival_Time=%s, Flight_Status=%s
                WHERE Flight_ID=%s
            """, (departure_airport, arrival_airport, departure_time, arrival_time, status, fid))
            conn.commit()
            flash("Flight updated successfully!", "success")
        except Error as e:
            conn.rollback()
            flash(f"Error updating flight: {e}", "error")
        cur.close(); conn.close()
        return redirect(url_for('admin_flights_page'))

    cur.execute("SELECT * FROM Flight WHERE Flight_ID=%s", (fid,))
    flight = cur.fetchone()
    cur.close(); conn.close()
    return render_template('flight_edit.html', flight=flight)


@app.route('/flight_delete/<string:fid>')
def flight_delete(fid):
    try:
        conn = airport_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM Flight WHERE Flight_ID=%s", (fid,))
        conn.commit()
        flash("Flight deleted successfully!", "success")
        cur.close(); conn.close()
    except Error as e:
        flash(f"Error deleting flight: {e}", "error")
    return redirect(url_for('admin_flights_page'))


@app.route('/admin_bookings')
def admin_bookings_page():
    try:
        conn = airport_conn()
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT 
                b.Booking_ID, b.Passenger_ID, b.Flight_ID,
                b.Class, b.Price, b.Booking_status, b.SeatNo, b.Booking_Date,
                p.Name AS PassengerName,
                f.Departure_Airport, f.Arrival_Airport
            FROM Booking b
            LEFT JOIN Passenger p ON b.Passenger_ID = p.Passenger_ID
            LEFT JOIN Flight f ON b.Flight_ID = f.Flight_ID
            ORDER BY b.Booking_ID;
        """)
        bookings = cur.fetchall()
        cur.close(); conn.close()
    except Error as e:
        flash(f"Error loading bookings: {e}", "error")
        bookings = []
    return render_template('admin_booking.html', bookings=bookings)

from datetime import date

from datetime import date

@app.route('/add_booking', methods=['POST'])
def add_booking():
    try:
        # Get form values using the same lowercase names as in HTML
        Booking_ID = request.form['booking_id']
        Passenger_ID = request.form['passenger_id']
        Flight_ID = request.form['flight_id']
        Class=request.form['class']
        SeatNo = request.form.get('seatno')
        Price = request.form.get('price', 0)
        Booking_Date = request.form.get('Booking_Date', str(date.today()))  # fallback to today

        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
        )
        cursor = conn.cursor()
        cursor.execute("""
    INSERT INTO Booking (Booking_ID, Passenger_ID, Flight_ID,Class ,SeatNo, Price, Booking_Date)
    VALUES (%s, %s, %s,%s, %s, %s, %s)
""", (Booking_ID, Passenger_ID, Flight_ID,Class, SeatNo, Price, Booking_Date))

        conn.commit()
        conn.close()
        flash("Booking added successfully!", "success")
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        flash(f"Error adding booking: {e}", "danger")
        return redirect(url_for('admin_dashboard'))




# ---------- UPDATE BOOKING ----------
@app.route('/booking_update/<int:bid>', methods=['GET', 'POST'])
def booking_update(bid):
    conn = airport_conn()
    cur = conn.cursor(dictionary=True)

    if request.method == 'POST':
        seat_class = request.form.get('class')
        price = request.form.get('price')
        booking_status = request.form.get('booking_status')
        seat_no = request.form.get('seat_no')
        booking_date = request.form.get('booking_date')
        passenger_id = request.form.get('passenger_id')
        flight_id = request.form.get('flight_id')

        try:
            cur.execute("""
                UPDATE Booking 
                SET Class=%s, Price=%s, Booking_status=%s, SeatNo=%s, 
                    Booking_Date=%s, Passenger_ID=%s, Flight_ID=%s
                WHERE Booking_ID=%s
            """, (seat_class, price, booking_status, seat_no,
                  booking_date, passenger_id, flight_id, bid))
            conn.commit()
            flash("Booking updated successfully!", "success")
        except Error as e:
            conn.rollback()
            flash(f"Error updating booking: {e}", "error")

        cur.close()
        conn.close()
        return redirect(url_for('admin_bookings_page'))

    # Fetch booking for the edit form
    cur.execute("""
        SELECT Booking_ID, Passenger_ID, Flight_ID, Class, Price, 
               Booking_status, SeatNo, Booking_Date
        FROM Booking WHERE Booking_ID=%s
    """, (bid,))
    booking = cur.fetchone()
    cur.close()
    conn.close()

    return render_template('booking_edit.html', booking=booking)



# ---------- DELETE BOOKING ----------
@app.route('/booking_delete/<int:bid>')
def booking_delete(bid):
    try:
        conn = airport_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM Booking WHERE Booking_ID=%s", (bid,))
        conn.commit()
        flash("Booking deleted successfully!", "success")
        cur.close(); conn.close()
    except Error as e:
        flash(f"Error deleting booking: {e}", "error")
    return redirect(url_for('admin_bookings_page'))


# ---------- ADD BOOKING ----------
@app.route('/booking/add', methods=['POST'])
def booking_add():
    passenger_id = request.form.get('passenger_id')
    flight_id = request.form.get('flight_id')
    seat_class = request.form.get('class') or request.form.get('seat_class')
    price = request.form.get('price')
    seat_no = request.form.get('seat_no') or None
    booking_status = request.form.get('booking_status') or "Confirmed"
    booking_date = request.form.get('booking_date') or None

    try:
        conn = airport_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO Booking (Class, Price, Booking_status, SeatNo, Booking_Date, Passenger_ID, Flight_ID)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (seat_class, price, booking_status, seat_no, booking_date, passenger_id, flight_id))
        conn.commit()
        cur.close(); conn.close()
        flash("Booking added successfully.", "success")
    except Error as e:
        flash(f"Error adding booking: {e}", "error")
    return redirect(url_for('admin_dashboard'))

# ---------- STAFF MANAGEMENT ----------
from datetime import date, datetime

# list + add staff
@app.route('/staff', methods=['GET', 'POST'])
def staff_page():
    conn = airport_conn()
    cur = conn.cursor(dictionary=True)

    if request.method == 'POST':
        # read form fields (names must match template)
        staff_id = request.form.get('staff_id')                    # required in form
        name = request.form.get('name')
        role = request.form.get('role')
        terminal_id = request.form.get('terminal_id')
        shift = request.form.get('shift')
        dob = request.form.get('date_of_birth')
        contact = request.form.get('contact_number')

        # validate required fields quickly
        if not (staff_id and name and role and terminal_id and dob):
            flash("Please fill required staff fields.", "error")
            # continue to render page with current data

        else:
            try:
                dob_date = datetime.strptime(dob, "%Y-%m-%d").date()
                age = date.today().year - dob_date.year - (
                    (date.today().month, date.today().day) < (dob_date.month, dob_date.day)
                )

                cur.execute("""
                    INSERT INTO Staff (Staff_ID, Name, Role, Terminal_ID, Shift, Date_of_Birth, Age, Contact_Number)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (staff_id, name, role, terminal_id, shift, dob, age, contact))
                conn.commit()
                flash("✅ Staff added successfully!", "success")
            except Exception as e:
                conn.rollback()
                flash(f"❌ Error adding staff: {e}", "error")

    # fetch and show staff list (always)
    cur.execute("SELECT * FROM Staff ORDER BY Staff_ID DESC;")
    staff = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('admin_staff.html', staff=staff)


# edit page (GET)
@app.route('/edit_staff/<int:id>', methods=['GET'])
def edit_staff(id):
    conn = airport_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM Staff WHERE Staff_ID = %s", (id,))
    staff = cur.fetchone()
    cur.close()
    conn.close()
    if not staff:
        flash("Staff record not found.", "error")
        return redirect(url_for('staff_page'))
    return render_template('staff_edit.html', staff=staff)


# update (POST)
@app.route('/update_staff/<int:id>', methods=['POST'])
def update_staff(id):
    conn = airport_conn()
    cur = conn.cursor()
    try:
        name = request.form.get('name')
        role = request.form.get('role')
        terminal_id = request.form.get('terminal_id')
        shift = request.form.get('shift')
        dob = request.form.get('date_of_birth')
        age = request.form.get('age')
        contact = request.form.get('contact_number')

        # optional: recalc age if dob present and age empty
        if dob and not age:
            dob_date = datetime.strptime(dob, "%Y-%m-%d").date()
            age = date.today().year - dob_date.year - (
                (date.today().month, date.today().day) < (dob_date.month, dob_date.day)
            )

        cur.execute("""
            UPDATE Staff
            SET Name=%s, Role=%s, Terminal_ID=%s, Shift=%s, Date_of_Birth=%s, Age=%s, Contact_Number=%s
            WHERE Staff_ID=%s
        """, (name, role, terminal_id, shift, dob, age, contact, id))
        conn.commit()
        flash("✅ Staff updated successfully!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"❌ Error updating staff: {e}", "error")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('staff_page'))


# delete
@app.route('/delete_staff/<int:id>')
def delete_staff(id):
    conn = airport_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM Staff WHERE Staff_ID = %s", (id,))
        conn.commit()
        flash("🗑️ Staff deleted successfully!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"❌ Error deleting staff: {e}", "error")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('staff_page'))






# ---------- ADMIN EMERGENCY ----------
@app.route('/admin_emergency')
def admin_emergency_page():
    emergencies = []  

    try:
        conn = airport_conn()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM Emergency ORDER BY Emergency_ID;")
        emergencies = cur.fetchall()
    except Error as e:
        flash(f"Error loading emergencies: {e}", "error")
    finally:
        if cur: cur.close()
        if conn: conn.close()

    return render_template('admin_emergency.html', emergencies=emergencies)



@app.route('/emergency_add', methods=['POST'])
def emergency_add():
    try:
        conn = airport_conn()
        cur = conn.cursor()

        data = (
            request.form['emergency_id'],
            request.form['type'],
            request.form['location'],
            request.form['response_time'],
            request.form['resolution_status'],
            request.form['reported_by']
        )

        query = """
        INSERT INTO Emergency (Emergency_ID, Type, Location, Response_Time, Resolution_Status, Reported_By)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        cur.execute(query, data)
        conn.commit()

        flash("Emergency added successfully!", "success")

    except Error as e:
        flash(f"Error adding emergency: {e}", "error")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('admin_dashboard'))




@app.route('/update_emergency/<string:emergency_id>', methods=['GET', 'POST'])
def emergency_update(emergency_id):
    conn = airport_conn()
    cur = conn.cursor(dictionary=True)

    if request.method == 'POST':
        emergency_type = request.form['type']
        location = request.form['location']
        response_time = request.form['response_time']
        resolution_status = request.form['resolution_status']
        reported_by = request.form['reported_by']

        try:
            cur.execute("""
                UPDATE Emergency 
                SET Type=%s, Location=%s, Response_Time=%s,
                    Resolution_Status=%s, Reported_By=%s
                WHERE Emergency_ID=%s
            """, (emergency_type, location, response_time, resolution_status, reported_by, emergency_id))
            conn.commit()
            flash("Emergency updated successfully!", "success")
        except Error as e:
            flash(f"Error updating emergency: {e}", "error")

        cur.close(); conn.close()
        return redirect(url_for('admin_emergency_page'))

    cur.execute("SELECT * FROM Emergency WHERE Emergency_ID=%s", (emergency_id,))
    emergency = cur.fetchone()
    cur.close(); conn.close()
    return render_template('emergency_edit.html', emergency=emergency)



@app.route('/emergency_delete/<string:emergency_id>')
def emergency_delete(emergency_id):
    try:
        conn = airport_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM Emergency WHERE Emergency_ID=%s", (emergency_id,))
        conn.commit()
        flash("Emergency record deleted successfully!", "success")
        cur.close(); conn.close()
    except Error as e:
        flash(f"Error deleting emergency: {e}", "error")
    return redirect(url_for('admin_emergency_page'))

@app.route('/baggage')
def baggage_page():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Baggage ORDER BY Baggage_ID DESC")
        baggage = cursor.fetchall()
        conn.close()
        return render_template("admin_baggage.html", baggage=baggage)
    except Exception as e:
        flash(f"Error loading baggage data: {e}", "danger")
        return redirect(url_for('admin_dashboard'))


@app.route('/baggage/add', methods=['POST'])
def add_baggage():
    try:
        Baggage_ID = request.form['baggage_id']
        Passenger_ID = request.form['passenger_id']
        Weight = request.form['weight']
        Status = request.form['status']
        Destination = request.form['destination']
        Tag_No = request.form['tag_no']

        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
        )
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Baggage (Baggage_ID, Passenger_ID, Weight, Status, Destination, Tag_No)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (Baggage_ID, Passenger_ID, Weight, Status, Destination, Tag_No))
        conn.commit()
        conn.close()
        flash("Baggage added successfully!", "success")
        return redirect(url_for('baggage_page'))
    except Exception as e:
        flash(f"Error adding baggage: {e}", "danger")
        return redirect(url_for('baggage_page'))


@app.route('/baggage/edit/<int:id>', methods=['GET', 'POST'])
def edit_baggage(id):
    conn = mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
    )
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        Weight = request.form['weight']
        Status = request.form['status']
        Destination = request.form['destination']
        cursor.execute("""
            UPDATE Baggage SET Weight=%s, Status=%s, Destination=%s WHERE Baggage_ID=%s
        """, (Weight, Status, Destination, id))
        conn.commit()
        conn.close()
        flash("Baggage updated successfully!", "success")
        return redirect(url_for('baggage_page'))

    cursor.execute("SELECT * FROM Baggage WHERE Baggage_ID = %s", (id,))
    baggage = cursor.fetchone()
    conn.close()
    return render_template("baggage_edit.html", baggage=baggage)


@app.route('/baggage/delete/<int:id>')
def delete_baggage(id):
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
        )
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Baggage WHERE Baggage_ID=%s", (id,))
        conn.commit()
        conn.close()
        flash("Baggage deleted successfully!", "info")
        return redirect(url_for('baggage_page'))
    except Exception as e:
        flash(f"Error deleting baggage: {e}", "danger")
        return redirect(url_for('baggage_page'))

@app.route('/security')
def security_page():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
    SELECT
        s.Check_ID AS Check_ID,
        s.Check_ID AS Security_ID,    -- provide both names so older templates and new ones work
        p.Name       AS Passenger_Name,
        s.Check_Date,
        s.Check_Status,
        s.Remarks
    FROM SecurityCheck s
    JOIN Passenger p ON s.Passenger_ID = p.Passenger_ID
    JOIN Flight f     ON s.Flight_ID = f.Flight_ID
    ORDER BY s.Check_ID DESC
""")

        security = cursor.fetchall()
        conn.close()
        return render_template("admin_security.html", security=security)
    except Exception as e:
        flash(f"Error loading security check data: {e}", "danger")
        return redirect(url_for('admin_dashboard'))


@app.route('/security_check/add', methods=['POST'])
def add_security_check():
    try:
        Check_ID = request.form['check_id']
        Passenger_ID = request.form['passenger_id']
        Flight_ID = request.form['flight_id']
        Check_Date = request.form['check_date']
        Check_Status = request.form['check_status']
        Remarks = request.form['remarks']

        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
        )
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO SecurityCheck (Check_ID, Passenger_ID, Flight_ID, Check_Date, Check_Status, Remarks)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (Check_ID, Passenger_ID, Flight_ID, Check_Date, Check_Status, Remarks))
        conn.commit()
        conn.close()
        flash("Security check added successfully!", "success")
        return redirect(url_for('security_page'))
    except Exception as e:
        flash(f"Error adding security check: {e}", "danger")
        return redirect(url_for('security_page'))


@app.route('/security_check/edit/<int:id>', methods=['GET', 'POST'])
def edit_security_check(id):
    conn = mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
    )
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        Check_Status = request.form['check_status']
        Remarks = request.form['remarks']
        cursor.execute("""
            UPDATE SecurityCheck 
            SET Check_Status=%s, Remarks=%s 
            WHERE Check_ID=%s
        """, (Check_Status, Remarks, id))
        conn.commit()
        conn.close()
        flash("Security check updated successfully!", "success")
        return redirect(url_for('security_page'))

    cursor.execute("SELECT * FROM SecurityCheck WHERE Check_ID = %s", (id,))
    check = cursor.fetchone()
    conn.close()
    return render_template("security_edit.html", check=check)


@app.route('/security_check/delete/<int:id>')
def delete_security_check(id):
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
        )
        cursor = conn.cursor()
        cursor.execute("DELETE FROM SecurityCheck WHERE Check_ID=%s", (id,))
        conn.commit()
        conn.close()
        flash("Security check deleted successfully!", "info")
        return redirect(url_for('security_page'))
    except Exception as e:
        flash(f"Error deleting security check: {e}", "danger")
        return redirect(url_for('security_page'))



@app.route('/vendors')
def vendors_page():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT v.*
            FROM Vendor v
            JOIN Terminal t ON v.Terminal_ID = t.Terminal_ID
            ORDER BY v.Vendor_ID DESC
        """)
        vendors = cursor.fetchall()
        
        conn.close()
        return render_template("admin_vendor.html", vendors=vendors)
    except Exception as e:
        flash(f"Error loading vendor data: {e}", "danger")
        return redirect(url_for('admin_dashboard'))
    
from datetime import date, datetime, timedelta
import mysql.connector

@app.route('/vendor')
def admin_vendor():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT v.*
            FROM Vendor v
            LEFT JOIN Terminal t ON v.Terminal_ID = t.Terminal_ID
            ORDER BY v.Vendor_ID DESC
        """)
        vendor = cursor.fetchall()

        # current date + warning date for highlighting expiring licenses
        from datetime import date, timedelta
        current_date = date.today()
        warning_date = current_date + timedelta(days=30)

        conn.close()
        return render_template(
            "admin_vendor.html",
            vendor=vendor,
            current_date=current_date,
            warning_date=warning_date
        )

    except Exception as e:
        flash(f"Error loading vendor data: {e}", "danger")
        return redirect(url_for('admin_dashboard'))





@app.route('/vendors/add', methods=['POST'])
def add_vendor():
    try:
        Vendor_ID = request.form['vendor_id']
        Vendor_Name = request.form['vendor_name']
        Service_Type = request.form['service_type']
        Terminal_ID = request.form['terminal_id']
        Contact_Number = request.form['contact_number']
        License_Expiry = request.form['license_expiry']

        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
        )
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Vendor (Vendor_ID, Vendor_Name, Service_Type, Terminal_ID, Contact_Number, License_Expiry)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (Vendor_ID, Vendor_Name, Service_Type, Terminal_ID, Contact_Number, License_Expiry))
        conn.commit()
        conn.close()
        flash("Vendor added successfully!", "success")
        return redirect(url_for('vendors_page'))
    except Exception as e:
        flash(f"Error adding vendor: {e}", "danger")
        return redirect(url_for('vendors_page'))


@app.route('/vendors/edit/<int:id>', methods=['GET', 'POST'])
def edit_vendor(id):
    conn = mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
    )
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        Vendor_Name = request.form['Vendor_Name']
        Service_Type = request.form['Service_Type']
        Terminal_ID = request.form['Terminal_ID']
        Contact_Number = request.form['Contact_Number']
        License_Expiry = request.form['License_Expiry']


        cursor.execute("""
            UPDATE Vendor 
            SET Vendor_Name=%s, Service_Type=%s, Terminal_ID=%s, Contact_Number=%s, License_Expiry=%s
            WHERE Vendor_ID=%s
        """, (Vendor_Name, Service_Type, Terminal_ID, Contact_Number, License_Expiry, id))
        conn.commit()
        conn.close()
        flash("Vendor updated successfully!", "success")
        return redirect(url_for('vendors_page'))

    cursor.execute("SELECT * FROM Vendor WHERE Vendor_ID=%s", (id,))
    vendor = cursor.fetchone()
    conn.close()
    return render_template("vendor_edit.html", vendor=vendor)


@app.route('/vendors/delete/<int:id>')
def delete_vendor(id):
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
        )
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Vendor WHERE Vendor_ID=%s", (id,))
        conn.commit()
        conn.close()
        flash("Vendor deleted successfully!", "info")
        return redirect(url_for('vendors_page'))
    except Exception as e:
        flash(f"Error deleting vendor: {e}", "danger")
        return redirect(url_for('vendors_page'))

@app.route('/admin_feedback')
def admin_feedback():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                f.Feedback_ID,
                COALESCE(p.Name, CONCAT('ID:', f.Passenger_ID)) AS PassengerName,
                f.Comment,
                f.Rating,
                f.Feedback_Date
            FROM Feedback f
            LEFT JOIN Passenger p ON f.Passenger_ID = p.Passenger_ID
            ORDER BY f.Feedback_Date DESC
        """)
        feedbacks = cursor.fetchall()
        conn.close()
        return render_template("admin_feedback.html", feedbacks=feedbacks)
    except Exception as e:
        flash(f"Error loading feedback data: {e}", "danger")
        return redirect(url_for('admin_dashboard'))




@app.route('/feedback/delete/<int:id>')
def delete_feedback(id):
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
        )
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Feedback WHERE Feedback_ID=%s", (id,))
        conn.commit()
        conn.close()
        flash("Feedback deleted successfully!", "info")
        return redirect(url_for('admin_feedback'))
    except Exception as e:
        flash(f"Error deleting feedback: {e}", "danger")
        return redirect(url_for('admin_feedback'))
 
 # ---------------- TERMINAL MANAGEMENT ----------------

@app.route('/admin/terminals')
def admin_terminals():
    conn = airport_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM Terminal")
    terminals = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('admin_terminal.html', terminals=terminals)

@app.route('/add_terminal', methods=['POST'])
def add_terminal():
    try:
        terminal_id = request.form.get('terminal_id')
        name = request.form.get('name')
        facility = request.form.get('facility')
        capacity = request.form.get('capacity')

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO Airport_Management.Terminal (Terminal_ID, Name, Facility, Capacity)
            VALUES (%s, %s, %s, %s)
        """, (terminal_id, name, facility, capacity))
        conn.commit()
        cur.close(); conn.close()
        flash("Terminal added successfully!", "success")
        return redirect(url_for('admin_terminals'))

    except Error as e:
        flash(f"Error adding terminal: {e}", "error")
        return redirect(url_for('admin_terminals'))


@app.route('/terminal_edit/<int:terminal_id>', methods=['GET', 'POST'])
def edit_terminal(terminal_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        if request.method == 'POST':
            name = request.form['name']
            facility = request.form['facility']
            capacity = request.form['capacity']
            cur.execute("""
                UPDATE Airport_Management.Terminal 
                SET Name=%s, Facility=%s, Capacity=%s 
                WHERE Terminal_ID=%s
            """, (name, facility, capacity, terminal_id))
            conn.commit()
            cur.close(); conn.close()
            flash("Terminal updated successfully!", "success")
            return redirect(url_for('admin_terminals'))

        # For GET requests — fetch data for the edit page
        cur.execute("SELECT * FROM Airport_Management.Terminal WHERE Terminal_ID=%s", (terminal_id,))
        terminal = cur.fetchone()
        cur.close(); conn.close()

        return render_template('terminal_edit.html', terminal=terminal)

    except Error as e:
        flash(f"Error fetching terminal: {e}", "error")
        return redirect(url_for('admin_terminals'))


@app.route('/delete_terminal/<int:id>', methods=['POST'])
def delete_terminal(id):
    conn = airport_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM Terminal WHERE Terminal_ID=%s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    flash("Terminal deleted successfully!", "success")
    return redirect(url_for('admin_terminals'))

@app.route('/admin_gates')
def admin_gates():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
        )
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT g.Gate_ID, g.Gate_Name, g.Terminal_ID, g.Flight_ID, g.Status
            FROM Gate g
            ORDER BY g.Gate_ID
        """)
        gates = cur.fetchall()
        conn.close()
        return render_template('admin_gates.html', gates=gates)
    except Exception as e:
        flash(f"Error loading gate data: {e}", "danger")
        return redirect(url_for('admin_dashboard'))
@app.route('/add_gate', methods=['POST'])
def add_gate():
    try:
        Gate_ID = request.form['Gate_ID']
        Gate_Name = request.form['Gate_Name']
        Terminal_ID = request.form['Terminal_ID']   # <--- this name must match input name
        Flight_ID = request.form.get('Flight_ID') or None
        Status = request.form['Status']

        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
        )
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Gate (Gate_ID, Gate_Name, Terminal_ID, Flight_ID, Status)
            VALUES (%s, %s, %s, %s, %s)
        """, (Gate_ID, Gate_Name, Terminal_ID, Flight_ID, Status))
        conn.commit()
        conn.close()
        flash("Gate added successfully!", "success")
    except Exception as e:
        flash(f"Error adding gate: {e}", "danger")

    return redirect(url_for('admin_gates'))


    
@app.route('/gate_edit/<int:gate_id>', methods=['GET', 'POST'])
def gate_edit(gate_id):
    conn = mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
    )
    cur = conn.cursor(dictionary=True)

    if request.method == 'POST':
        gate_name = request.form['Gate_Name']
        terminal_id = request.form['Terminal_ID']
        flight_id = request.form['Flight_ID']
        status = request.form['Status']

        try:
            cur.execute("""
                UPDATE Gate
                SET Gate_Name=%s, Terminal_ID=%s, Flight_ID=%s, Status=%s
                WHERE Gate_ID=%s
            """, (gate_name, terminal_id, flight_id, status, gate_id))
            conn.commit()
            conn.close()
            flash("Gate updated successfully!", "success")
            return redirect(url_for('admin_gates'))
        except Exception as e:
            flash(f"Error updating gate: {e}", "danger")
            return redirect(url_for('admin_gates'))

    cur.execute("SELECT * FROM Gate WHERE Gate_ID=%s", (gate_id,))
    gate = cur.fetchone()
    conn.close()
    return render_template('gate_edit.html', gate=gate)
@app.route('/delete_gate/<int:gate_id>')
def delete_gate(gate_id):
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
        )
        cur = conn.cursor()
        cur.execute("DELETE FROM Gate WHERE Gate_ID=%s", (gate_id,))
        conn.commit()
        conn.close()
        flash("Gate deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting gate: {e}", "danger")

    return redirect(url_for('admin_gates'))

# ---------------- RUNWAY MANAGEMENT ----------------

@app.route('/admin/runways')
def admin_runways():
    conn = mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Runway")
    runways = cursor.fetchall()
    conn.close()
    return render_template('admin_runway.html', runways=runways)


@app.route('/add_runway', methods=['POST'])
def add_runway():
    try:
        Runway_ID = request.form['Runway_ID']
        Length = request.form['Length']
        Type = request.form['Type']
        Status = request.form['Status']

        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
        )
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Runway (Runway_ID, Length, Type, Status)
            VALUES (%s, %s, %s, %s)
        """, (Runway_ID, Length, Type, Status))
        conn.commit()
        conn.close()
        flash("Runway added successfully!", "success")
    except Exception as e:
        flash(f"Error adding runway: {e}", "danger")

    return redirect(url_for('admin_runways'))


@app.route('/edit_runway/<int:runway_id>', methods=['GET', 'POST'])
def edit_runway(runway_id):
    conn = mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
    )
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        try:
            Length = request.form['Length']
            Type = request.form['Type']
            Status = request.form['Status']

            cursor.execute("""
                UPDATE Runway
                SET Length=%s, Type=%s, Status=%s
                WHERE Runway_ID=%s
            """, (Length, Type, Status, runway_id))
            conn.commit()
            flash("Runway updated successfully!", "success")
            return redirect(url_for('admin_runways'))
        except Exception as e:
            flash(f"Error updating runway: {e}", "danger")

    cursor.execute("SELECT * FROM Runway WHERE Runway_ID=%s", (runway_id,))
    runway = cursor.fetchone()
    conn.close()
    return render_template('runway_edit.html', runway=runway)


@app.route('/delete_runway/<int:runway_id>')
def delete_runway(runway_id):
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
        )
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Runway WHERE Runway_ID=%s", (runway_id,))
        conn.commit()
        conn.close()
        flash("Runway deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting runway: {e}", "danger")

    return redirect(url_for('admin_runways'))

# -------------------- AIRPLANE MANAGEMENT --------------------
@app.route('/airplanes', methods=['GET', 'POST'])
def airplane_page():
    conn = mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
    )
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        Airplane_ID = request.form['airplane_id']
        Airline_Name = request.form['airline_name']
        Model = request.form['model']
        Seating_Capacity = request.form['seating_capacity']
        Country = request.form['country']

        try:
            cursor.execute("""
                INSERT INTO Airplane (Airplane_ID, Airline_Name, Model, Seating_Capacity, Country)
                VALUES (%s, %s, %s, %s, %s)
            """, (Airplane_ID, Airline_Name, Model, Seating_Capacity, Country))
            conn.commit()
            flash("✈️ Airplane added successfully!", "success")
        except Exception as e:
            conn.rollback()
            flash(f"❌ Error adding airplane: {e}", "danger")

    cursor.execute("SELECT * FROM Airplane ORDER BY Airplane_ID DESC")
    airplanes = cursor.fetchall()
    conn.close()
    return render_template("admin_airplane.html", airplanes=airplanes)


@app.route('/airplane/edit/<int:id>', methods=['GET', 'POST'])
def edit_airplane(id):
    conn = mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
    )
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        Airline_Name = request.form['airline_name']
        Model = request.form['model']
        Seating_Capacity = request.form['seating_capacity']
        Country = request.form['country']

        cursor.execute("""
            UPDATE Airplane 
            SET Airline_Name=%s, Model=%s, Seating_Capacity=%s, Country=%s
            WHERE Airplane_ID=%s
        """, (Airline_Name, Model, Seating_Capacity, Country, id))
        conn.commit()
        conn.close()
        flash("Airplane updated successfully!", "success")
        return redirect(url_for('airplane_page'))

    cursor.execute("SELECT * FROM Airplane WHERE Airplane_ID=%s", (id,))
    airplane = cursor.fetchone()
    conn.close()
    return render_template("airplane_edit.html", airplane=airplane)


@app.route('/airplane/delete/<int:id>')
def delete_airplane(id):
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
        )
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Airplane WHERE Airplane_ID=%s", (id,))
        conn.commit()
        conn.close()
        flash("Airplane deleted successfully!", "info")
        return redirect(url_for('airplane_page'))
    except Exception as e:
        flash(f"Error deleting airplane: {e}", "danger")
        return redirect(url_for('airplane_page'))

@app.route('/admin_view')
def admin_view():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_AIRPORT
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM PassengerBookings")
        data = cursor.fetchall()
        conn.close()
        return render_template("admin_view.html", data=data)
    except Exception as e:
        flash(f"Error loading view data: {e}", "danger")
        return redirect(url_for('admin_dashboard'))


# ---------- RUN ----------
if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)







