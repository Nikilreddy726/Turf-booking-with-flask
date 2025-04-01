from flask import Flask, render_template, request, redirect, url_for, flash, get_flashed_messages
from flask_sqlalchemy import SQLAlchemy
from flask_apscheduler import APScheduler
from datetime import datetime, date

# Flask app initialization
app = Flask(__name__)
app.config['SECRET_KEY'] = 'ABCD123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SCHEDULER_API_ENABLED'] = True

db = SQLAlchemy(app)
scheduler = APScheduler()
scheduler.init_app(app)

# Booking db model
class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    payment = db.Column(db.String(50), nullable=False)
    sport = db.Column(db.String(50), nullable=True)
    date_booked = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f"<Booking {self.id}>"

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/sports')
def sports():
    return render_template('sports.html')

@app.route('/book')
def book():
    today_date = date.today()
    current_time = datetime.now().strftime("%H:%M")
    sport = request.args.get('game')
    return render_template('book.html', sport=sport, today_date=today_date, current_time=current_time)

@app.route('/confirm', methods=['POST'])
def confirm():
    try:
        name = request.form['name']
        location = request.form['location']
        payment = request.form['payment']
        sport = request.form.get('sport')
        
        booking_date = request.form.get('date')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        
        booking_date = datetime.strptime(booking_date, '%Y-%m-%d').date()
        start_datetime = datetime.strptime(f"{booking_date} {start_time}", '%Y-%m-%d %H:%M')
        end_datetime = datetime.strptime(f"{booking_date} {end_time}", '%Y-%m-%d %H:%M')
        
        # Validate date and time
        if booking_date < date.today():
            flash("Cannot book for past dates", "error")
            return redirect(url_for('book'))
        
        if booking_date == date.today() and start_datetime < datetime.now():
            flash("Start time cannot be in the past", "error")
            return redirect(url_for('book'))
        
        if end_datetime <= start_datetime:
            flash("End time must be after start time", "error")
            return redirect(url_for('book'))
        
        # Check for booking conflicts
        existing_booking = Booking.query.filter(
            Booking.location == location,
            Booking.date == booking_date,
            db.or_(
                db.and_(Booking.start_time <= start_datetime.time(), Booking.end_time > start_datetime.time()),
                db.and_(Booking.start_time < end_datetime.time(), Booking.end_time >= end_datetime.time()),
                db.and_(Booking.start_time >= start_datetime.time(), Booking.end_time <= end_datetime.time())
            )
        ).first()

        if existing_booking:
            flash('The Ground is already booked for the selected date and time.', 'error')
            return redirect('/sports')

        # Create and save new booking
        new_booking = Booking(
            name=name,
            date=booking_date,
            start_time=start_datetime.time(),
            end_time=end_datetime.time(),
            location=location,
            payment=payment,
            sport=sport
        )
        db.session.add(new_booking)
        db.session.commit()

        return render_template('thankyou.html', name=name, sport=sport, location=location)
    
    except Exception as e:
        flash(f"An error occurred: {str(e)}", 'error')
        return redirect(url_for('book'))

@app.route('/bookings')
def view_bookings():
    bookings = Booking.query.order_by(Booking.start_time.desc()).all()
    return render_template('bookings.html', bookings=bookings, messages=get_flashed_messages(with_categories=True))

@app.route('/delete_booking/<int:booking_id>', methods=['POST'])
def delete_booking(booking_id):
    booking = Booking.query.get(booking_id)
    if booking:
        db.session.delete(booking)
        db.session.commit()
        flash('Booking deleted successfully!', 'success')
    else:
        flash('Booking not found!', 'danger')
    return redirect(url_for('view_bookings'))

# Automatic cleanup task
def delete_expired_bookings():
    now = datetime.now()
    expired_bookings = Booking.query.filter(
        Booking.date < now.date(),
        Booking.end_time < now.time()
    ).all()
    for booking in expired_bookings:
        db.session.delete(booking)
    db.session.commit()
    print(f"Deleted {len(expired_bookings)} expired bookings.")

# Schedule the cleanup job
scheduler.add_job(id='delete_expired_bookings', func=delete_expired_bookings, trigger='interval', hours=24)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        scheduler.start()
        print("Database created successfully!")
    app.run(debug=True)