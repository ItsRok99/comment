from fastapi import FastAPI, HTTPException, Response, Depends, Form, Body, status, Header, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pymongo import MongoClient
from pydantic import BaseModel, Field
from typing import List, Optional
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
import uuid
import jwt
import httpx
from datetime import datetime
import rabbitpy
import requests
import os
import certifi

# pozeni kodo s tem: uvicorn main:app --host 0.0.0.0 --port 8001

ca = certifi.where()

# Function to log messages to RabbitMQ
def logMessageToRabbitMQ(correlationId, message, logType, url, applicationName):
    rabbit_conn = None
    rabbit_channel = None
    try:
        # RabbitMQ setup
        rabbitUser = "student"
        rabbitPassword = "student123"
        rabbitHost = "studentdocker.informatika.uni-mb.si"
        rabbitPort = "5672"
        vhost = ""
        amqpUrl = f"amqp://{rabbitUser}:{rabbitPassword}@{rabbitHost}:{rabbitPort}/{vhost}"
        exchange = 'upp-3'
        routingKey = 'zelovarnikey'
        # Connect to RabbitMQ
        rabbit_conn = rabbitpy.Connection(amqpUrl)
        rabbit_channel = rabbit_conn.channel()

        msg = f"{datetime.now().isoformat()} {logType} {url} Correlation: {correlationId} [{applicationName}] - {message}"

        message = rabbitpy.Message(rabbit_channel, msg)

        # Declare the exchange
        exchange = rabbitpy.Exchange(rabbit_channel, exchange, exchange_type='direct', durable=True)
        exchange.declare()

        # Send the message
        message.publish(exchange, routing_key=routingKey)

        print(f" [x] Sent {msg}")

    except Exception as e:
        print(f"Failed to send message: {str(e)}")

    finally:
        if rabbit_channel:
            rabbit_channel.close()
        if rabbit_conn:
            rabbit_conn.close()

# Function to send statistics
async def sendStatistics(data):
    try:
        response = requests.post('https://statistics-app-cc50d2934119.herokuapp.com/add-statistic', data)
        # axios.post('https://statistics-app-cc50d2934119.herokuapp.com/add-statistic', { service: "Product", endpoint: "create" })
        print(response.json())
    except Exception as error:
        print(f"Error sending statistics: {str(error)}")


app = FastAPI()

# MongoDB setup
client = MongoClient("mongodb+srv://Rok:Feri123!@cluster0.bkl6gj5.mongodb.net/comment", tlsCAFile=ca)
db = client["commentsDB"]
collection = db["comments"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class CommentUpdate(BaseModel):
    subject: str
    text: str

class Comment(BaseModel):
    subject: str
    text: str
    userid: str

class CommentWithID(Comment):
    id: str

SECRET_KEY = 'SUPER_STRONG_SECRET_BY_JAN'

def get_token_from_header(request: Request):
    auth_header: Optional[str] = request.headers.get('authorization')
    if auth_header is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    return auth_header.split(' ')[1]

def jwt_auth(token: str = Depends(get_token_from_header)):
    try:
        jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=403, detail='Invalid token')

@app.on_event("startup")
async def startup_event():
    openapi_schema = app.openapi()
    openapi_schema['components']['securitySchemes'] = {
        'bearerAuth': {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
        }
    }
    openapi_schema['security'] = [{'bearerAuth': []}]
    app.openapi_schema = openapi_schema

#Create a comment
@app.post("/comments/", response_model=CommentWithID, dependencies=[Depends(jwt_auth)])
async def create_comment(comment: Comment):
    # Generate correlationId
    correlationId = str(uuid.uuid4())

    # Log message and send statistics
    logMessageToRabbitMQ(correlationId, "Received a request to create a comment", "INFO", "/comments/", "comment-service")
    await sendStatistics({
        'service': 'comment-service',
        'endpoint': '/comments/',
        'method': 'POST',
        'timestamp': datetime.now().isoformat()
    })

    comment_id = str(uuid.uuid4())
    comment_data = comment.dict(by_alias=True)
    comment_data["id"] = comment_id

    # Make an HTTP request to get the users data
    async with httpx.AsyncClient() as client:
        response = await client.get("http://127.0.0.1:8000/users/")

    # Check if the specified user_id exists in the response data
    users_data = response.json()
    user_exists = any(user["id"] == comment.userid for user in users_data)

    if not user_exists:
        raise HTTPException(status_code=404, detail="User not found")

    result = collection.insert_one(comment_data)

    return CommentWithID(**comment.dict(), id=comment_id)

@app.get("/comments/", response_model=List[CommentWithID], dependencies=[Depends(jwt_auth)])
async def read_comments():
    # Generate correlationId
    correlationId = str(uuid.uuid4())

    # Log message and send statistics
    logMessageToRabbitMQ(correlationId, "Received a request to read comments", "INFO", "/comments/", "comment-service")
    await sendStatistics({
        'service': 'comment-service',
        'endpoint': '/comments/',
        'method': 'GET',
        'timestamp': datetime.now().isoformat()
    })

    comments = list(collection.find())
    return [CommentWithID(**comment) for comment in comments]


@app.get("/comments/{comment_id}", response_model=CommentWithID, dependencies=[Depends(jwt_auth)])
async def get_comment(comment_id: str):
    # Generate correlationId
    correlationId = str(uuid.uuid4())

    # Log message and send statistics
    logMessageToRabbitMQ(correlationId, "Received a request to get a comment", "INFO", f"/comments/{comment_id}", "comment-service")
    await sendStatistics({
        'service': 'comment-service',
        'endpoint': f"/comments/{comment_id}",
        'method': 'GET',
        'timestamp': datetime.now().isoformat()
    })

    comment = collection.find_one({"id": comment_id})
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    return comment

@app.delete("/comments/{comment_id}", response_model=str, dependencies=[Depends(jwt_auth)])
async def delete_comment(comment_id: str):
    # Generate correlationId
    correlationId = str(uuid.uuid4())

    # Log message and send statistics
    logMessageToRabbitMQ(correlationId, "Received a request to delete a comment", "INFO", f"/comments/{comment_id}", "comment-service")
    await sendStatistics({
        'service': 'comment-service',
        'endpoint': f"/comments/{comment_id}",
        'method': 'DELETE',
        'timestamp': datetime.now().isoformat()
    })

    result = collection.delete_one({"id": comment_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Comment not found")
    return f"Comment with ID {comment_id} deleted successfully"

@app.delete("/comments/", response_model=str, dependencies=[Depends(jwt_auth)])
async def delete_all_comments():
    # Generate correlationId
    correlationId = str(uuid.uuid4())

    # Log message and send statistics
    logMessageToRabbitMQ(correlationId, "Received a request to delete all comments", "INFO", "/comments/", "comment-service")
    await sendStatistics({
        'service': 'comment-service',
        'endpoint': "/comments/",
        'method': 'DELETE',
        'timestamp': datetime.now().isoformat()
    })

    result = collection.delete_many({})
    return f"{result.deleted_count} comments deleted successfully"

@app.put("/comments/{comment_id}", response_model=CommentWithID, dependencies=[Depends(jwt_auth)])
async def update_comment(comment_id: str, updated_comment: CommentUpdate):
    # Generate correlationId
    correlationId = str(uuid.uuid4())

    # Log message and send statistics
    logMessageToRabbitMQ(correlationId, "Received a request to update a comment", "INFO", f"/comments/{comment_id}", "comment-service")
    await sendStatistics({
        'service': 'comment-service',
        'endpoint': f"/comments/{comment_id}",
        'method': 'PUT',
        'timestamp': datetime.now().isoformat()
    })

    existing_comment = collection.find_one({"id": comment_id})
    if not existing_comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    comment_data = updated_comment.dict(by_alias=True)
    comment_data.pop("id", None)

    # Make an HTTP request to get the users data
    async with httpx.AsyncClient() as client:
        response = await client.get("http://127.0.0.1:8000/users/")

    # Check if the specified user_id exists in the response data
    users_data = response.json()
    user_exists = any(user["id"] == existing_comment["userid"] for user in users_data)

    if not user_exists:
        raise HTTPException(status_code=404, detail="User not found")

    result = collection.update_one({"id": comment_id}, {"$set": comment_data})

    if result.modified_count > 0:
        return CommentWithID(id=comment_id, userid=existing_comment["userid"], **comment_data)

    raise HTTPException(status_code=500, detail="Failed to update comment")


@app.get("/", include_in_schema=False)
def redirect_to_docs():
    return Response(content="", media_type="text/html", headers={"Location": "/docs"})
