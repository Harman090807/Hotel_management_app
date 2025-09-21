# app.py
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from models import Room, Customer
from typing import List, Dict
import re

app = Flask(__name__)
app.secret_key = "dev-secret"  # for flash messages in UI

# In-memory storage (like your C++ arrays)
rooms: List[Room] = []
booking_ids = set()

# Helper functions
def find_room_index(rno: int):
    for i, r in enumerate(rooms):
        if r.room_number == rno:
            return i
    return None

# UI Routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/manage-rooms", methods=["GET", "POST"])
def manage_rooms():
    if request.method == "POST":
        try:
            rno = int(request.form["room_number"])
        except ValueError:
            flash("Room number must be an integer", "danger")
            return redirect(url_for("manage_rooms"))

        if find_room_index(rno) is not None:
            flash("Room number already exists. Choose a unique number.", "warning")
            return redirect(url_for("manage_rooms"))

        ac = request.form.get("ac", "N").upper()
        comfort = request.form.get("comfort", "N").upper()
        size = request.form.get("size", "S").upper()
        rent = int(request.form.get("rent", 0))

        # basic validation
        if ac not in ("A", "N") or comfort not in ("S", "N") or size not in ("B", "S"):
            flash("Invalid room attributes", "danger")
            return redirect(url_for("manage_rooms"))

        room = Room(room_number=rno, ac=ac, comfort=comfort, size=size, rent=rent, status=0, cust=None)
        rooms.append(room)
        flash(f"Room {rno} added successfully", "success")
        return redirect(url_for("manage_rooms"))

    return render_template("manage_rooms.html", rooms=rooms)

@app.route("/checkin", methods=["GET", "POST"])
def checkin():
    if request.method == "POST":
        try:
            rno = int(request.form["room_number"])
        except ValueError:
            flash("Invalid room number", "danger")
            return redirect(url_for("checkin"))

        idx = find_room_index(rno)
        if idx is None:
            flash("Room not found", "warning")
            return redirect(url_for("checkin"))

        room = rooms[idx]
        if room.status == 1:
            flash("Room is already booked", "warning")
            return redirect(url_for("checkin"))

        try:
            booking_id = int(request.form["booking_id"])
        except ValueError:
            flash("Booking ID must be an integer", "danger")
            return redirect(url_for("checkin"))

        if booking_id in booking_ids:
            flash("Booking ID already taken. Use a different ID", "warning")
            return redirect(url_for("checkin"))

        name = request.form.get("name", "").strip()
        address = request.form.get("address", "").strip()
        phone = request.form.get("phone", "").strip()
        from_date = request.form.get("from_date", "").strip()
        to_date = request.form.get("to_date", "").strip()
        try:
            advance = float(request.form.get("advance", 0))
        except ValueError:
            advance = 0.0

        # create customer and assign
        cust = Customer(
            name=name,
            address=address,
            phone=phone,
            from_date=from_date,
            to_date=to_date,
            payment_advance=advance,
            booking_id=booking_id
        )
        room.cust = cust
        room.status = 1
        booking_ids.add(booking_id)
        flash(f"Customer {name} checked into room {rno}", "success")
        return redirect(url_for("checkin"))

    return render_template("checkin.html", rooms=rooms)

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    if request.method == "POST":
        try:
            rno = int(request.form["room_number"])
        except ValueError:
            flash("Invalid room number", "danger")
            return redirect(url_for("checkout"))

        idx = find_room_index(rno)
        if idx is None or rooms[idx].status == 0:
            flash("Room is not currently checked-in", "warning")
            return redirect(url_for("checkout"))

        try:
            days = int(request.form["days"])
        except ValueError:
            flash("Number of days must be an integer", "danger")
            return redirect(url_for("checkout"))

        room = rooms[idx]
        bill = days * room.rent
        advance = room.cust.payment_advance if room.cust else 0.0
        payable = bill - advance

        # free the room
        if room.cust and room.cust.booking_id:
            booking_ids.discard(room.cust.booking_id)
        room.cust = None
        room.status = 0

        return render_template("guests.html", checkout_result={
            "room_number": rno,
            "bill": bill,
            "advance": advance,
            "payable": payable
        })

    return render_template("checkout.html", rooms=rooms)

@app.route("/guests")
def guests():
    current_guests = [r for r in rooms if r.status == 1]
    return render_template("guests.html", guests=current_guests)

@app.route("/available")
def available():
    avail_rooms = [r for r in rooms if r.status == 0]
    return render_template("index.html", available=avail_rooms)

# --- Simple JSON API endpoints (for integration or React frontend) ---

@app.route("/api/rooms", methods=["GET", "POST"])
def api_rooms():
    if request.method == "GET":
        return jsonify([{
            "room_number": r.room_number,
            "ac": r.ac,
            "comfort": r.comfort,
            "size": r.size,
            "rent": r.rent,
            "status": r.status,
            "cust": vars(r.cust) if r.cust else None
        } for r in rooms])
    else:
        data = request.json or {}
        rno = data.get("room_number")
        if rno is None:
            return jsonify({"error": "room_number required"}), 400
        if find_room_index(rno) is not None:
            return jsonify({"error": "room exists"}), 400
        room = Room(
            room_number=rno,
            ac=data.get("ac", "N"),
            comfort=data.get("comfort", "N"),
            size=data.get("size", "S"),
            rent=int(data.get("rent", 0)),
            status=0
        )
        rooms.append(room)
        return jsonify({"ok": True}), 201

@app.route("/api/rooms/<int:rno>", methods=["GET"])
def api_room(rno):
    idx = find_room_index(rno)
    if idx is None:
        return jsonify({"error": "not found"}), 404
    r = rooms[idx]
    return jsonify({
        "room_number": r.room_number,
        "ac": r.ac,
        "comfort": r.comfort,
        "size": r.size,
        "rent": r.rent,
        "status": r.status,
        "cust": vars(r.cust) if r.cust else None
    })

@app.route("/api/checkin", methods=["POST"])
def api_checkin():
    data = request.json or {}
    rno = data.get("room_number")
    if rno is None:
        return jsonify({"error": "room_number required"}), 400
    idx = find_room_index(rno)
    if idx is None:
        return jsonify({"error": "room not found"}), 404
    room = rooms[idx]
    if room.status == 1:
        return jsonify({"error": "already booked"}), 400

    booking_id = data.get("booking_id")
    if booking_id in booking_ids:
        return jsonify({"error": "booking id taken"}), 400

    cust = Customer(
        name=data.get("name",""),
        address=data.get("address",""),
        phone=data.get("phone",""),
        from_date=data.get("from_date",""),
        to_date=data.get("to_date",""),
        payment_advance=float(data.get("payment_advance",0)),
        booking_id=booking_id
    )
    room.cust = cust
    room.status = 1
    booking_ids.add(booking_id)
    return jsonify({"ok": True}), 200

@app.route("/api/checkout", methods=["POST"])
def api_checkout():
    data = request.json or {}
    rno = data.get("room_number")
    days = int(data.get("days", 0))
    idx = find_room_index(rno)
    if idx is None or rooms[idx].status == 0:
        return jsonify({"error": "room not checked-in"}), 400
    room = rooms[idx]
    bill = days * room.rent
    advance = room.cust.payment_advance if room.cust else 0.0
    payable = bill - advance
    booking_ids.discard(room.cust.booking_id) if room.cust and room.cust.booking_id else None
    room.cust = None
    room.status = 0
    return jsonify({"bill": bill, "advance": advance, "payable": payable}), 200

@app.route("/api/search_customer")
def api_search_customer():
    name = request.args.get("name", "").strip().lower()
    results = []
    if name:
        for r in rooms:
            if r.status == 1 and r.cust and r.cust.name.lower() == name:
                results.append({"room_number": r.room_number, "customer": vars(r.cust)})
    return jsonify(results)

@app.route("/api/guests")
def api_guests():
    guests_list = []
    for r in rooms:
        if r.status == 1 and r.cust:
            guests_list.append({
                "room_number": r.room_number,
                "customer": vars(r.cust)
            })
    return jsonify(guests_list)

if __name__ == "__main__":
    app.run(debug=True)
