from functools import wraps
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template, request, session, redirect
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from config import DB_CONFIG

app = Flask(__name__)
app.secret_key = "change-this-to-any-long-random-text"
ROLES = {"customer": ("Customer", "Customer_ID"), "seller": ("Supplier", "Supplier_ID"), "admin": ("Admin", "Admin_ID")}
PROFILE = {"customer": ["Name", "Phone_no", "Email", "Address"], "seller": ["Name", "Phone_no", "Address"], "admin": ["Name", "Phone_no", "Address"]}
HOLD = timedelta(hours=12)  # only used for pre-orders that come back in stock
NEXT = {"Paid": "Left for delivery", "Left for delivery": "Delivered"}

def q(sql, args=(), one=False, commit=False):
    """Run one query. Returns rows, or the number of rows changed when commit=True."""
    db = mysql.connector.connect(**DB_CONFIG)
    try:
        cur = db.cursor(dictionary=True)
        cur.execute(sql, args)
        if commit:
            db.commit()
            out = cur.rowcount
        else:
            out = cur.fetchone() if one else cur.fetchall()
        cur.close()
        return out
    finally:
        db.close()

def nid(table, col):  # next id; table/col are fixed names from this file, never user input
    return q(f"SELECT COALESCE(MAX({col}),0)+1 AS n FROM {table}", one=True)["n"]

def fail(msg, code=400):
    return jsonify(error=msg), code

def need(*roles):
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            if session.get("role") not in roles:
                return jsonify(error="Not allowed"), 403
            return f(*a, **k)
        return w
    return deco

# ---------- stock queue (unchanged logic) ----------

def allocate(item):
    """Give free stock to waiting orders, oldest first. Stops at the first order that doesn't fit, so nobody jumps the queue."""
    stock = q("SELECT Stock FROM Product WHERE Item_code=%s", (item,), one=True)["Stock"]
    waiting = q("""SELECT o.Order_ID, oi.Quantity FROM Orders o JOIN Order_Item oi ON oi.Order_ID=o.Order_ID
                   WHERE oi.Item_code=%s AND o.Status='Waiting for stock' ORDER BY o.Created_At, o.Order_ID""", (item,))
    for w in waiting:
        if w["Quantity"] > stock:
            break
        stock -= w["Quantity"]
        q("UPDATE Orders SET Status='Reserved', Reserved_Until=%s WHERE Order_ID=%s", (datetime.now() + HOLD, w["Order_ID"]), commit=True)
        q("DELETE FROM Backorder WHERE Order_ID=%s", (w["Order_ID"],), commit=True)
    q("UPDATE Product SET Stock=%s WHERE Item_code=%s", (stock, item), commit=True)

def cancel_order(oid):
    o = q("""SELECT o.Status, oi.Item_code, oi.Quantity FROM Orders o JOIN Order_Item oi ON oi.Order_ID=o.Order_ID
             WHERE o.Order_ID=%s""", (oid,), one=True)
    if not o or o["Status"] not in ("Reserved", "Waiting for stock"):
        return False
    q("UPDATE Orders SET Status='Cancelled' WHERE Order_ID=%s", (oid,), commit=True)
    q("DELETE FROM Backorder WHERE Order_ID=%s", (oid,), commit=True)
    if o["Status"] == "Reserved":  # released stock is open to everyone, but the queue goes first
        q("UPDATE Product SET Stock=Stock+%s WHERE Item_code=%s", (o["Quantity"], o["Item_code"]), commit=True)
    allocate(o["Item_code"])
    return True

def expire():
    for o in q("SELECT Order_ID FROM Orders WHERE Status='Reserved' AND Reserved_Until < %s", (datetime.now(),)):
        cancel_order(o["Order_ID"])

def buy(cid, lines):
    """Pay for in-stock items right now (no 12-hour timer). lines = {item_code: qty}. All-or-nothing."""
    db = mysql.connector.connect(**DB_CONFIG)
    cur = db.cursor(dictionary=True)
    try:
        total, picked = 0, []
        for item in sorted(lines):
            n = lines[item]
            cur.execute("SELECT Item_name, Price, Stock, Banned FROM Product WHERE Item_code=%s FOR UPDATE", (item,))
            p = cur.fetchone()
            if not p or p["Banned"]:
                raise ValueError("A product in your order is no longer available.")
            cur.execute("""SELECT 1 FROM Orders o JOIN Order_Item oi ON oi.Order_ID=o.Order_ID
                           WHERE oi.Item_code=%s AND o.Status='Waiting for stock' LIMIT 1""", (item,))
            if cur.fetchone() or p["Stock"] < n:
                raise ValueError(f"{p['Item_name']} doesn't have enough stock. Reduce the quantity or pre-order it.")
            total += p["Price"] * n
            picked.append((item, n))
        cur.execute("SELECT COALESCE(MAX(Order_ID),0)+1 AS n FROM Orders FOR UPDATE")
        oid = cur.fetchone()["n"]
        cur.execute("INSERT INTO Orders (Order_ID, Amount, Status, Customer_ID, Created_At) VALUES (%s,%s,'Paid',%s,%s)",
                    (oid, total, cid, datetime.now()))
        for item, n in picked:
            cur.execute("UPDATE Product SET Stock=Stock-%s WHERE Item_code=%s", (n, item))
            cur.execute("INSERT INTO Order_Item (Order_ID, Item_code, Quantity) VALUES (%s,%s,%s)", (oid, item, n))
        cur.execute("INSERT INTO Payment (Order_ID, Payment_ID, Amount, Customer_ID) VALUES (%s,1,%s,%s)", (oid, total, cid))
        db.commit()
        return oid
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

# ---------- pages and auth ----------

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login/<role>", methods=["GET", "POST"])
def login(role):
    if role not in ROLES:
        return redirect("/")
    table, idcol = ROLES[role]
    err = None
    if request.method == "POST":
        u = q(f"SELECT * FROM {table} WHERE Username=%s", (request.form["username"],), one=True)
        if u and u["Password_Hash"] and check_password_hash(u["Password_Hash"], request.form["password"]):
            session.clear(); session.update(role=role, uid=u[idcol], name=u["Name"])
            return redirect("/dash")
        err = "Wrong username or password."
    return render_template("login.html", role=role, err=err, signup=False)

@app.post("/signup/<role>")
def signup(role):
    if role not in ("customer", "seller"):
        return redirect("/")
    table, idcol = ROLES[role]
    name, user, pw = request.form["name"].strip(), request.form["username"].strip(), request.form["password"]
    err = None
    if not (name and user and len(pw) >= 6):
        err = "Fill in every field. Password needs at least 6 characters."
    elif q(f"SELECT 1 FROM {table} WHERE Username=%s", (user,), one=True):
        err = "That username is taken."
    if err:
        return render_template("login.html", role=role, err=err, signup=True)
    uid = nid(table, idcol)
    q(f"INSERT INTO {table} ({idcol}, Name, Username, Password_Hash) VALUES (%s,%s,%s,%s)",
      (uid, name, user, generate_password_hash(pw)), commit=True)
    session.clear(); session.update(role=role, uid=uid, name=name)
    return redirect("/dash")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/dash")
def dash():
    if "role" not in session:
        return redirect("/")
    return render_template("dash.html", role=session["role"], name=session["name"])

# ---------- profile ----------

@app.get("/api/profile")
@need("customer", "seller", "admin")
def profile():
    role = session["role"]; table, idcol = ROLES[role]
    row = q(f"SELECT Username, {', '.join(PROFILE[role])} FROM {table} WHERE {idcol}=%s", (session["uid"],), one=True)
    return jsonify(username=row.pop("Username"), fields=row)

@app.post("/api/profile")
@need("customer", "seller", "admin")
def save_profile():
    role = session["role"]; table, idcol = ROLES[role]; cols = PROFILE[role]
    d = request.json
    vals = [(d.get(c) or "").strip() or None for c in cols]
    if not vals[0]:  # cols[0] is Name
        return fail("Name can't be empty.")
    try:
        q(f"UPDATE {table} SET {', '.join(c + '=%s' for c in cols)} WHERE {idcol}=%s", (*vals, session["uid"]), commit=True)
    except mysql.connector.IntegrityError:
        return fail("That phone number is already used by another account.")
    session["name"] = vals[0]
    return jsonify(ok=True, name=vals[0])

# ---------- products ----------

PSQL = """SELECT p.*, s.Name AS Supplier,
    (SELECT Category_name FROM Product_Category c WHERE c.Item_code=p.Item_code LIMIT 1) AS Category,
    (SELECT AVG(Rating) FROM Review r WHERE r.Item_code=p.Item_code) AS Rating,
    (SELECT COUNT(*) FROM Review r WHERE r.Item_code=p.Item_code) AS Reviews,
    (SELECT COALESCE(SUM(oi.Quantity),0) FROM Order_Item oi JOIN Orders o ON o.Order_ID=oi.Order_ID
      WHERE oi.Item_code=p.Item_code AND o.Status='Waiting for stock') AS Waiting
    FROM Product p LEFT JOIN Supplier s ON s.Supplier_ID=p.Supplier_ID"""

def tidy(r):
    r["Price"] = float(r["Price"] or 0); r["Waiting"] = int(r["Waiting"]); r["Reviews"] = int(r["Reviews"])
    r["Rating"] = float(r["Rating"]) if r["Rating"] is not None else None
    r["Expected_Date"] = str(r["Expected_Date"] or "")
    r["Buyable"] = r["Stock"] if r["Waiting"] == 0 else 0  # if people are queued, nobody skips ahead
    return r

@app.get("/api/categories")
@need("customer", "seller", "admin")
def categories():
    return jsonify([r["Category_name"] for r in q("SELECT Category_name FROM Category ORDER BY Category_name")])

@app.get("/api/products")
@need("customer", "seller", "admin")
def products():
    expire()
    role = session["role"]
    if role == "customer":
        rows = q(PSQL + " WHERE p.Banned=0 ORDER BY p.Item_name")
    elif role == "seller":
        rows = q(PSQL + " WHERE p.Supplier_ID=%s ORDER BY p.Item_name", (session["uid"],))
    else:
        rows = q(PSQL + " ORDER BY p.Item_name")
    return jsonify([tidy(r) for r in rows])

@app.get("/api/product/<int:item>")
@need("customer")
def product_detail(item):
    expire()
    rows = q(PSQL + " WHERE p.Item_code=%s AND p.Banned=0", (item,))
    if not rows:
        return fail("No such product.", 404)
    reviews = q("""SELECT r.Customer_ID, r.Rating, r.Comment, c.Name FROM Review r
                   JOIN Customer c ON c.Customer_ID=r.Customer_ID WHERE r.Item_code=%s""", (item,))
    uid = session["uid"]
    mine = next((r for r in reviews if r["Customer_ID"] == uid), None)
    bought = q("""SELECT 1 FROM Orders o JOIN Order_Item oi ON oi.Order_ID=o.Order_ID
                  WHERE o.Customer_ID=%s AND oi.Item_code=%s AND o.Status='Delivered' LIMIT 1""", (uid, item), one=True)
    for r in reviews:
        del r["Customer_ID"]
    return jsonify(product=tidy(rows[0]), reviews=reviews, can_review=bool(bought), mine=mine)

@app.post("/api/review")
@need("customer")
def review():
    d = request.json
    item, uid = int(d["item_code"]), session["uid"]
    rating = int(d["rating"])
    if not 1 <= rating <= 5:
        return fail("Rating must be 1 to 5.")
    if not q("""SELECT 1 FROM Orders o JOIN Order_Item oi ON oi.Order_ID=o.Order_ID
                WHERE o.Customer_ID=%s AND oi.Item_code=%s AND o.Status='Delivered' LIMIT 1""", (uid, item), one=True):
        return fail("You can review a product after it's been delivered to you.", 403)
    q("""INSERT INTO Review (Customer_ID, Item_code, Rating, Comment) VALUES (%s,%s,%s,%s)
         ON DUPLICATE KEY UPDATE Rating=VALUES(Rating), Comment=VALUES(Comment)""",
      (uid, item, rating, (d.get("comment") or "").strip()[:500] or None), commit=True)
    return jsonify(ok=True)

@app.post("/api/product")
@need("seller")
def add_product():
    d = request.json
    name = (d.get("name") or "").strip()
    try:
        price, stock = float(d["price"]), int(d.get("stock") or 0)
    except (ValueError, KeyError):
        return fail("Enter a valid price and stock.")
    if not name or price < 0 or stock < 0:
        return fail("Name and price are required, and numbers can't be negative.")
    cat = d.get("category")
    if not q("SELECT 1 FROM Category WHERE Category_name=%s", (cat,), one=True):
        return fail("Pick a category.")
    item = nid("Product", "Item_code")
    image = (d.get("image") or "").strip()
    if not image.startswith(("http://", "https://")) or len(image) > 500:
        image = None
    q("INSERT INTO Product (Item_code, Item_name, Details, Price, Stock, Expected_Date, Supplier_ID, Image) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
      (item, name, (d.get("details") or "").strip()[:255], price, stock, d.get("expected") or None, session["uid"], image), commit=True)
    q("INSERT INTO Product_Category (Item_code, Category_name) VALUES (%s,%s)", (item, cat), commit=True)
    return jsonify(ok=True)

@app.post("/api/restock")
@need("seller")
def restock():
    d = request.json
    if not q("SELECT 1 FROM Product WHERE Item_code=%s AND Supplier_ID=%s", (d["item_code"], session["uid"]), one=True):
        return fail("Not your product", 403)
    q("UPDATE Product SET Stock=Stock+%s, Expected_Date=%s WHERE Item_code=%s",
      (max(0, int(d.get("qty") or 0)), d.get("expected") or None, d["item_code"]), commit=True)
    allocate(d["item_code"])
    return jsonify(ok=True)

@app.post("/api/ban")
@need("admin")
def ban():
    d = request.json
    q("UPDATE Product SET Banned=%s WHERE Item_code=%s", (1 if d.get("banned") else 0, d["item_code"]), commit=True)
    return jsonify(ok=True)

@app.post("/api/category")
@need("admin")
def recategorise():
    d = request.json
    if not q("SELECT 1 FROM Category WHERE Category_name=%s", (d["category"],), one=True):
        return fail("No such category.")
    q("DELETE FROM Product_Category WHERE Item_code=%s", (d["item_code"],), commit=True)
    q("INSERT INTO Product_Category (Item_code, Category_name) VALUES (%s,%s)", (d["item_code"], d["category"]), commit=True)
    return jsonify(ok=True)

# ---------- cart ----------

@app.get("/api/cart")
@need("customer")
def cart():
    rows = q("""SELECT ci.Item_code, ci.Quantity, p.Item_name, p.Price, p.Stock, p.Banned,
                (SELECT COUNT(*) FROM Order_Item oi JOIN Orders o ON o.Order_ID=oi.Order_ID
                 WHERE oi.Item_code=p.Item_code AND o.Status='Waiting for stock') AS Queue
                FROM Cart_Item ci JOIN Product p ON p.Item_code=ci.Item_code
                WHERE ci.Customer_ID=%s AND ci.Cart_ID=1 ORDER BY p.Item_name""", (session["uid"],))
    for r in rows:
        r["Price"] = float(r["Price"])
        r["Ok"] = not r["Banned"] and r["Queue"] == 0 and r["Stock"] >= r["Quantity"]
    return jsonify(rows)

@app.post("/api/cart/add")
@need("customer")
def cart_add():
    d = request.json
    item, n, uid = int(d["item_code"]), max(1, int(d["qty"])), session["uid"]
    if not q("SELECT 1 FROM Product WHERE Item_code=%s AND Banned=0", (item,), one=True):
        return fail("No such product.", 404)
    q("INSERT IGNORE INTO Cart (Customer_ID, Cart_ID) VALUES (%s,1)", (uid,), commit=True)
    q("""INSERT INTO Cart_Item (Customer_ID, Cart_ID, Item_code, Quantity) VALUES (%s,1,%s,%s)
         ON DUPLICATE KEY UPDATE Quantity=Quantity+%s""", (uid, item, n, n), commit=True)
    return jsonify(ok=True)

@app.post("/api/cart/set")
@need("customer")
def cart_set():
    d = request.json
    item, n, uid = int(d["item_code"]), int(d["qty"]), session["uid"]
    if n < 1:
        q("DELETE FROM Cart_Item WHERE Customer_ID=%s AND Cart_ID=1 AND Item_code=%s", (uid, item), commit=True)
    else:
        q("UPDATE Cart_Item SET Quantity=%s WHERE Customer_ID=%s AND Cart_ID=1 AND Item_code=%s", (n, uid, item), commit=True)
    return jsonify(ok=True)

@app.post("/api/checkout")
@need("customer")
def checkout():
    uid = session["uid"]
    rows = q("SELECT Item_code, Quantity FROM Cart_Item WHERE Customer_ID=%s AND Cart_ID=1", (uid,))
    if not rows:
        return fail("Your cart is empty.")
    try:
        oid = buy(uid, {r["Item_code"]: r["Quantity"] for r in rows})
    except ValueError as e:
        return fail(str(e))
    q("DELETE FROM Cart_Item WHERE Customer_ID=%s AND Cart_ID=1", (uid,), commit=True)
    return jsonify(ok=True, order_id=oid)

# ---------- orders ----------

def order_rows(where="", args=()):
    rows = q("""SELECT o.Order_ID, o.Amount, o.Status, o.Reserved_Until, o.Created_At, o.Return_Reason, c.Name AS Customer
                FROM Orders o JOIN Customer c ON c.Customer_ID=o.Customer_ID""" + where + " ORDER BY o.Order_ID DESC", args)
    items = []
    if rows:
        ids = [r["Order_ID"] for r in rows]
        items = q("""SELECT oi.Order_ID, oi.Quantity, p.Item_code, p.Item_name, p.Price, p.Expected_Date
                     FROM Order_Item oi JOIN Product p ON p.Item_code=oi.Item_code
                     WHERE oi.Order_ID IN (%s)""" % ",".join(["%s"] * len(ids)), ids)
    for r in rows:
        r["Amount"] = float(r["Amount"])
        r["Reserved_Until"] = str(r["Reserved_Until"] or "")
        r["Created_At"] = str(r["Created_At"] or "")[:16]
        r["Items"] = [dict(i, Price=float(i["Price"]), Expected_Date=str(i["Expected_Date"] or "")) for i in items if i["Order_ID"] == r["Order_ID"]]
    return rows

@app.get("/api/orders")
@need("customer", "admin")
def orders():
    expire()
    if session["role"] == "customer":
        return jsonify(order_rows(" WHERE o.Customer_ID=%s", (session["uid"],)))
    return jsonify(order_rows())

@app.get("/api/order/<int:oid>")
@need("customer", "admin")
def one_order(oid):
    expire()
    if session["role"] == "customer":
        rows = order_rows(" WHERE o.Order_ID=%s AND o.Customer_ID=%s", (oid, session["uid"]))
    else:
        rows = order_rows(" WHERE o.Order_ID=%s", (oid,))
    return jsonify(rows[0]) if rows else fail("No order with that number.", 404)

@app.post("/api/buy")
@need("customer")
def buy_now():
    d = request.json
    try:
        oid = buy(session["uid"], {int(d["item_code"]): max(1, int(d["qty"]))})
    except ValueError as e:
        return fail(str(e))
    return jsonify(ok=True, order_id=oid)

@app.post("/api/preorder")
@need("customer")
def preorder():
    d = request.json
    item, n = int(d["item_code"]), max(1, int(d["qty"]))
    p = q("SELECT * FROM Product WHERE Item_code=%s AND Banned=0", (item,), one=True)
    if not p:
        return fail("No such product.", 404)
    queue = q("""SELECT 1 FROM Orders o JOIN Order_Item oi ON oi.Order_ID=o.Order_ID
                 WHERE oi.Item_code=%s AND o.Status='Waiting for stock' LIMIT 1""", (item,), one=True)
    if p["Stock"] >= n and not queue:
        return fail("That's in stock right now. Use Buy now or Add to cart.")
    oid = nid("Orders", "Order_ID")
    q("INSERT INTO Orders (Order_ID, Amount, Status, Customer_ID, Created_At) VALUES (%s,%s,'Waiting for stock',%s,%s)",
      (oid, p["Price"] * n, session["uid"], datetime.now()), commit=True)
    q("INSERT INTO Order_Item (Order_ID, Item_code, Quantity) VALUES (%s,%s,%s)", (oid, item, n), commit=True)
    q("INSERT INTO Backorder (Order_ID, Item_code, Expected_Date) VALUES (%s,%s,%s)", (oid, item, p["Expected_Date"]), commit=True)
    return jsonify(ok=True, order_id=oid)

@app.post("/api/pay/<int:oid>")
@need("customer")
def pay(oid):
    expire()
    o = q("SELECT * FROM Orders WHERE Order_ID=%s AND Customer_ID=%s", (oid, session["uid"]), one=True)
    if not o or o["Status"] != "Reserved":
        return fail("This order can't be paid: it has expired or is still waiting for stock.")
    q("UPDATE Orders SET Status='Paid' WHERE Order_ID=%s", (oid,), commit=True)
    q("INSERT INTO Payment (Order_ID, Payment_ID, Amount, Customer_ID) VALUES (%s,1,%s,%s)", (oid, o["Amount"], o["Customer_ID"]), commit=True)
    return jsonify(ok=True)

@app.post("/api/cancel/<int:oid>")
@need("customer", "admin")
def cancel(oid):
    if session["role"] == "customer" and not q("SELECT 1 FROM Orders WHERE Order_ID=%s AND Customer_ID=%s", (oid, session["uid"]), one=True):
        return fail("Not your order", 403)
    return jsonify(ok=cancel_order(oid))

@app.post("/api/order/<int:oid>/advance")
@need("admin")
def advance(oid):
    o = q("SELECT Status, Customer_ID FROM Orders WHERE Order_ID=%s", (oid,), one=True)
    if not o or o["Status"] not in NEXT:
        return fail("This order can't move to the next step.")
    new = NEXT[o["Status"]]
    delivered_to = o["Customer_ID"] if new == "Delivered" else None
    q("UPDATE Orders SET Status=%s, Admin_ID=%s, Delivered_To_ID=COALESCE(%s, Delivered_To_ID) WHERE Order_ID=%s",
      (new, session["uid"], delivered_to, oid), commit=True)
    return jsonify(ok=True, status=new)

@app.post("/api/return/<int:oid>")
@need("customer")
def request_return(oid):
    reason = (request.json.get("reason") or "").strip()[:250]
    if not reason:
        return fail("Tell us why you're returning it.")
    n = q("""UPDATE Orders SET Status='Return requested', Returned_By_ID=%s, Return_Reason=%s
             WHERE Order_ID=%s AND Customer_ID=%s AND Status='Delivered'""", (session["uid"], reason, oid, session["uid"]), commit=True)
    if not n:
        return fail("Only delivered orders can be returned.")
    return jsonify(ok=True)

@app.post("/api/return/<int:oid>/decide")
@need("admin")
def decide(oid):
    approve = bool(request.json.get("approve"))
    o = q("SELECT Status, Customer_ID FROM Orders WHERE Order_ID=%s", (oid,), one=True)
    if not o or o["Status"] != "Return requested":
        return fail("There's no return request on this order.")
    if approve:
        items = q("SELECT Item_code, Quantity FROM Order_Item WHERE Order_ID=%s", (oid,))
        q("UPDATE Orders SET Status='Returned', Admin_ID=%s WHERE Order_ID=%s", (session["uid"], oid), commit=True)
        q("UPDATE Payment SET Refunded_To_ID=%s WHERE Order_ID=%s", (o["Customer_ID"], oid), commit=True)
        for i in items:  # returned goods go back on the shelf, and the pre-order queue gets first pick
            q("UPDATE Product SET Stock=Stock+%s WHERE Item_code=%s", (i["Quantity"], i["Item_code"]), commit=True)
            allocate(i["Item_code"])
    else:
        q("UPDATE Orders SET Status='Delivered', Returned_By_ID=NULL, Return_Reason=NULL, Admin_ID=%s WHERE Order_ID=%s",
          (session["uid"], oid), commit=True)
    return jsonify(ok=True)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")