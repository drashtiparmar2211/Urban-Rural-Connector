from flask import Flask, request, jsonify, g, send_from_directory
from flask_cors import CORS
import os, random, string, math, sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# We use '..' to go up one folder, then into the Main Website's database folder
DATABASE = os.path.join(os.path.dirname(__file__), "..", "URC_Main_Website", "instance", "urc_database.db")
BASE_FARE   = 20.0
RATE_PER_KM = 8.0

@app.get("/")
def index():
    return send_from_directory("frontend", "index.html")

TIER_CONFIG = {
    1: {"name": "Instant",  "allow_group": False, "threshold": 1,  "max_wait_hrs": 0},
    2: {"name": "Priority", "allow_group": True,  "threshold": 2,  "max_wait_hrs": 4},
    3: {"name": "Standard", "allow_group": True,  "threshold": 5,  "max_wait_hrs": 12},
}

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.teardown_appcontext
def close_db(exc):
    db = getattr(g, "_database", None)
    if db: db.close()

def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rv  = cur.fetchall()
    return (rv[0] if rv else None) if one else rv

def execute(sql, args=()):
    db  = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid

def row_to_dict(row):
    return dict(row) if row else None


def haversine_km(lat1, lng1, lat2, lng2):
    """Straight-line distance in km between two GPS points."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def calc_delivery_cost(distance_km, vehicle_type="auto"):
    multiplier = {"bike": 0.8, "auto": 1.0, "truck": 1.5}.get(vehicle_type, 1.0)
    return round((BASE_FARE + distance_km * RATE_PER_KM) * multiplier, 2)

def gen_otp(length=6):
    return "".join(random.choices(string.digits, k=length))

def gen_pickup_id():
    return "PID-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

def ok(data=None, msg="success", code=200):
    return jsonify({"status": "ok", "message": msg, "data": data}), code

def err(msg="error", code=400):
    return jsonify({"status": "error", "message": msg}), code

def init_transport_db():
    db = get_db()
    
    # 1. Create missing Logistics Tables [cite: 1518-1546]
    db.execute("CREATE TABLE IF NOT EXISTS active_groups (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER, group_name TEXT, status TEXT DEFAULT 'open', joined INTEGER DEFAULT 0, threshold INTEGER DEFAULT 5, total_cost FLOAT, expires_at DATETIME, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)")
    db.execute("CREATE TABLE IF NOT EXISTS backhaul_bookings (id INTEGER PRIMARY KEY AUTOINCREMENT, driver_id INTEGER, requester_id INTEGER, item_desc TEXT, origin_city TEXT, destination TEXT, weight_kg FLOAT, original_cost FLOAT, discount_pct FLOAT, final_cost FLOAT, scheduled_date TEXT, status TEXT DEFAULT 'pending', created_at DATETIME DEFAULT CURRENT_TIMESTAMP)")
    db.execute("CREATE TABLE IF NOT EXISTS verification_otps (id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER, otp_type TEXT, otp_code TEXT, is_used INTEGER DEFAULT 0, expires_at DATETIME, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)")
    
    # 2. Create the Drivers table (Main app doesn't have this yet)
    db.execute("CREATE TABLE IF NOT EXISTS drivers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, phone TEXT, vehicle_type TEXT, vehicle_num TEXT, rating FLOAT, gps_lat FLOAT, gps_lng FLOAT, is_available INTEGER DEFAULT 1)")
    
    # 3. Insert a Sample Driver so 'Raju Bhai' works in your tracker [cite: 1182-1185]
    check_driver = db.execute("SELECT * FROM drivers WHERE name='Raju Bhai'").fetchone()
    if not check_driver:
        db.execute("INSERT INTO drivers (name, phone, vehicle_type, vehicle_num, rating, is_available) VALUES ('Raju Bhai', '+918765432108', 'bike', 'GJ-06-AB-9999', 5.0, 1)")

    db.commit()

# Ensure this runs when the Transport server starts [cite: 1549-1550]
with app.app_context():
    init_transport_db()


@app.get("/api/producers")
def list_producers():
    rows = query("SELECT * FROM producers")
    return ok([row_to_dict(r) for r in rows])

@app.get("/api/delivery/options/<int:product_id>")
def delivery_options(product_id):
    # Ensure this pulls the product correctly
    prod = query("SELECT * FROM products WHERE id=?", (product_id,), one=True)
    if not prod: return err("Product not found", 404)
    
    tier    = prod["perishability"]
    config  = TIER_CONFIG[tier]
    options = []

    options.append({
        "type": "self",
        "label": "Self Pickup (Direct-from-Farm)",
        "cost": 0,
        "description": "Collect directly from the farm. Free!",
        "available": True,
    })

    if config["allow_group"]:
        group = query("""
            SELECT * FROM active_groups
            WHERE product_id=? AND status='open'
            ORDER BY created_at DESC LIMIT 1
        """, (product_id,), one=True)
        options.append({
            "type": "group",
            "label": "Group Pickup (Community Economy)",
            "cost": "Shared cost",
            "description": f"Join with neighbors. {config['threshold']} orders trigger a driver.",
            "available": True,
            "group_info": row_to_dict(group) if group else None,
            "threshold": config["threshold"],
            "max_wait_hrs": config["max_wait_hrs"],
        })

    options.append({
        "type": "standard",
        "label": "Standard Delivery (Door-to-Door)",
        "cost": "Based on distance",
        "description": "Dedicated driver. Live GPS tracking.",
        "available": True,
    })

    return ok({
        "product_id": product_id,
        "perishability_tier": tier,
        "tier_name": config["name"],
        "options": options,
    })


@app.post("/api/delivery/quote")
def delivery_quote():
    """Calculate delivery cost for a buyer–producer pair."""
    data = request.json or {}
    prod_id    = data.get("product_id")
    buyer_lat  = data.get("buyer_lat")
    buyer_lng  = data.get("buyer_lng")
    dtype      = data.get("delivery_type", "standard")

    if not all([prod_id, buyer_lat, buyer_lng]):
        return err("product_id, buyer_lat, buyer_lng required")

    prod = query("""
        SELECT p.*, pr.gps_lat, pr.gps_lng FROM products p
        JOIN producers pr ON p.producer_id = pr.id WHERE p.id = ?
    """, (prod_id,), one=True)
    if not prod: return err("Product not found", 404)

    dist = haversine_km(prod["gps_lat"], prod["gps_lng"], buyer_lat, buyer_lng)

    if dtype == "self":
        cost = 0.0
    elif dtype == "group":
       
        cost = calc_delivery_cost(dist)
    else:
        cost = calc_delivery_cost(dist)

    return ok({
        "distance_km": round(dist, 2),
        "delivery_cost": cost,
        "formula": f"₹{BASE_FARE} base + {dist:.1f}km × ₹{RATE_PER_KM}/km",
    })


@app.post("/api/orders")
def create_order():
    data = request.json or {}
    required = ["buyer_id", "product_id", "quantity", "delivery_type"]
    if not all(k in data for k in required):
        return err(f"Missing fields: {required}")

    buyer_id      = data["buyer_id"]
    product_id    = data["product_id"]
    quantity      = int(data["quantity"])
    delivery_type = data["delivery_type"]   
    buyer_lat     = data.get("buyer_lat")
    buyer_lng     = data.get("buyer_lng")

    prod = query("""
        SELECT p.*, pr.gps_lat as farm_lat, pr.gps_lng as farm_lng, pr.id as farm_id
        FROM products p JOIN producers pr ON p.producer_id = pr.id
        WHERE p.id = ?
    """, (product_id,), one=True)
    if not prod: return err("Product not found", 404)
    if prod["stock"] < quantity: return err("Insufficient stock")

    tier = prod["perishability"]
    if delivery_type == "group" and not TIER_CONFIG[tier]["allow_group"]:
        return err("Group delivery not allowed for Tier-1 (Instant) products")

    total_price   = round(prod["price_per_unit"] * quantity, 2)
    distance_km   = 0.0
    delivery_cost = 0.0
    driver_id     = None
    group_id      = None
    pickup_id     = None

    if delivery_type == "self":
        pickup_id = gen_pickup_id()

    elif delivery_type == "standard":
        if not (buyer_lat and buyer_lng):
            return err("buyer_lat and buyer_lng required for standard delivery")
        distance_km   = haversine_km(prod["farm_lat"], prod["farm_lng"], buyer_lat, buyer_lng)
        delivery_cost = calc_delivery_cost(distance_km)
    
        drv = query("SELECT * FROM drivers WHERE is_available=1 ORDER BY RANDOM() LIMIT 1", one=True)
        if drv: driver_id = drv["id"]

    elif delivery_type == "group":
        cfg  = TIER_CONFIG[tier]
        grp  = query("""
            SELECT * FROM active_groups WHERE product_id=? AND status='open'
            ORDER BY created_at DESC LIMIT 1
        """, (product_id,), one=True)

        if not grp:
            expires = datetime.utcnow() + timedelta(hours=cfg["max_wait_hrs"] or 12)
           
            if buyer_lat and buyer_lng:
                distance_km = haversine_km(prod["farm_lat"], prod["farm_lng"], buyer_lat, buyer_lng)
            est_cost = calc_delivery_cost(distance_km or 10)
            grp_id = execute("""
                INSERT INTO active_groups(product_id, delivery_zone, threshold, joined,
                                          total_cost, expires_at, status)
                VALUES(?, ?, ?, 1, ?, ?, 'open')
            """, (product_id, "Vadodara", cfg["threshold"], est_cost,
                  expires.strftime("%Y-%m-%d %H:%M:%S")))
            group_id = grp_id
        else:
            group_id  = grp["id"]
            new_joined = grp["joined"] + 1
           
            delivery_cost = round(grp["total_cost"] / new_joined, 2)
            execute("UPDATE active_groups SET joined=? WHERE id=?", (new_joined, group_id))
            
            if new_joined >= grp["threshold"]:
                drv = query("SELECT * FROM drivers WHERE is_available=1 ORDER BY RANDOM() LIMIT 1", one=True)
                if drv:
                    driver_id = drv["id"]
                execute("UPDATE active_groups SET status='full' WHERE id=?", (group_id,))

    order_id = execute("""
        INSERT INTO orders(buyer_id, producer_id, product_id, driver_id, group_id,
                            delivery_type, quantity, total_price, delivery_cost,
                            distance_km, status, pickup_id)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
    """, (buyer_id, prod["farm_id"], product_id, driver_id, group_id,
          delivery_type, quantity, total_price, delivery_cost,
          round(distance_km, 2), "confirmed", pickup_id))

   
    execute("UPDATE products SET stock = stock - ? WHERE id=?", (quantity, product_id))

   
    if delivery_type != "self":
        now = datetime.utcnow()
        exp = (now + timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
        for otp_type in ("pickup", "delivery"):
            execute("""
                INSERT INTO verification_otps(order_id, otp_type, otp_code, expires_at)
                VALUES(?,?,?,?)
            """, (order_id, otp_type, gen_otp(), exp))

    order = query("SELECT * FROM orders WHERE id=?", (order_id,), one=True)
    return ok(row_to_dict(order), "Order created successfully", 201)


@app.route("/api/orders/<int:order_id>")
def get_order(order_id):
    db = get_db()
    cursor = db.cursor()
    
    # Simple query first to see if the order exists at all
    query = """
    SELECT o.*, 
           u_buyer.name as buyer_name, 
           u_buyer.phone as buyer_phone, 
           u_seller.name as producer_name,
           d.name as driver_name, 
           d.phone as driver_phone, 
           d.vehicle_type, 
           d.vehicle_num, 
           d.rating as driver_rating
    FROM orders o
    JOIN users u_buyer ON o.user_id = u_buyer.id
    JOIN users u_seller ON o.seller_id = u_seller.id
    LEFT JOIN drivers d ON o.driver_id = d.id
    WHERE o.id = ?
    """
    
    try:
        cursor.execute(query, (order_id,))
        row = cursor.fetchone()
        db.close()
        
        if row:
        # Convert the sqlite3.Row object to a dictionary
            data = dict(row)
            return jsonify({"status": "ok", "data": data})
        else:
            return jsonify({"status": "error", "message": "Order not found"}), 404
        
    except Exception as e:
        print(f"Transport API Error: {e}")
        return {"status": "error", "message": str(e)}, 500
    finally:
        db.close()


@app.get("/api/orders")
def list_orders():
    buyer_id = request.args.get("buyer_id")
    if buyer_id:
        rows = query("SELECT * FROM orders WHERE buyer_id=? ORDER BY created_at DESC", (buyer_id,))
    else:
        rows = query("SELECT * FROM orders ORDER BY created_at DESC LIMIT 50")
    return ok([row_to_dict(r) for r in rows])



@app.get("/api/orders/<int:order_id>/otps")
def get_otps(order_id):
    """Return OTPs for an order (dev/demo endpoint — restrict in production)."""
    rows = query("SELECT * FROM verification_otps WHERE order_id=?", (order_id,))
    return ok([row_to_dict(r) for r in rows])


@app.post("/api/orders/<int:order_id>/verify-otp")
def verify_otp(order_id):
    data     = request.json or {}
    otp_type = data.get("otp_type")   
    otp_code = data.get("otp_code")

    if not otp_type or not otp_code:
        return err("otp_type and otp_code required")

    record = query("""
        SELECT * FROM verification_otps
        WHERE order_id=? AND otp_type=? AND is_used=0
        ORDER BY created_at DESC LIMIT 1
    """, (order_id, otp_type), one=True)

    if not record: return err("OTP not found or already used", 404)
    if record["otp_code"] != otp_code: return err("Invalid OTP", 401)
    if datetime.strptime(record["expires_at"], "%Y-%m-%d %H:%M:%S") < datetime.utcnow():
        return err("OTP expired", 410)

    execute("UPDATE verification_otps SET is_used=1 WHERE id=?", (record["id"],))

    new_status = "in_transit" if otp_type == "pickup" else "delivered"
    execute("UPDATE orders SET status=? WHERE id=?", (new_status, order_id))
    if new_status == "delivered":
        execute("UPDATE orders SET delivered_at=? WHERE id=?",
                (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), order_id))

    return ok({"verified": True, "order_status": new_status})


@app.post("/api/orders/<int:order_id>/proof")
def upload_proof(order_id):
    data     = request.json or {}
    driver_id = data.get("driver_id")
    photo_url = data.get("photo_url")
    notes     = data.get("notes", "")

    if not driver_id or not photo_url:
        return err("driver_id and photo_url required")

    proof_id = execute("""
        INSERT INTO condition_proofs(order_id, driver_id, photo_url, notes)
        VALUES(?,?,?,?)
    """, (order_id, driver_id, photo_url, notes))

    execute("UPDATE orders SET status='pickup_otp_sent' WHERE id=?", (order_id,))
    return ok({"proof_id": proof_id}, "Proof uploaded", 201)



@app.get("/api/groups")
def list_groups():
    # Changed p.name to p.title
    rows = query("""
        SELECT ag.*, p.title as product_name, p.category as perishability
        FROM active_groups ag
        JOIN products p ON ag.product_id = p.id
        WHERE ag.status = 'open'
        ORDER BY ag.created_at DESC
    """)
    return ok([row_to_dict(r) for r in rows])


@app.get("/api/groups/<int:group_id>")
def get_group(group_id):
    # Changed p.name to p.title
    row = query("""
        SELECT ag.*, p.title as product_name, p.category as perishability,
        u.name as producer_name
        FROM active_groups ag
        JOIN products p  ON ag.product_id   = p.id
        JOIN users u ON p.seller_id  = u.id
        WHERE ag.id = ?
    """, (group_id,), one=True)
    if not row: return err("Group not found", 404)
    grp = row_to_dict(row)
    grp["progress_pct"] = min(100, int((grp["joined"] / grp["threshold"]) * 100))
    grp["cost_per_person"] = round(grp["total_cost"] / max(grp["joined"], 1), 2)
    return ok(grp)


@app.get("/api/backhaul/drivers")
def returning_drivers():
    """List drivers returning from city to village today."""
    today = datetime.utcnow().date().isoformat()
    rows  = query("""
        SELECT DISTINCT d.id, d.name, d.phone, d.vehicle_type, d.vehicle_num,
               d.rating, d.gps_lat, d.gps_lng
        FROM drivers d
        WHERE d.is_available = 1
    """)
    return ok([row_to_dict(r) for r in rows])


@app.post("/api/backhaul")
def book_backhaul():
    data = request.json or {}
    required = ["driver_id", "requester_id", "item_desc",
                "origin_city", "destination", "scheduled_date"]
    if not all(k in data for k in required):
        return err(f"Required: {required}")

   
    weight      = float(data.get("weight_kg", 10))
    base_cost   = calc_delivery_cost(15, "auto")   
    discount    = data.get("discount_pct", 40)
    final_cost  = round(base_cost * (1 - discount / 100), 2)

    bid = execute("""
        INSERT INTO backhaul_bookings(driver_id, requester_id, item_desc, origin_city,
                                       destination, weight_kg, original_cost, discount_pct,
                                       final_cost, scheduled_date)
        VALUES(?,?,?,?,?,?,?,?,?,?)
    """, (data["driver_id"], data["requester_id"], data["item_desc"],
          data["origin_city"], data["destination"], weight,
          base_cost, discount, final_cost, data["scheduled_date"]))

    return ok({
        "booking_id": bid,
        "original_cost": base_cost,
        "discount_pct": discount,
        "final_cost": final_cost,
    }, "Back-haul booking confirmed", 201)


@app.get("/api/backhaul")
def list_backhaul():
    requester_id = request.args.get("requester_id")
    if requester_id:
        rows = query("SELECT * FROM backhaul_bookings WHERE requester_id=?", (requester_id,))
    else:
        rows = query("SELECT * FROM backhaul_bookings ORDER BY created_at DESC LIMIT 30")
    return ok([row_to_dict(r) for r in rows])


@app.get("/api/drivers")
def list_drivers():
    rows = query("SELECT * FROM drivers")
    return ok([row_to_dict(r) for r in rows])


@app.put("/api/drivers/<int:driver_id>/location")
def update_driver_location(driver_id):
    data = request.json or {}
    lat, lng = data.get("lat"), data.get("lng")
    if not lat or not lng: return err("lat and lng required")
    execute("UPDATE drivers SET gps_lat=?, gps_lng=? WHERE id=?", (lat, lng, driver_id))
    return ok({"driver_id": driver_id, "lat": lat, "lng": lng})

@app.get("/api/stats")
def dashboard_stats():
    total_orders    = query("SELECT COUNT(*) as c FROM orders", one=True)["c"]
    delivered       = query("SELECT COUNT(*) as c FROM orders WHERE status='delivered'", one=True)["c"]
    active_groups   = query("SELECT COUNT(*) as c FROM active_groups WHERE status='open'", one=True)["c"]
    active_drivers  = query("SELECT COUNT(*) as c FROM drivers WHERE is_available=1", one=True)["c"]
    backhaul_count  = query("SELECT COUNT(*) as c FROM backhaul_bookings", one=True)["c"]
    revenue         = query("SELECT SUM(total_price) as s FROM orders WHERE status='delivered'", one=True)["s"] or 0

    return ok({
        "total_orders": total_orders,
        "delivered_orders": delivered,
        "active_groups": active_groups,
        "active_drivers": active_drivers,
        "backhaul_bookings": backhaul_count,
        "total_revenue": round(revenue, 2),
    })


if __name__ == "__main__":
    # We no longer run init_db() or schema.sql because 
    # the Main Website handles the database structure now.
    print("Connecting to Shared URC Database...")
    app.run(debug=True, port=5001)    
