from flask import Flask, render_template, request, redirect, url_for, flash
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'secret!') # Default fallback for dev
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

from datetime import datetime

# ... (Previous imports) ...

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class InviteCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    is_used = db.Column(db.Boolean, default=False)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('messages', lazy=True))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
@login_required
def index():
    return render_template('base.html', user=current_user)

@app.route('/chat')
@login_required
def chat():
    return render_template('chat.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        invite_code = request.form.get('invite_code')
        username = request.form.get('username')
        password = request.form.get('password')

        invite = InviteCode.query.filter_by(code=invite_code, is_used=False).first()
        if not invite:
            flash('Invalid or used invite code')
            return redirect(url_for('register'))
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))

        new_user = User(username=username)
        new_user.set_password(password)
        # First user is admin
        if User.query.count() == 0:
            new_user.is_admin = True
        
        invite.is_used = True
        db.session.add(new_user)
        db.session.commit()
        
        login_user(new_user)
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# SocketIO Events
@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        pass # Optional join logic

@socketio.on('send_message')
def handle_message(data):
    if current_user.is_authenticated:
        content = data.get('content')
        if content:
            msg = Message(content=content, user_id=current_user.id)
            db.session.add(msg)
            db.session.commit()
            emit('message', {
                'username': current_user.username,
                'content': content,
                'timestamp': msg.timestamp.strftime('%H:%M')
            }, broadcast=True)


# ... (Previous imports and models) ...

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    threads = db.relationship('Thread', backref='category', lazy=True)

class Thread(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    user = db.relationship('User', backref='threads')
    posts = db.relationship('Post', backref='thread', lazy=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    thread_id = db.Column(db.Integer, db.ForeignKey('thread.id'), nullable=False)
    user = db.relationship('User', backref='posts')

# ... (Previous routes) ...

@app.route('/forum')
@login_required
def forum():
    categories = Category.query.all()
    # If no categories, create them (quick fix for initialization)
    if not categories:
        defaults = ['Coding & Tech', 'Problem-Solving', 'General Discussion']
        for name in defaults:
            db.session.add(Category(name=name))
        db.session.commit()
        categories = Category.query.all()
    return render_template('forum_list.html', categories=categories)

@app.route('/forum/<int:category_id>')
@login_required
def forum_category(category_id):
    category = Category.query.get_or_404(category_id)
    return render_template('forum_category.html', category=category)

@app.route('/forum/<int:category_id>/new', methods=['GET', 'POST'])
@login_required
def new_thread(category_id):
    category = Category.query.get_or_404(category_id)
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        thread = Thread(title=title, content=content, category=category, user=current_user)
        db.session.add(thread)
        db.session.commit()
        return redirect(url_for('view_thread', thread_id=thread.id))
    return render_template('new_thread.html', category=category)

@app.route('/thread/<int:thread_id>', methods=['GET', 'POST'])
@login_required
def view_thread(thread_id):
    thread = Thread.query.get_or_404(thread_id)
    if request.method == 'POST':
        content = request.form.get('content')
        post = Post(content=content, thread=thread, user=current_user)
        db.session.add(post)
        db.session.commit()
        return redirect(url_for('view_thread', thread_id=thread_id))
    return render_template('forum_thread.html', thread=thread)

# ... (Previous imports and models) ...
from werkzeug.utils import secure_filename

app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref='files')
    size = db.Column(db.Integer)

# ... (Previous routes) ...

@app.route('/files', methods=['GET', 'POST'])
@login_required
def files():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file:
            original_name = file.filename
            filename = secure_filename(original_name)
            # Avoid duplicate overwrite by prepending timestamp
            filename = f"{int(datetime.utcnow().timestamp())}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            new_file = File(
                filename=filename, 
                original_name=original_name, 
                user=current_user,
                size=os.path.getsize(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            )
            db.session.add(new_file)
            db.session.commit()
            flash('File uploaded successfully')
            return redirect(url_for('files'))
            
    files = File.query.order_by(File.upload_date.desc()).all()
    return render_template('files.html', files=files)

@app.route('/files/download/<int:file_id>')
@login_required
def download_file(file_id):
    file = File.query.get_or_404(file_id)
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], file.filename, as_attachment=True, download_name=file.original_name)

@app.route('/files/delete/<int:file_id>')
@login_required
def delete_file(file_id):
    file = File.query.get_or_404(file_id)
    if not current_user.is_admin and current_user.id != file.user_id:
        flash('Permission denied')
        return redirect(url_for('files'))
    
    try:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))
    except:
        pass # File might be missing from disk
    
    db.session.delete(file)
    db.session.commit()
    flash('File deleted')
    return redirect(url_for('files'))

# ... (Previous imports and models) ...

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    start = db.Column(db.DateTime, nullable=False)
    end = db.Column(db.DateTime)
    type = db.Column(db.String(50)) # assignment, test, study, social
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Habit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    frequency = db.Column(db.String(50), default='daily')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    logs = db.relationship('HabitLog', backref='habit', lazy=True)

class HabitLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    habit_id = db.Column(db.Integer, db.ForeignKey('habit.id'), nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow().date)
    completed = db.Column(db.Boolean, default=True)

# ... (Previous routes) ...

@app.route('/calendar')
@login_required
def calendar():
    return render_template('calendar.html')

@app.route('/api/events', methods=['GET', 'POST'])
@login_required
def api_events():
    if request.method == 'POST':
        data = request.json
        start = datetime.strptime(data['start'], '%Y-%m-%dT%H:%M')
        end = datetime.strptime(data['end'], '%Y-%m-%dT%H:%M') if data.get('end') else None
        event = Event(title=data['title'], start=start, end=end, type=data['type'], user_id=current_user.id)
        db.session.add(event)
        db.session.commit()
        return {'status': 'success', 'id': event.id}
    
    events = Event.query.all()
    events_list = [{
        'id': e.id,
        'title': e.title,
        'start': e.start.isoformat(),
        'end': e.end.isoformat() if e.end else None,
        'backgroundColor': '#cf6679' if e.type == 'test' else '#bb86fc',
        'borderColor': '#cf6679' if e.type == 'test' else '#bb86fc'
    } for e in events]
    return {'events': events_list}

@app.route('/habits', methods=['GET', 'POST'])
@login_required
def habits():
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            habit = Habit(name=name, user_id=current_user.id)
            db.session.add(habit)
            db.session.commit()
        return redirect(url_for('habits'))
    
    my_habits = Habit.query.filter_by(user_id=current_user.id).all()
    today = datetime.utcnow().date()
    
    # Process habits to check status for today
    habit_data = []
    for h in my_habits:
        is_done = HabitLog.query.filter_by(habit_id=h.id, date=today, completed=True).first() is not None
        habit_data.append({'habit': h, 'today_done': is_done})
        
    return render_template('habits.html', habits=habit_data)

@app.route('/habits/toggle/<int:habit_id>')
@login_required
def toggle_habit(habit_id):
    habit = Habit.query.get_or_404(habit_id)
    if habit.user_id != current_user.id:
        return "Access Denied", 403
        
    today = datetime.utcnow().date()
    log = HabitLog.query.filter_by(habit_id=habit.id, date=today).first()
    
    if log:
        db.session.delete(log)
    else:
        new_log = HabitLog(habit=habit, date=today)
        db.session.add(new_log)
    
    db.session.commit()
    return redirect(url_for('habits'))

# ... (Previous imports and models) ...
import json

class Poll(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(200), nullable=False)
    options = db.Column(db.Text, nullable=False) # JSON encoded
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    active = db.Column(db.Boolean, default=True)
    votes = db.relationship('Vote', backref='poll', lazy=True)

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey('poll.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    option_index = db.Column(db.Integer, nullable=False)

# ... (Previous routes) ...

@app.route('/polls', methods=['GET', 'POST'])
@login_required
def polls():
    if request.method == 'POST':
        question = request.form.get('question')
        options = request.form.getlist('option')
        # Filter empty options
        options = [opt for opt in options if opt.strip()]
        
        if question and len(options) >= 2:
            poll = Poll(question=question, options=json.dumps(options), creator_id=current_user.id)
            db.session.add(poll)
            db.session.commit()
        return redirect(url_for('polls'))

    all_polls = Poll.query.order_by(Poll.id.desc()).all()
    polls_data = []
    
    for poll in all_polls:
        options = json.loads(poll.options)
        # Calculate results
        results = [0] * len(options)
        total_votes = 0
        user_voted_index = None
        
        for vote in poll.votes:
            if vote.option_index < len(results):
                results[vote.option_index] += 1
                total_votes += 1
            if vote.user_id == current_user.id:
                user_voted_index = vote.option_index
                
        polls_data.append({
            'poll': poll,
            'options': options,
            'results': results,
            'total_votes': total_votes,
            'user_voted_index': user_voted_index
        })
        
    return render_template('polls.html', polls=polls_data)

@app.route('/polls/vote/<int:poll_id>/<int:option_index>')
@login_required
def vote_poll(poll_id, option_index):
    poll = Poll.query.get_or_404(poll_id)
    if not poll.active:
        return "Poll Closed", 403
        
    existing_vote = Vote.query.filter_by(poll_id=poll.id, user_id=current_user.id).first()
    if existing_vote:
        existing_vote.option_index = option_index
    else:
        new_vote = Vote(poll_id=poll.id, user_id=current_user.id, option_index=option_index)
        db.session.add(new_vote)
        
    db.session.commit()
    return redirect(url_for('polls'))

# Admin helper continued...


@app.route('/admin/generate_invite')
@login_required
def generate_invite():
    if not current_user.is_admin:
        return "Access Denied", 403
    import secrets
    code = secrets.token_hex(4)
    new_invite = InviteCode(code=code)
    db.session.add(new_invite)
    db.session.commit()
    return f"Generated Code: {code}"

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Create initial invite code if none exists
        if InviteCode.query.count() == 0:
            initial_code = "WELCOME123"
            db.session.add(InviteCode(code=initial_code))
            db.session.commit()
            print(f"Initial Invite Code Created: {initial_code}")
            
    socketio.run(app, debug=False, port=int(os.environ.get("PORT", 5000)))

