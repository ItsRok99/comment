from fastapi.testclient import TestClient
from main import app
from main import Comment, CommentUpdate
import pytest
from pydantic import UUID4

client = TestClient(app)

# Test data
test_comment = {
    "subject": "Test subject",
    "text": "Test text",
    "userid": "test_userid"
}

test_comment_update = {
    "subject": "Test subject updated",
    "text": "Test text updated",
}

def test_create_comment():
    response = client.post("/comments/", json=test_comment)
    assert response.status_code == 200
    assert response.json()["subject"] == "Test subject"

def test_read_comments():
    response = client.get("/comments/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_comment():
    # Here we need an existing comment id, for simplicity, I'm using a random UUID.
    comment_id = UUID4()
    response = client.get(f"/comments/{comment_id}")
    assert response.status_code == 404

def test_update_comment():
    # Here we need an existing comment id, for simplicity, I'm using a random UUID.
    comment_id = UUID4()
    response = client.put(f"/comments/{comment_id}", json=test_comment_update)
    assert response.status_code == 404

def test_delete_comment():
    # Here we need an existing comment id, for simplicity, I'm using a random UUID.
    comment_id = UUID4()
    response = client.delete(f"/comments/{comment_id}")
    assert response.status_code == 404

def test_delete_all_comments():
    response = client.delete("/comments/")
    assert response.status_code == 200
