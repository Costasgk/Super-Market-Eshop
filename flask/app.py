from json.decoder import JSONDecoder
from re import I, search
from flask.json import JSONEncoder
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from flask import Flask, request, jsonify, redirect, Response
import json, os
import uuid
import time
from bson.objectid import ObjectId

# Connect to our local MongoDB
mongodb_hostname = os.environ.get("MONGO_HOSTNAME","localhost")
client = MongoClient('mongodb://'+mongodb_hostname+':27017/')

# Choose database
db = client['DSMarkets'] 

# Choose collections
users = db['Users']
products = db['Products']

# Initiate Flask App
app = Flask(__name__)

users_sessions = {}

basket = []

def create_session(email):
    user_uuid = str(uuid.uuid1())
    users_sessions[user_uuid] = (email, time.time())
    return user_uuid  

def is_session_valid(user_uuid):
    return user_uuid in users_sessions


# =================================== ΑΠΛΟΣ ΧΡΗΣΤΗΣ ===================================

# 1ο ENDPOINT : Εισαγωγή χρηστών στο σύστημα
@app.route('/createUser', methods=['POST'])
def create_user():
    # Request JSON data
    data = None
    try:
        data = json.loads(request.data)
    except Exception as e:
        return Response("bad json content",status=500,mimetype='application/json')
    if data == None:
        return Response("bad request",status=500,mimetype='application/json')
    if not "email" in data or not "name" in data or not "password" in data:
        return Response("Information incomplete",status=500,mimetype="application/json")

    if users.find({"email":data['email']}).count() == 0:
        user = {"email":data['email'], "name":data['name'], "password":data['password'], "category":"Simple Costumer"}
        users.insert_one(user)
        return Response(data['name']+" was added to the MongoDB",status=200,mimetype='application/json') 
    else:
        return Response("A user with the given email already exists",status=400,mimetype='application/json')


# 2o ENDPOINT: Login στο σύστημα
@app.route('/login', methods = ['POST'])
def login():
    # Request JSON data
    data = None
    try:
        data = json.loads(request.data)
    except Exception as e:
        return Response("bad json content",status=500,mimetype='application/json')
    if data == None:
        return Response("bad request",status=500,mimetype='application/json')
    if not "email" in data or not "password" in data:
        return Response("Information incomplete",status=500,mimetype="application/json")

    if users.find_one({"email":data['email'],"password":data['password']}):
        user_uuid = create_session(data['email'])
        res = {"uuid": user_uuid, "email":data['email']}
        return Response(json.dumps(res),status=200,mimetype='application/json')
    else:
        return Response("Wrong email or password", status=400,mimetype='application/json')


# 3o ENDPOINT: Επιστροφή προϊόντος με βάσει όνομα, κατηγορία, ID
@app.route('/getProducts', methods = ['GET'])
def get_products():
    # Request JSON data
    data = None 
    try:
        data = json.loads(request.data)
    except Exception as e:
        return Response("bad json content",status=500,mimetype='application/json')
    if data == None:
        return Response("bad request",status=500,mimetype='application/json')

    uuid = request.headers.get('authorization')
    if is_session_valid(uuid):
        if "name" in data:
            product = products.find({"name":data['name']})
            productsList = [] 
            if product != None:
                    for item in product:
                        productsList.append(item)
                    sortedproductList = sorted(productsList, key = lambda x: x['name'])
                    return Response(json.dumps(sortedproductList,default=str), status=200, mimetype='application/json')
            else:
                return Response("No product with the given name was found",status=400,mimetype='application/json')
        if "category" in data:
            category = products.find({"category":data['category']})
            categoryList = []
            if category != None:
                for item in category:
                    categoryList.append(item)
                sortedcategoryList = sorted(categoryList, key = lambda x: x['price'])
                return Response(json.dumps(sortedcategoryList,default=str), status=200, mimetype='application/json')
            else:
                return Response("No product of the given category was found",status=400,mimetype='application/json')
        if "_id" in data:
            byID = products.find({"_id": ObjectId(data['_id'])})
            byIDList = []
            if byID != None:
                for item in byID:
                    byIDList.append(item)
                return Response(json.dumps(byIDList,default=str), status=200, mimetype='application/json')
            else:
                return Response("No product with the given ID was found",status=400,mimetype='application/json')
    else:
        return Response("The session is not valid",status=401,mimetype='application/json')

# 4o ENDPOINT: Προσθήκη προϊόντων στο καλάθι
@app.route('/addProducts', methods = ['PATCH'])
def add_products():
    # Request JSON data
    data = None
    try:
        data = json.loads(request.data)
    except Exception as e:
        return Response("bad json content",status=500,mimetype='application/json')
    if data == None:
        return Response("bad request",status=500,mimetype='application/json')
    if not "_id" in data or not "quantity" in data:
        return Response("Information incomplete",status=500,mimetype="application/json")
    
    uuid = request.headers.get('authorization')
    if is_session_valid(uuid):
        product = products.find_one({"_id":ObjectId(data['_id'])})
        if data['quantity'] < product['stock']:
            del product['stock']
            product.update({"quantity": data['quantity']})
            basket.append(product)
            total = sum(d["price"] * d["quantity"] for d in basket)
            msg1 = ("Your basket is: ",basket)
            msg2 = ("And the total amount is", total)
            msg3 = msg1 + msg2
            return Response(json.dumps(msg3,default=str), status=200, mimetype='application/json')
        if data['quantity'] > product['stock']:
            return Response("The quantity you want to buy is more than we have in stocks",status=401,mimetype='application/json')
        else:
            return Response("No product was found",status=401,mimetype='application/json')
    else:
        return Response("The session is not valid",status=401,mimetype='application/json')

# 5o ENDPOINT: Εμφάνιση καλαθιού
@app.route('/getBasket', methods=['GET'])
def get_basket():
    uuid = request.headers.get('authorization')
    if is_session_valid(uuid):
        total = sum(d["price"] * d["quantity"] for d in basket)
        msg1 = ("Your basket: ",basket)
        msg2 = ("The total cost: ", total)
        msg3 = msg1 + msg2
        return Response(json.dumps(msg3,default=str), status=200, mimetype='application/json') 
    else:
        return Response("The session is not valid",status=401,mimetype='application/json')

# 6o ENDPOINT: Διαγραφή προϊόντος από το καλάθι.
@app.route('/deleteBasketProduct', methods=['DELETE'])
def delete_basket_product():
    # Request JSON data
    data = None
    try:
        data = json.loads(request.data)
    except Exception as e:
        return Response("bad json content",status=500,mimetype='application/json')
    if data == None:
        return Response("bad request",status=500,mimetype='application/json')
    if not "_id" in data:
        return Response("Information incomplete",status=500,mimetype="application/json")

    uuid = request.headers.get('authorization')
    if is_session_valid(uuid):
        for d in basket:
            if ObjectId(data['_id']) == d['_id']:
                basket.remove(d)
        total = sum(d["price"]*d["quantity"] for d in basket)
        msg1 = ("Your basket: ",basket)
        msg2 = ("And the total amount is", total)
        msg3 = msg1 + msg2
        return Response(json.dumps(msg3,default=str), status=200, mimetype='application/json')
    else:
        return Response("The session is not valid",status=401,mimetype='application/json')

# 7o ENDPOINT: Αγορά προϊόντων
@app.route('/buyProduct', methods = ['GET'])
def buy_product():
    data = None
    try:
        data = json.loads(request.data)
    except Exception as e:
        return Response("bad json content",status=500,mimetype='application/json')
    if data == None:
        return Response("bad request",status=500,mimetype='application/json')
    if not "_id" in data or not "debit_card_number" in data:
        return Response("Information incomplete",status=500,mimetype="application/json")

    uuid = request.headers.get('authorization')
    if is_session_valid(uuid):
        user = users.find_one({"_id": ObjectId(data['_id'])})
        if user != None:
            if len(data['debit_card_number']) == 16:
                users.update({"_id": ObjectId(data['_id'])}, {"$set":{"orderHistory": basket}}) 
                recipt = basket
                total = sum(d["price"] * d["quantity"] for d in recipt)
                msg1 = ("Purchase: ",recipt)
                msg2 = ("Total cost: ", total)
                msg3 = msg1 + msg2
                return Response(json.dumps(msg3,default=str), status=200, mimetype='application/json')
            else:
                return Response("Invalid debit card number",status=400,mimetype='application/json')
        else:
            return Response("No user was found",status=400,mimetype='application/json')
    else:
        return Response("The session is not valid",status=401,mimetype='application/json')


# 8o ENDPOINT: Εμφάνιση ιστορικού παραγγελιών του συγκεκριμένου χρήστη.
@app.route('/getOrderHistory', methods=['GET'])
def get_order_history():
    data = None
    try:
        data = json.loads(request.data)
    except Exception as e:
        return Response("bad json content",status=500,mimetype='application/json')
    if data == None:
        return Response("bad request",status=500,mimetype='application/json')
    if not "_id" in data:
        return Response("Information incomplete",status=500,mimetype="application/json")
         
         
    uuid = request.headers.get('authorization')
    if is_session_valid(uuid):
        user = users.find_one({"$and":[{"_id":ObjectId(data['_id'])}, {"orderHistory":{"$exists":True}}]})
        if user != None:
            orderHistory = user['orderHistory']
            return Response(json.dumps(orderHistory,default=str), status=200, mimetype='application/json')
        else:
            return Response("No user was found",status=400,mimetype='application/json')
    else:
        return Response("The session is not valid",status=401,mimetype='application/json')

# 9o ENDPOINT: Διαγραφή του λογαριασμού
@app.route('/deleteUser', methods=['DELETE'])
def delete_user():
    data = None
    try:
        data = json.loads(request.data)
    except Exception as e:
        return Response("bad json content",status=500,mimetype='application/json')
    if data == None:
        return Response("bad request",status=500,mimetype='application/json')
    if not "_id" in data:
        return Response("Information incomplete",status=500,mimetype="application/json")

    uuid = request.headers.get('authorization')
    if is_session_valid(uuid):
        user = users.find_one({"_id": ObjectId(data['_id'])})
        if user != None:
            users.delete_one({"_id": ObjectId(user['_id'])})
            msg = user['name'] + " was deleted"
            return Response(msg, status=200, mimetype='application/json')
        else:
            return Response("Student was not found",status=400,mimetype='application/json')     
    else:
        return Response("The session is not valid",status=401,mimetype='application/json')
        

# =================================== ΔΙΑΧΕΙΡΙΣΤΗΣ ===================================

# 1o ENDPOINT: Εισαγωγή νέου προϊόντος
@app.route('/insertProduct', methods = ['POST'])
def insert_product():
    # Request JSON data
    data = None
    try:
        data = json.loads(request.data)
    except Exception as e:
        return Response("bad json content",status=500,mimetype='application/json')
    if data == None:
        return Response("bad request",status=500,mimetype='application/json')
    if not "name" in data or not "category" in data or not "description" in data or not "price" in data or not "stock" in data : 
        return Response("Information incomplete",status=500,mimetype="application/json")

    product = {"name":data['name'], "category":data['category'], "description":data['description'], "price":data['price'], "stock": data['stock']}
    products.insert_one(product)

    return Response(data['name']+" was added",status=200,mimetype='application/json')

# 2o ENDPOINT: Διαγραφή προϊόντος από το σύστημα
@app.route('/deleteProduct', methods = ['DELETE'])
def delete_product():
    # Request JSON data
    data = None
    try:
        data = json.loads(request.data)
    except Exception as e:
        return Response("bad json content",status=500,mimetype='application/json')
    if data == None:
        return Response("bad request",status=500,mimetype='application/json')
    if not "_id" in data:
        return Response("Information incomplete",status=500,mimetype="application/json")

    product = products.find_one({"_id": ObjectId(data['_id'])})
    if product != None:
        products.delete_one({"_id": ObjectId(product['_id'])})
        return Response("The product was successfully deleted",status=200, mimetype='application/json')
    else:
        return Response("Product was not found",status=400, mimetype='application/json')

# 3o ENDPOINT: Ενημέρωση κάποιου προϊόντος
@app.route('/updateProduct', methods=['PATCH'])
def update_product():
    # Request JSON data
    data = None
    try:
        data = json.loads(request.data)
    except Exception as e:
        return Response("bad json content",status=500,mimetype='application/json')
    if data == None:
        return Response("bad request",status=500,mimetype='application/json')
    if not "_id" in data:
        return Response("Information incomplete",status=500,mimetype="application/json")

    product = products.find_one({"_id": ObjectId(data['_id'])})
    if product != None:
        if "name" in data:
            products.update_one({"_id": ObjectId(data['_id'])}, {"$set":{"name": data['name']}}) 
        if "price" in data:
            products.update_one({"_id": ObjectId(data['_id'])}, {"$set":{"price": data['price']}}) 
        if "description" in data:
            products.update_one({"_id": ObjectId(data['_id'])}, {"$set":{"description": data['description']}}) 
        if "stock" in data:
            products.update_one({"_id": ObjectId(data['_id'])}, {"$set":{"stock": data['stock']}}) 
        return Response("The product was successfully updated",status=200, mimetype='application/json')
    else:
        return Response("Product was not found",status=400, mimetype='application/json')

# Εκτέλεση flask service σε debug mode, στην port 5000. 
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)