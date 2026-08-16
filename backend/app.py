import os
import datetime
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import jwt

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-taskflow-secret-key-change-in-prod')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///taskflow.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Enable CORS for local API access
CORS(app, resources={r"/api/*": {"origins": "*"}})
db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user') # 'admin' or 'user'
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    # Relationships
    owned_projects = db.relationship('Project', backref='owner', lazy=True)
    assigned_tasks = db.relationship('Task', foreign_keys='Task.assigned_to', backref='assignee', lazy=True)
    created_tasks = db.relationship('Task', foreign_keys='Task.created_by', backref='creator', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Project(db.Model):
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), nullable=False, default='active') # 'planning', 'active', 'completed', 'on_hold'
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Cascade delete tasks on project removal
    tasks = db.relationship('Task', backref='project', cascade='all, delete-orphan', lazy=True)

    def to_dict(self):
        total_tasks = len(self.tasks)
        completed_tasks = sum(1 for t in self.tasks if t.status == 'completed')
        progress = round((completed_tasks / total_tasks * 100)) if total_tasks > 0 else 0

        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'status': self.status,
            'owner_id': self.owner_id,
            'owner_name': self.owner.name if self.owner else 'Unknown',
            'task_count': total_tasks,
            'completed_task_count': completed_tasks,
            'progress': progress,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), nullable=False, default='to_do') # 'to_do', 'in_progress', 'review', 'completed'
    priority = db.Column(db.String(20), nullable=False, default='medium') # 'low', 'medium', 'high', 'urgent'
    due_date = db.Column(db.String(10), nullable=True) # YYYY-MM-DD
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'priority': self.priority,
            'due_date': self.due_date,
            'project_id': self.project_id,
            'project_name': self.project.name if self.project else 'Unknown',
            'assigned_to': self.assigned_to,
            'assignee_name': self.assignee.name if self.assignee else 'Unassigned',
            'created_by': self.created_by,
            'creator_name': self.creator.name if self.creator else 'Unknown',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

def make_response(data=None, error=None, status_code=200):
    if error:
        return jsonify({"success": False, "error": error}), status_code
    return jsonify({"success": True, "data": data}), status_code

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                token = parts[1].strip().strip("'\"")

        if not token:
            return make_response(error={"code": "UNAUTHORIZED", "message": "Authentication token missing"}, status_code=401)

        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            user_id = payload.get('sub')
            current_user = db.session.get(User, int(user_id)) if user_id else None
            if not current_user:
                return make_response(error={"code": "UNAUTHORIZED", "message": "Invalid authentication token"}, status_code=401)
        except jwt.ExpiredSignatureError:
            return make_response(error={"code": "UNAUTHORIZED", "message": "Authentication token expired"}, status_code=401)
        except jwt.InvalidTokenError as e:
            return make_response(error={"code": "UNAUTHORIZED", "message": f"Could not validate authentication token: {str(e)}"}, status_code=401)
        except Exception as e:
            return make_response(error={"code": "UNAUTHORIZED", "message": f"Could not validate authentication token: {str(e)}"}, status_code=401)

        return f(current_user, *args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(current_user, *args, **kwargs):
        if current_user.role != 'admin':
            return make_response(error={"code": "FORBIDDEN", "message": "Admin privileges required for this action"}, status_code=403)
        return f(current_user, *args, **kwargs)
    return decorated

@app.route("/")
def home():
    return send_from_directory(
    os.path.join(os.path.dirname(__file__), "..", "frontend"),
    "index.html"
)

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not name or not email or not password:
        return make_response(error={"code": "VALIDATION_ERROR", "message": "Name, email, and password are required"}, status_code=400)

    if User.query.filter_by(email=email).first():
        return make_response(error={"code": "DUPLICATE_EMAIL", "message": "An account with this email already exists"}, status_code=409)

    user = User(name=name, email=email, role='user')
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = jwt.encode({
        'sub': str(user.id),
        'role': user.role,
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
    }, app.config['SECRET_KEY'], algorithm="HS256")
    
    if isinstance(token, bytes):
        token = token.decode('utf-8')

    return make_response(data={"token": token, "user": user.to_dict()}, status_code=201)

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return make_response(error={"code": "VALIDATION_ERROR", "message": "Email and password are required"}, status_code=400)

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return make_response(error={"code": "INVALID_CREDENTIALS", "message": "Invalid email or password"}, status_code=401)

    token = jwt.encode({
        'sub': str(user.id),
        'role': user.role,
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
    }, app.config['SECRET_KEY'], algorithm="HS256")

    if isinstance(token, bytes):
        token = token.decode('utf-8')

    return make_response(data={"token": token, "user": user.to_dict()})

@app.route('/api/auth/me', methods=['GET'])
@token_required
def get_current_user(current_user):
    return make_response(data=current_user.to_dict())

@app.route('/api/projects', methods=['GET'])
@token_required
def get_projects(current_user):
    projects = Project.query.all()
    return make_response(data=[p.to_dict() for p in projects])

@app.route('/api/projects/<int:project_id>', methods=['GET'])
@token_required
def get_project(current_user, project_id):
    project = Project.query.get(project_id)
    if not project:
        return make_response(error={"code": "NOT_FOUND", "message": "Project not found"}, status_code=404)
    return make_response(data=project.to_dict())

@app.route('/api/projects', methods=['POST'])
@token_required
@admin_required
def create_project(current_user):
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    status = data.get('status', 'active')

    if not name:
        return make_response(error={"code": "VALIDATION_ERROR", "message": "Project name is required"}, status_code=400)

    project = Project(
        name=name,
        description=description,
        status=status,
        owner_id=current_user.id
    )
    db.session.add(project)
    db.session.commit()
    return make_response(data=project.to_dict(), status_code=201)

@app.route('/api/projects/<int:project_id>', methods=['PUT'])
@token_required
@admin_required
def update_project(current_user, project_id):
    project = Project.query.get(project_id)
    if not project:
        return make_response(error={"code": "NOT_FOUND", "message": "Project not found"}, status_code=404)

    data = request.get_json() or {}
    if 'name' in data:
        project.name = data['name'].strip()
    if 'description' in data:
        project.description = data['description'].strip()
    if 'status' in data:
        project.status = data['status']

    db.session.commit()
    return make_response(data=project.to_dict())

@app.route('/api/projects/<int:project_id>', methods=['DELETE'])
@token_required
@admin_required
def delete_project(current_user, project_id):
    project = Project.query.get(project_id)
    if not project:
        return make_response(error={"code": "NOT_FOUND", "message": "Project not found"}, status_code=404)

    db.session.delete(project)
    db.session.commit()
    return make_response(data={"message": "Project deleted successfully"})

@app.route('/api/tasks', methods=['GET'])
@token_required
def get_tasks(current_user):
    query = Task.query

    # Filtering parameters
    search = request.args.get('search', '').strip()
    status = request.args.get('status', '').strip()
    priority = request.args.get('priority', '').strip()
    project_id = request.args.get('project_id', type=int)
    assigned_to = request.args.get('assigned_to', type=int)

    if search:
        query = query.filter(Task.title.ilike(f'%{search}%') | Task.description.ilike(f'%{search}%'))
    if status:
        query = query.filter(Task.status == status)
    if priority:
        query = query.filter(Task.priority == priority)
    if project_id:
        query = query.filter(Task.project_id == project_id)
    if assigned_to:
        query = query.filter(Task.assigned_to == assigned_to)

    tasks = query.order_by(Task.created_at.desc()).all()
    return make_response(data=[t.to_dict() for t in tasks])

@app.route('/api/tasks/<int:task_id>', methods=['GET'])
@token_required
def get_task(current_user, task_id):
    task = Task.query.get(task_id)
    if not task:
        return make_response(error={"code": "NOT_FOUND", "message": "Task not found"}, status_code=404)
    return make_response(data=task.to_dict())

@app.route('/api/tasks', methods=['POST'])
@token_required
def create_task(current_user):
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    status = data.get('status', 'to_do')
    priority = data.get('priority', 'medium')
    due_date = data.get('due_date', '')
    project_id = data.get('project_id')
    assigned_to = data.get('assigned_to')

    if not title:
        return make_response(error={"code": "VALIDATION_ERROR", "message": "Task title is required"}, status_code=400)
    if not project_id or not Project.query.get(project_id):
        return make_response(error={"code": "VALIDATION_ERROR", "message": "A valid project selection is required"}, status_code=400)

    task = Task(
        title=title,
        description=description,
        status=status,
        priority=priority,
        due_date=due_date,
        project_id=project_id,
        assigned_to=assigned_to if assigned_to else None,
        created_by=current_user.id
    )
    db.session.add(task)
    db.session.commit()
    return make_response(data=task.to_dict(), status_code=201)

@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
@token_required
def update_task(current_user, task_id):
    task = Task.query.get(task_id)
    if not task:
        return make_response(error={"code": "NOT_FOUND", "message": "Task not found"}, status_code=404)

    # Permission check: Admin, Task Creator, or Assignee can modify
    if current_user.role != 'admin' and task.created_by != current_user.id and task.assigned_to != current_user.id:
        return make_response(error={"code": "FORBIDDEN", "message": "Permission denied to update this task"}, status_code=403)

    data = request.get_json() or {}
    if 'title' in data:
        task.title = data['title'].strip()
    if 'description' in data:
        task.description = data['description'].strip()
    if 'status' in data:
        task.status = data['status']
    if 'priority' in data:
        task.priority = data['priority']
    if 'due_date' in data:
        task.due_date = data['due_date']
    if 'project_id' in data and Project.query.get(data['project_id']):
        task.project_id = data['project_id']
    if 'assigned_to' in data:
        task.assigned_to = data['assigned_to'] if data['assigned_to'] else None

    db.session.commit()
    return make_response(data=task.to_dict())

@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
@token_required
def delete_task(current_user, task_id):
    task = Task.query.get(task_id)
    if not task:
        return make_response(error={"code": "NOT_FOUND", "message": "Task not found"}, status_code=404)

    if current_user.role != 'admin' and task.created_by != current_user.id:
        return make_response(error={"code": "FORBIDDEN", "message": "Permission denied to delete this task"}, status_code=403)

    db.session.delete(task)
    db.session.commit()
    return make_response(data={"message": "Task deleted successfully"})

@app.route('/api/users', methods=['GET'])
@token_required
def get_users(current_user):
    users = User.query.all()
    return make_response(data=[u.to_dict() for u in users])

@app.route('/api/users/<int:user_id>', methods=['PUT'])
@token_required
@admin_required
def update_user_role(current_user, user_id):
    user = User.query.get(user_id)
    if not user:
        return make_response(error={"code": "NOT_FOUND", "message": "User not found"}, status_code=404)

    data = request.get_json() or {}
    new_role = data.get('role')

    if new_role not in ['admin', 'user']:
        return make_response(error={"code": "VALIDATION_ERROR", "message": "Role must be 'admin' or 'user'"}, status_code=400)

    # Protect against demoting the sole remaining admin
    if user.role == 'admin' and new_role == 'user':
        admin_count = User.query.filter_by(role='admin').count()
        if admin_count <= 1:
            return make_response(error={"code": "PROTECTION_ERROR", "message": "Cannot demote the sole administrator"}, status_code=400)

    user.role = new_role
    db.session.commit()
    return make_response(data=user.to_dict())

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@token_required
@admin_required
def delete_user(current_user, user_id):
    if user_id == current_user.id:
        return make_response(error={"code": "ACTION_DENIED", "message": "Administrators cannot delete their own account"}, status_code=400)

    user = User.query.get(user_id)
    if not user:
        return make_response(error={"code": "NOT_FOUND", "message": "User not found"}, status_code=404)

    db.session.delete(user)
    db.session.commit()
    return make_response(data={"message": "User removed successfully"})

@app.route('/api/admin/stats', methods=['GET'])
@token_required
@admin_required
def get_admin_stats(current_user):
    today_str = datetime.date.today().isoformat()
    total_users = User.query.count()
    total_projects = Project.query.count()
    active_projects = Project.query.filter_by(status='active').count()
    total_tasks = Task.query.count()
    completed_tasks = Task.query.filter_by(status='completed').count()
    overdue_tasks = Task.query.filter(Task.due_date < today_str, Task.status != 'completed').count()

    return make_response(data={
        "total_users": total_users,
        "total_projects": total_projects,
        "active_projects": active_projects,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "overdue_tasks": overdue_tasks
    })

def seed_database():
    db.create_all()
    if User.query.first() is not None:
        return # Database already seeded

    print("Seeding database with fictional initial data...")
    
    # 1. Users
    admin = User(name="System Admin", email="admin@taskflow.demo", role="admin")
    admin.set_password("AdminPass123!")

    alex = User(name="Alex Rivera", email="alex@taskflow.demo", role="user")
    alex.set_password("UserPass123!")

    sam = User(name="Sam Chen", email="sam@taskflow.demo", role="user")
    sam.set_password("UserPass123!")

    db.session.add_all([admin, alex, sam])
    db.session.commit()

    # 2. Projects
    p1 = Project(name="Mobile App Redesign", description="Complete UX overhaul of iOS and Android applications.", status="active", owner_id=admin.id)
    p2 = Project(name="Cloud Infrastructure Migration", description="Migrating legacy servers to containerized AWS instances.", status="active", owner_id=admin.id)
    p3 = Project(name="Q3 Marketing Campaign", description="Launch collateral for the upcoming v2.0 feature drop.", status="planning", owner_id=admin.id)

    db.session.add_all([p1, p2, p3])
    db.session.commit()

    # 3. Tasks
    today = datetime.date.today()
    tasks = [
        Task(title="Design Wireframes for Onboarding", description="Create Figma wireframes for user sign-up flow.", status="completed", priority="high", due_date=(today - datetime.timedelta(days=2)).isoformat(), project_id=p1.id, assigned_to=alex.id, created_by=admin.id),
        Task(title="Implement Dark Mode Theme", description="Add CSS variables and React toggle for dark theme.", status="in_progress", priority="medium", due_date=(today + datetime.timedelta(days=3)).isoformat(), project_id=p1.id, assigned_to=sam.id, created_by=admin.id),
        Task(title="Fix Navigation Gesture Bug", description="Mobile menu freezes on swipe left on iOS devices.", status="to_do", priority="urgent", due_date=(today + datetime.timedelta(days=1)).isoformat(), project_id=p1.id, assigned_to=alex.id, created_by=admin.id),
        Task(title="Audit Docker Containers", description="Security scan for existing Docker images.", status="completed", priority="high", due_date=(today - datetime.timedelta(days=5)).isoformat(), project_id=p2.id, assigned_to=sam.id, created_by=admin.id),
        Task(title="Configure TerraForm Scripts", description="Automate VPC creation and subnet allocation.", status="in_progress", priority="urgent", due_date=(today + datetime.timedelta(days=4)).isoformat(), project_id=p2.id, assigned_to=sam.id, created_by=admin.id),
        Task(title="Database Index Optimization", description="Optimize query execution time on user lookup tables.", status="review", priority="medium", due_date=(today + datetime.timedelta(days=2)).isoformat(), project_id=p2.id, assigned_to=alex.id, created_by=admin.id),
        Task(title="Draft Press Release", description="Write copy for tech news publication announcement.", status="to_do", priority="low", due_date=(today + datetime.timedelta(days=10)).isoformat(), project_id=p3.id, assigned_to=alex.id, created_by=admin.id),
        Task(title="Design Email Banners", description="Export SVG assets for customer newsletter.", status="to_do", priority="medium", due_date=(today + datetime.timedelta(days=7)).isoformat(), project_id=p3.id, assigned_to=sam.id, created_by=admin.id),
        Task(title="User Feedback Survey Analysis", description="Review answers from top 50 active beta testers.", status="completed", priority="medium", due_date=(today - datetime.timedelta(days=1)).isoformat(), project_id=p1.id, assigned_to=alex.id, created_by=admin.id),
        Task(title="Setup CI/CD Pipeline", description="Configure GitHub Actions for automated linting and unit tests.", status="completed", priority="high", due_date=(today - datetime.timedelta(days=4)).isoformat(), project_id=p2.id, assigned_to=sam.id, created_by=admin.id),
        Task(title="API Rate Limiting Middleware", description="Implement Token Bucket algorithm to prevent abuse.", status="in_progress", priority="high", due_date=(today + datetime.timedelta(days=5)).isoformat(), project_id=p2.id, assigned_to=alex.id, created_by=admin.id)
    ]

    db.session.add_all(tasks)
    db.session.commit()
    print("Database seeding completed successfully.")

if __name__ == '__main__':
    with app.app_context():
        seed_database()
    app.run(host='127.0.0.1', port=5000, debug=True)