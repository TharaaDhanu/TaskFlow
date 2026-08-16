# TaskFlow — Full-Stack Task Management Application

TaskFlow is a real-world full-stack task management application built with a React-based frontend and a Python Flask REST API backend.

It provides user authentication, project management, task management, role-based access control, dashboard statistics, and database persistence.

## 🚀 Features

- User registration and login
- JWT-based authentication
- Password hashing with Werkzeug
- Role-based access control
- Project creation, updating, and deletion
- Task creation, updating, filtering, and deletion
- Task assignment to workspace users
- Task status and priority management
- Dashboard project and task statistics
- SQLite database persistence
- SQLAlchemy ORM
- RESTful API architecture
- CORS support for frontend/backend communication
- Automated backend integration testing
- Responsive frontend interface

## 🛠️ Technologies Used

### Frontend
- HTML
- CSS
- JavaScript
- React

### Backend
- Python 3
- Flask
- Flask-CORS
- Flask-SQLAlchemy
- PyJWT
- Werkzeug

### Database
- SQLite

### Testing
- Python Requests
- Custom backend integration test suite

## 📁 Project Structure

```text
PROJECT3_TASKFLOW/
│
├── backend/
│   └── app.py
│
├── frontend/
│   └── index.html
│
├── tests/
│   └── backend_integration_test_script.py
│
├── instance/
│   └── taskflow.db
│
├── .gitignore
├── LICENSE
└── README.md