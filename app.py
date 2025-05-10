from flask import Flask, render_template, jsonify, request, session, send_from_directory
from flask_cors import CORS
import random
import requests
from urllib.parse import quote_plus
from datetime import datetime, timedelta, timezone
import json
import os
import bcrypt
from werkzeug.utils import secure_filename
from dateutil.parser import isoparse
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from textblob import TextBlob
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

app = Flask(__name__)
CORS(app)
app.secret_key = os.urandom(24)  # For session management
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mood_music.db'
db = SQLAlchemy(app)

# File paths
USERS_FILE = 'users.json'
MOOD_HISTORY_FILE = 'mood_history.json'
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    profile_pic = db.Column(db.String(200))
    bio = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    moods = db.relationship('MoodEntry', backref='user', lazy=True)
    favorite_genres = db.Column(db.String(200))
    notification_preferences = db.Column(db.String(200))

class MoodEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    mood = db.Column(db.String(50), nullable=False)
    intensity = db.Column(db.Integer)
    notes = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    music_recommendations = db.Column(db.String(500))
    quote_recommendations = db.Column(db.String(500))

# Spotify API setup
SPOTIFY_CLIENT_ID = 'your-spotify-client-id'
SPOTIFY_CLIENT_SECRET = 'your-spotify-client-secret'
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_mood_history():
    try:
        with open(MOOD_HISTORY_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_mood_history(history):
    with open(MOOD_HISTORY_FILE, 'w') as f:
        json.dump(history, f)

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

# Sample music database with YouTube embed links
MUSIC_DATABASE = {
    'happy': {
        'hindi': [
            {'title': 'Kesariya', 'artist': 'Arijit Singh', 'youtube_embed': 'https://www.youtube.com/embed/Z1JZ9O15280'},
            {'title': 'Chaleya', 'artist': 'Arijit Singh, Shilpa Rao', 'youtube_embed': 'https://www.youtube.com/embed/k1BneeJTDcU'}
        ],
        'english': [
            {'title': 'Flowers', 'artist': 'Miley Cyrus', 'youtube_embed': 'https://www.youtube.com/embed/G7KNmW9a75Y'},
            {'title': 'Vampire', 'artist': 'Olivia Rodrigo', 'youtube_embed': 'https://www.youtube.com/embed/Bt7cfXyT6rM'}
        ],
        'punjabi': [
            {'title': '52 Gaj Ka Daman', 'artist': 'Renuka Panwar', 'youtube_embed': 'https://www.youtube.com/embed/gF6nfZLCnJ8'},
            {'title': 'Chal Jindiye', 'artist': 'Amrinder Gill', 'youtube_embed': 'https://www.youtube.com/embed/Qw1r1C2Tn5E'}
        ]
    },
    'sad': {
        'hindi': [
            {'title': 'Tere Vaaste', 'artist': 'Varun Jain', 'youtube_embed': 'https://www.youtube.com/embed/F2t6EsPFAQU'},
            {'title': 'O Bedardeya', 'artist': 'Arijit Singh', 'youtube_embed': 'https://www.youtube.com/embed/F6g7FqjQb6w'}
        ],
        'english': [
            {'title': 'Last Night', 'artist': 'Morgan Wallen', 'youtube_embed': 'https://www.youtube.com/embed/pRY1l4A2G9M'},
            {'title': 'Anti-Hero', 'artist': 'Taylor Swift', 'youtube_embed': 'https://www.youtube.com/embed/b1kbLwvqugk'}
        ],
        'punjabi': [
            {'title': 'Pyaar Hota Kayi Baar Hai', 'artist': 'Arijit Singh', 'youtube_embed': 'https://www.youtube.com/embed/Qw1r1C2Tn5E'},
            {'title': 'Tere Te', 'artist': 'AP Dhillon', 'youtube_embed': 'https://www.youtube.com/embed/Qw1r1C2Tn5E'}
        ]
    },
    'energetic': {
        'hindi': [
            {'title': 'Naatu Naatu', 'artist': 'Rahul Sipligunj, Kaala Bhairava', 'youtube_embed': 'https://www.youtube.com/embed/OSa3lK9Qb6M'},
            {'title': 'Jhoome Jo Pathaan', 'artist': 'Arijit Singh, Sukriti Kakar', 'youtube_embed': 'https://www.youtube.com/embed/vqu4z34wENw'}
        ],
        'english': [
            {'title': 'Unholy', 'artist': 'Sam Smith, Kim Petras', 'youtube_embed': 'https://www.youtube.com/embed/8FW_0gQ3w2M'},
            {'title': 'As It Was', 'artist': 'Harry Styles', 'youtube_embed': 'https://www.youtube.com/embed/H5v3kku4y6Q'}
        ],
        'punjabi': [
            {'title': 'Brown Munde', 'artist': 'AP Dhillon', 'youtube_embed': 'https://www.youtube.com/embed/n_FCrCQ6-bA'},
            {'title': '295', 'artist': 'Sidhu Moose Wala', 'youtube_embed': 'https://www.youtube.com/embed/qFLhGq0060w'}
        ]
    },
    'calm': {
        'hindi': [
            {'title': 'Tere Pyaar Mein', 'artist': 'Arijit Singh', 'youtube_embed': 'https://www.youtube.com/embed/Qw1r1C2Tn5E'},
            {'title': 'Kya Mujhe Pyaar Hai', 'artist': 'KK', 'youtube_embed': 'https://www.youtube.com/embed/Qw1r1C2Tn5E'}
        ],
        'english': [
            {'title': 'Easy On Me', 'artist': 'Adele', 'youtube_embed': 'https://www.youtube.com/embed/YQHsXMglC9A'},
            {'title': 'All of Me', 'artist': 'John Legend', 'youtube_embed': 'https://www.youtube.com/embed/450p7goxZqg'}
        ],
        'punjabi': [
            {'title': 'Pyaar Manga Hai', 'artist': 'Jassie Gill', 'youtube_embed': 'https://www.youtube.com/embed/Qw1r1C2Tn5E'},
            {'title': 'Sakhiyaan', 'artist': 'Maninder Buttar', 'youtube_embed': 'https://www.youtube.com/embed/Qw1r1C2Tn5E'}
        ]
    },
    'romantic': {
        'hindi': [
            {'title': 'Tum Kya Mile', 'artist': 'Pritam, Arijit Singh', 'youtube_embed': 'https://www.youtube.com/embed/4Kc8gk5pN2c'},
            {'title': 'Heeriye', 'artist': 'Jasleen Royal', 'youtube_embed': 'https://www.youtube.com/embed/Qw1r1C2Tn5E'}
        ],
        'english': [
            {'title': 'Perfect', 'artist': 'Ed Sheeran', 'youtube_embed': 'https://www.youtube.com/embed/2Vv-BfVoq4g'},
            {'title': 'Thinking Out Loud', 'artist': 'Ed Sheeran', 'youtube_embed': 'https://www.youtube.com/embed/lp-EO5I60KA'}
        ],
        'punjabi': [
            {'title': 'Pyaar Hona', 'artist': 'Jassie Gill', 'youtube_embed': 'https://www.youtube.com/embed/Qw1r1C2Tn5E'},
            {'title': 'Sakhiyaan', 'artist': 'Maninder Buttar', 'youtube_embed': 'https://www.youtube.com/embed/Qw1r1C2Tn5E'}
        ]
    },
    'motivated': {
        'hindi': [
            {'title': 'Chaleya', 'artist': 'Arijit Singh, Shilpa Rao', 'youtube_embed': 'https://www.youtube.com/embed/k1BneeJTDcU'},
            {'title': 'Naatu Naatu', 'artist': 'Rahul Sipligunj', 'youtube_embed': 'https://www.youtube.com/embed/OSa3lK9Qb6M'}
        ],
        'english': [
            {'title': 'Unstoppable', 'artist': 'Sia', 'youtube_embed': 'https://www.youtube.com/embed/cRM70Jw7F4M'},
            {'title': 'Fight Song', 'artist': 'Rachel Platten', 'youtube_embed': 'https://www.youtube.com/embed/xo1VInw-SKc'}
        ],
        'punjabi': [
            {'title': '295', 'artist': 'Sidhu Moose Wala', 'youtube_embed': 'https://www.youtube.com/embed/qFLhGq0060w'},
            {'title': 'Brown Munde', 'artist': 'AP Dhillon', 'youtube_embed': 'https://www.youtube.com/embed/n_FCrCQ6-bA'}
        ]
    },
    'nostalgic': {
        'hindi': [
            {'title': 'Tum Hi Ho', 'artist': 'Arijit Singh', 'youtube_embed': 'https://www.youtube.com/embed/Umqb9KENgmk'},
            {'title': 'Raabta', 'artist': 'Pritam', 'youtube_embed': 'https://www.youtube.com/embed/p4QqMKe3rwY'}
        ],
        'english': [
            {'title': 'See You Again', 'artist': 'Wiz Khalifa ft. Charlie Puth', 'youtube_embed': 'https://www.youtube.com/embed/RgKAFK5djSk'},
            {'title': 'Photograph', 'artist': 'Ed Sheeran', 'youtube_embed': 'https://www.youtube.com/embed/nSDgHBxUbVQ'}
        ],
        'punjabi': [
            {'title': 'Pyaar Manga Hai', 'artist': 'Jassie Gill', 'youtube_embed': 'https://www.youtube.com/embed/Qw1r1C2Tn5E'},
            {'title': 'Sakhiyaan', 'artist': 'Maninder Buttar', 'youtube_embed': 'https://www.youtube.com/embed/Qw1r1C2Tn5E'}
        ]
    }
}

# Sample quotes database
QUOTES_DATABASE = {
    'happy': [
        {'text': 'Happiness is not something ready-made. It comes from your own actions.', 'author': 'Dalai Lama'},
        {'text': 'The joy of life comes from our encounters with new experiences.', 'author': 'Jon Krakauer'},
        {'text': 'Happiness is a warm puppy.', 'author': 'Charles M. Schulz'},
        {'text': 'The best way to cheer yourself up is to try to cheer somebody else up.', 'author': 'Mark Twain'},
        {'text': 'Happiness is a choice, not a result.', 'author': 'Ralph Marston'}
    ],
    'sad': [
        {'text': 'The wound is the place where the Light enters you.', 'author': 'Rumi'},
        {'text': 'When one door of happiness closes, another opens.', 'author': 'Helen Keller'},
        {'text': 'The only way to do great work is to love what you do.', 'author': 'Steve Jobs'},
        {'text': 'Everything will be okay in the end. If it\'s not okay, it\'s not the end.', 'author': 'John Lennon'},
        {'text': 'The sun will rise and we will try again.', 'author': 'Twenty One Pilots'}
    ],
    'energetic': [
        {'text': 'Energy and persistence conquer all things.', 'author': 'Benjamin Franklin'},
        {'text': 'The only way to do great work is to love what you do.', 'author': 'Steve Jobs'},
        {'text': 'Success is not final, failure is not fatal: it is the courage to continue that counts.', 'author': 'Winston Churchill'},
        {'text': 'Believe you can and you\'re halfway there.', 'author': 'Theodore Roosevelt'},
        {'text': 'The future belongs to those who believe in the beauty of their dreams.', 'author': 'Eleanor Roosevelt'}
    ],
    'calm': [
        {'text': 'Peace begins with a smile.', 'author': 'Mother Teresa'},
        {'text': 'In the midst of chaos, there is also opportunity.', 'author': 'Sun Tzu'},
        {'text': 'The present moment is filled with joy and happiness. If you are attentive, you will see it.', 'author': 'Thich Nhat Hanh'},
        {'text': 'Calm mind brings inner strength and self-confidence.', 'author': 'Dalai Lama'},
        {'text': 'The quieter you become, the more you can hear.', 'author': 'Ram Dass'}
    ],
    'romantic': [
        {'text': 'The best thing to hold onto in life is each other.', 'author': 'Audrey Hepburn'},
        {'text': 'Love is composed of a single soul inhabiting two bodies.', 'author': 'Aristotle'},
        {'text': 'The greatest happiness of life is the conviction that we are loved.', 'author': 'Victor Hugo'},
        {'text': 'Love is a friendship set to music.', 'author': 'Joseph Campbell'},
        {'text': 'In all the world, there is no heart for me like yours.', 'author': 'Maya Angelou'}
    ],
    'motivated': [
        {'text': 'The only way to do great work is to love what you do.', 'author': 'Steve Jobs'},
        {'text': 'Success is not final, failure is not fatal: it is the courage to continue that counts.', 'author': 'Winston Churchill'},
        {'text': 'Believe you can and you\'re halfway there.', 'author': 'Theodore Roosevelt'},
        {'text': 'The future belongs to those who believe in the beauty of their dreams.', 'author': 'Eleanor Roosevelt'},
        {'text': 'Don\'t watch the clock; do what it does. Keep going.', 'author': 'Sam Levenson'}
    ],
    'nostalgic': [
        {'text': 'The past is a place of reference, not a place of residence.', 'author': 'Roy T. Bennett'},
        {'text': 'Nostalgia is a file that removes the rough edges from the good old days.', 'author': 'Doug Larson'},
        {'text': 'The good old days are now.', 'author': 'Tom Stoppard'},
        {'text': 'Memories are the key not to the past, but to the future.', 'author': 'Corrie Ten Boom'},
        {'text': 'The past beats inside me like a second heart.', 'author': 'John Banville'}
    ]
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/calendar')
def calendar():
    return render_template('calendar.html')

@app.route('/api/mood-history')
def get_mood_history():
    try:
        date = request.args.get('date')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not date and not (start_date and end_date):
            return jsonify({'error': 'Either date or start_date and end_date parameters are required'}), 400

        # Load mood history
        mood_history = load_mood_history()
        
        def to_utc_date(dtstr):
            dt = isoparse(dtstr)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt.date()

        if date:
            target_date = isoparse(date).date()
            daily_entries = [
                entry for entry in mood_history 
                if to_utc_date(entry['timestamp']) == target_date and all(k in entry for k in ['mood', 'music_played', 'quotes_shown'])
            ]
        else:
            start = isoparse(start_date).date()
            end = isoparse(end_date).date()
            daily_entries = [
                entry for entry in mood_history 
                if start <= to_utc_date(entry['timestamp']) <= end and all(k in entry for k in ['mood', 'music_played', 'quotes_shown'])
            ]
        
        # Sort entries by time
        daily_entries.sort(key=lambda x: isoparse(x['timestamp']).date())
        
        # Format entries for response
        formatted_entries = []
        now = datetime.now(timezone.utc)
        for entry in daily_entries:
            # Skip non-mood entries
            if not all(k in entry for k in ['mood', 'music_played', 'quotes_shown']):
                continue
            timestamp = isoparse(entry['timestamp'])
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            if timestamp <= now:
                formatted_entries.append({
                    'time': timestamp.strftime('%I:%M %p'),
                    'mood': entry['mood'].capitalize(),
                    'music': entry['music_played'],
                    'quotes': entry['quotes_shown'],
                    'timestamp': entry['timestamp']
                })
        
        return jsonify({
            'entries': formatted_entries
        })
    except Exception as e:
        print(f"Error in get_mood_history: {str(e)}")
        return jsonify({
            'error': 'Failed to get mood history',
            'details': str(e)
        }), 500

@app.route('/api/mood-stats')
def get_mood_stats():
    try:
        # Load mood history
        mood_history = load_mood_history()
        
        if not mood_history:
            return jsonify({
                'streak': 0,
                'common_mood': None,
                'total_entries': 0,
                'mood_distribution': {}
            })
        
        # Calculate streak
        streak = 0
        today = datetime.now().date()
        current_date = today
        
        while True:
            has_entry = any(
                to_utc_date(entry['timestamp']) == current_date
                for entry in mood_history
            )
            if not has_entry:
                break
            streak += 1
            current_date = current_date - timedelta(days=1)
        
        # Calculate mood distribution
        mood_counts = {}
        for entry in mood_history:
            mood = entry['mood']
            mood_counts[mood] = mood_counts.get(mood, 0) + 1
        
        # Find most common mood
        common_mood = max(mood_counts.items(), key=lambda x: x[1])[0] if mood_counts else None
        
        return jsonify({
            'streak': streak,
            'common_mood': common_mood,
            'total_entries': len(mood_history),
            'mood_distribution': mood_counts
        })
    except Exception as e:
        print(f"Error in get_mood_stats: {str(e)}")
        return jsonify({
            'error': 'Failed to get mood statistics',
            'details': str(e)
        }), 500

@app.route('/api/recommendations')
def get_recommendations():
    try:
        mood = request.args.get('mood', 'happy').lower()
        date_str = request.args.get('date')
        # Get 2 recommendations for each language
        music = []
        for language in ['hindi', 'english', 'punjabi']:
            if mood in MUSIC_DATABASE and language in MUSIC_DATABASE[mood]:
                music.extend(MUSIC_DATABASE[mood][language])
        # Get 3 random quotes
        quotes = random.sample(QUOTES_DATABASE.get(mood, QUOTES_DATABASE['happy']), 3)
        # Record mood in history
        mood_history = load_mood_history()
        if date_str:
            try:
                timestamp = isoparse(date_str)
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                else:
                    timestamp = timestamp.astimezone(timezone.utc)
                timestamp_str = timestamp.isoformat()
            except Exception:
                timestamp_str = datetime.now(timezone.utc).isoformat()
        else:
            timestamp_str = datetime.now(timezone.utc).isoformat()
        mood_history.append({
            'mood': mood,
            'timestamp': timestamp_str,
            'music_played': [song['title'] for song in music],
            'quotes_shown': [quote['text'] for quote in quotes]
        })
        save_mood_history(mood_history)
        return jsonify({
            'music': music,
            'quotes': quotes
        })
    except Exception as e:
        print(f"Error in get_recommendations: {str(e)}")
        return jsonify({
            'error': 'Failed to get recommendations',
            'details': str(e)
        }), 500

@app.route('/profile')
def profile():
    if 'user_email' not in session:
        return render_template('index.html')
    return render_template('profile.html')

@app.route('/api/signin', methods=['POST'])
def signin():
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'success': False, 'error': 'Email and password are required'})
        
        users = load_users()
        
        # Check if user exists
        if email not in users:
            return jsonify({'success': False, 'error': 'No account found with this email. Please sign up first.'})
        
        user = users[email]
        
        # Verify password
        if not bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            return jsonify({'success': False, 'error': 'Invalid password'})
        
        # Set session
        session['user_email'] = email
        session['username'] = user['username']
        
        return jsonify({
            'success': True,
            'username': user['username'],
            'name': user['name'],
            'profile_pic': user.get('profile_pic')
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'success': False, 'message': 'Email already registered'})
    
    user = User(
        username=data['username'],
        email=data['email'],
        password_hash=generate_password_hash(data['password']),
        favorite_genres=json.dumps([]),
        notification_preferences=json.dumps({'email': True, 'push': True})
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/signout', methods=['POST'])
def signout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/profile', methods=['GET', 'POST'])
def profile_api():
    if 'user_email' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'})
    
    users = load_users()
    user = users.get(session['user_email'])
    
    if not user:
        return jsonify({'success': False, 'error': 'User not found'})
    
    if request.method == 'GET':
        return jsonify({
            'success': True,
            'name': user['name'],
            'username': user['username'],
            'email': session['user_email'],
            'profile_pic': user.get('profile_pic'),
            'bio': user.get('bio', ''),
            'music_genres': user.get('music_genres', [])
        })
    else:
        try:
            if request.files.get('profile_pic'):
                profile_pic = request.files['profile_pic']
                if allowed_file(profile_pic.filename):
                    filename = secure_filename(f"{user['username']}_{profile_pic.filename}")
                    profile_pic_path = os.path.join('uploads', filename)
                    profile_pic.save(os.path.join(UPLOAD_FOLDER, filename))
                    user['profile_pic'] = profile_pic_path
            else:
                data = request.get_json()
                if 'bio' in data:
                    user['bio'] = data['bio']
                if 'music_genres' in data:
                    user['music_genres'] = data['music_genres']
            
            save_users(users)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

@app.route('/settings')
def settings():
    if 'user_email' not in session:
        return render_template('index.html')
    return render_template('settings.html')

@app.route('/api/favorite', methods=['POST'])
def add_favorite():
    if 'user_email' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'})
    users = load_users()
    user = users[session['user_email']]
    data = request.get_json()
    fav_type = data.get('type')  # 'song' or 'quote'
    item = data.get('item')
    if fav_type not in ['song', 'quote'] or not item:
        return jsonify({'success': False, 'error': 'Invalid data'})
    user.setdefault('favorites', {'songs': [], 'quotes': []})
    if fav_type == 'song' and item not in user['favorites']['songs']:
        user['favorites']['songs'].append(item)
    if fav_type == 'quote' and item not in user['favorites']['quotes']:
        user['favorites']['quotes'].append(item)
    save_users(users)
    return jsonify({'success': True})

@app.route('/api/favorite', methods=['DELETE'])
def remove_favorite():
    if 'user_email' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'})
    users = load_users()
    user = users[session['user_email']]
    data = request.get_json()
    fav_type = data.get('type')
    item = data.get('item')
    if fav_type not in ['song', 'quote'] or not item:
        return jsonify({'success': False, 'error': 'Invalid data'})
    user.setdefault('favorites', {'songs': [], 'quotes': []})
    if fav_type == 'song' and item in user['favorites']['songs']:
        user['favorites']['songs'].remove(item)
    if fav_type == 'quote' and item in user['favorites']['quotes']:
        user['favorites']['quotes'].remove(item)
    save_users(users)
    return jsonify({'success': True})

@app.route('/api/favorites')
def get_favorites():
    if 'user_email' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'})
    users = load_users()
    user = users[session['user_email']]
    return jsonify({'success': True, 'favorites': user.get('favorites', {'songs': [], 'quotes': []})})

@app.route('/quiz')
def quiz():
    return render_template('quiz.html')

@app.route('/motivational-wall')
def motivational_wall():
    return render_template('motivational_wall.html')

@app.route('/api/motivational-messages', methods=['GET', 'POST'])
def motivational_messages():
    # Store messages in a JSON file
    MESSAGES_FILE = 'motivational_messages.json'
    if request.method == 'POST':
        data = request.get_json()
        msg = data.get('message')
        if not msg:
            return jsonify({'success': False, 'error': 'Message required'})
        try:
            with open(MESSAGES_FILE, 'r') as f:
                messages = json.load(f)
        except:
            messages = []
        messages.append({'message': msg, 'likes': 0})
        with open(MESSAGES_FILE, 'w') as f:
            json.dump(messages, f)
        return jsonify({'success': True})
    else:
        try:
            with open(MESSAGES_FILE, 'r') as f:
                messages = json.load(f)
        except:
            messages = []
        return jsonify({'success': True, 'messages': messages})

@app.route('/api/motivational-like', methods=['POST'])
def motivational_like():
    MESSAGES_FILE = 'motivational_messages.json'
    data = request.get_json()
    idx = data.get('index')
    try:
        with open(MESSAGES_FILE, 'r') as f:
            messages = json.load(f)
        messages[idx]['likes'] += 1
        with open(MESSAGES_FILE, 'w') as f:
            json.dump(messages, f)
        return jsonify({'success': True})
    except:
        return jsonify({'success': False})

@app.route('/funny')
def funny():
    return render_template('funny.html')

@app.route('/api/change-password', methods=['POST'])
def change_password():
    if 'user_email' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    data = request.get_json()
    current = data.get('current_password')
    new = data.get('new_password')
    users = load_users()
    user = users.get(session['user_email'])
    if not user or not bcrypt.checkpw(current.encode('utf-8'), user['password'].encode('utf-8')):
        return jsonify({'success': False, 'error': 'Current password is incorrect'})
    user['password'] = bcrypt.hashpw(new.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    save_users(users)
    return jsonify({'success': True})

@app.route('/api/preferences', methods=['POST'])
def save_preferences():
    if 'user_email' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    data = request.get_json()
    users = load_users()
    user = users.get(session['user_email'])
    user['preferences'] = data
    save_users(users)
    return jsonify({'success': True})

@app.route('/api/analyze-mood', methods=['POST'])
def analyze_mood():
    if 'user_email' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    data = request.json
    text = data.get('text', '')
    
    # Analyze mood using TextBlob
    analysis = TextBlob(text)
    sentiment = analysis.sentiment.polarity
    
    # Map sentiment to mood
    if sentiment > 0.5:
        mood = 'Very Happy'
    elif sentiment > 0:
        mood = 'Happy'
    elif sentiment > -0.5:
        mood = 'Neutral'
    elif sentiment > -1:
        mood = 'Sad'
    else:
        mood = 'Very Sad'
    
    # Get music recommendations based on mood
    music_recommendations = get_music_recommendations(mood)
    
    # Get quote recommendations based on mood
    quote_recommendations = get_quote_recommendations(mood)
    
    # Save mood entry
    entry = MoodEntry(
        user_id=session['user_id'],
        mood=mood,
        intensity=int(abs(sentiment) * 10),
        notes=text,
        music_recommendations=json.dumps(music_recommendations),
        quote_recommendations=json.dumps(quote_recommendations)
    )
    db.session.add(entry)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'mood': mood,
        'intensity': entry.intensity,
        'music_recommendations': music_recommendations,
        'quote_recommendations': quote_recommendations
    })

def get_music_recommendations(mood):
    # Map moods to Spotify genres
    mood_to_genres = {
        'Very Happy': ['happy', 'dance', 'pop'],
        'Happy': ['pop', 'indie-pop', 'folk'],
        'Neutral': ['ambient', 'classical', 'jazz'],
        'Sad': ['indie', 'alternative', 'soul'],
        'Very Sad': ['classical', 'ambient', 'piano']
    }
    
    genres = mood_to_genres.get(mood, ['pop'])
    recommendations = []
    
    for genre in genres:
        results = sp.recommendations(
            seed_genres=[genre],
            limit=5
        )
        for track in results['tracks']:
            recommendations.append({
                'name': track['name'],
                'artist': track['artists'][0]['name'],
                'preview_url': track['preview_url'],
                'image_url': track['album']['images'][0]['url']
            })
    
    return recommendations

def get_quote_recommendations(mood):
    # Map moods to quote categories
    mood_to_categories = {
        'Very Happy': ['success', 'happiness', 'motivation'],
        'Happy': ['joy', 'positivity', 'inspiration'],
        'Neutral': ['wisdom', 'reflection', 'peace'],
        'Sad': ['hope', 'healing', 'comfort'],
        'Very Sad': ['strength', 'courage', 'resilience']
    }
    
    categories = mood_to_categories.get(mood, ['inspiration'])
    quotes = []
    
    for category in categories:
        response = requests.get(f'https://api.quotable.io/quotes?tags={category}&limit=5')
        if response.status_code == 200:
            data = response.json()
            for quote in data['results']:
                quotes.append({
                    'text': quote['content'],
                    'author': quote['author']
                })
    
    return quotes

@app.route('/api/update-profile', methods=['POST'])
def update_profile():
    if 'user_email' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    data = request.json
    user = User.query.filter_by(email=session['user_email']).first()
    
    if 'username' in data:
        user.username = data['username']
    if 'bio' in data:
        user.bio = data['bio']
    if 'favorite_genres' in data:
        user.favorite_genres = json.dumps(data['favorite_genres'])
    
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/delete-account', methods=['POST'])
def delete_account():
    if 'user_email' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    user = User.query.filter_by(email=session['user_email']).first()
    db.session.delete(user)
    db.session.commit()
    session.clear()
    return jsonify({'success': True})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 