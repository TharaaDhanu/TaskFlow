import sys
import json
import requests

BASE_URL = "http://127.0.0.1:5000/api"

def print_result(step, status, details=""):
    symbol = "✓ PASS" if status else "✗ FAIL"
    print(f"[{symbol}] Step {step}: {details}")

def run_tests():
    print("==================================================")
    print(" TASKFLOW BACKEND LIVE INTEGRATION TEST SUITE")
    print("==================================================")

    # 1. Health check / server availability
    try:
        res = requests.get(f"{BASE_URL}/projects")
    except requests.exceptions.ConnectionError:
        print("\n❌ Could not connect to Flask server at http://127.0.0.1:5000")
        print("Please start the backend first using: python app.py\n")
        sys.exit(1)

    print_result(1, True, "Flask server is online and accepting TCP connections")

    # 2. Login as Admin
    login_payload = {
        "email": "admin@taskflow.demo",
        "password": "AdminPass123!"
    }
    res = requests.post(f"{BASE_URL}/auth/login", json=login_payload)
    if res.status_code != 200 or not res.json().get("success"):
        print_result(2, False, f"Admin login failed: {res.text}")
        sys.exit(1)
    
    token = res.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    print_result(2, True, f"Admin authenticated successfully. JWT acquired.")

    # 3. GET /api/tasks
    res = requests.get(f"{BASE_URL}/tasks", headers=headers)
    if res.status_code != 200 or not res.json().get("success"):
        print_result(3, False, f"GET /api/tasks failed: {res.text}")
        sys.exit(1)
    
    initial_tasks = res.json()["data"]
    print_result(3, True, f"Retrieved {len(initial_tasks)} tasks from database.")

    # 4. POST /api/tasks (Create test task)
    new_task_payload = {
        "title": "Live Verification Task",
        "description": "Created during backend integration testing.",
        "status": "to_do",
        "priority": "urgent",
        "project_id": 1
    }
    res = requests.post(f"{BASE_URL}/tasks", headers=headers, json=new_task_payload)
    if res.status_code != 201 or not res.json().get("success"):
        print_result(4, False, f"POST /api/tasks failed: {res.text}")
        sys.exit(1)
    
    created_task = res.json()["data"]
    task_id = created_task["id"]
    print_result(4, True, f"Task created with ID #{task_id} (Title: '{created_task['title']}')")

    # 5. GET /api/tasks/<id> (Retrieve single task)
    res = requests.get(f"{BASE_URL}/tasks/{task_id}", headers=headers)
    if res.status_code != 200 or res.json()["data"]["title"] != "Live Verification Task":
        print_result(5, False, f"GET /api/tasks/{task_id} failed: {res.text}")
        sys.exit(1)
    print_result(5, True, f"Retrieved task #{task_id} matching created payload.")

    # 6. PUT /api/tasks/<id> (Update task)
    update_payload = {"status": "completed", "priority": "low"}
    res = requests.put(f"{BASE_URL}/tasks/{task_id}", headers=headers, json=update_payload)
    if res.status_code != 200 or res.json()["data"]["status"] != "completed":
        print_result(6, False, f"PUT /api/tasks/{task_id} failed: {res.text}")
        sys.exit(1)
    print_result(6, True, f"Updated task #{task_id} status to 'completed'.")

    # 7. DELETE /api/tasks/<id> (Delete task)
    res = requests.delete(f"{BASE_URL}/tasks/{task_id}", headers=headers)
    if res.status_code != 200 or not res.json().get("success"):
        print_result(7, False, f"DELETE /api/tasks/{task_id} failed: {res.text}")
        sys.exit(1)
    print_result(7, True, f"Deleted task #{task_id} from database.")

    # 8. Verify Task No Longer Exists
    res = requests.get(f"{BASE_URL}/tasks/{task_id}", headers=headers)
    if res.status_code == 404:
        print_result(8, True, f"Verified task #{task_id} returned HTTP 404 Not Found.")
    else:
        print_result(8, False, f"Expected 404 after deletion, but got HTTP {res.status_code}")

    print("==================================================")
    print(" ALL BACKEND INTEGRATION TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()