# test_mongo_images.py
from pymongo import MongoClient

mongo_uri = "mongodb+srv://<abhishek>:<hardik>@cluster0.mongodb.net/mydb?retryWrites=true&w=majority&tls=true"

client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
client.server_info()
   
db = client["bhushuraksha"]
detections = db["detections"]

detections.delete_many({})

