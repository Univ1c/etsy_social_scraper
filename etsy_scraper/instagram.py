"""Instagram-related functionality with enhanced safety, scheduling, and analytics."""
import os
import random
import time
import json
import csv
import threading
from instagrapi.exceptions import ClientLoginRequired, ChallengeRequired, ClientThrottledError
from instagrapi import Client
import concurrent.futures
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict, Any, Set
from urllib.parse import urlparse
from pathlib import Path
import traceback

from config import (
    INSTAGRAM_ENABLED, 
    DRY_RUN, 
    BASE_DIR,
    INSTAGRAM_MAX_DAILY_FOLLOWS,
    INSTAGRAM_MAX_LIKES,
    INSTAGRAM_MIN_SESSION_GAP_HOURS
)
from feedback_system import FEEDBACK
from rate_limiter import INSTAGRAM_RATE_LIMITER
from screen_manager import SCREEN

# Constants
MIN_DELAY_BETWEEN_ACTIONS = 10  # Minimum seconds between actions
MAX_DELAY_BETWEEN_ACTIONS = 30  # Maximum seconds between actions
MAX_LIKES_PER_PROFILE = 2       # Conservative default
REQUEST_TIMEOUT = 45            # Seconds before API calls timeout

# Global locks
IG_ACTION_LOCK = threading.Lock()
IG_SESSION_LOCK = threading.Lock()

class InstagramManager:
    """Centralized Instagram operations with safety controls."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize the Instagram client and state tracking."""
        self.client = None
        self.last_session_start = None
        self.follow_count = 0
        self.like_count = 0
        self._setup_files()
        
        if INSTAGRAM_ENABLED:
            self._init_client()
    
    def _setup_files(self):
        """Ensure required data files exist."""
        self.session_file = BASE_DIR / "instagram_session.json"
        self.action_log_file = BASE_DIR / "instagram_actions.csv"
        self.followed_users_file = BASE_DIR / "followed_users.csv"
        
        # Create action log if missing
        if not self.action_log_file.exists():
            with open(self.action_log_file, 'w') as f:
                f.write("timestamp,action_type,username,success\n")
                
        # Create followed users file if missing
        if not self.followed_users_file.exists():
            with open(self.followed_users_file, 'w') as f:
                f.write("timestamp,username,followed_back,last_checked\n")
    
    def _init_client(self):
        """Initialize the Instagram client with safety controls."""
        try:
            from instagrapi import Client
            self.client = InstagramClient(
                session_file=self.session_file,
                action_log_file=self.action_log_file,
                followed_users_file=self.followed_users_file
            )
            
            if not self.client.ensure_session():
                raise RuntimeError("Failed to establish Instagram session")
                
        except Exception as e:
            SCREEN.print_content(f"Instagram initialization failed: {e}")
            traceback.print_exc()
            self.client = None

    def can_perform_actions(self) -> bool:
        """Check if we're allowed to perform actions based on timing."""
        if not self.last_session_start:
            return True
            
        hours_since_last = (datetime.now() - self.last_session_start).total_seconds() / 3600
        return hours_since_last >= INSTAGRAM_MIN_SESSION_GAP_HOURS
    
    def record_action(self, action_type: str, username: str, success: bool):
        """Log an action attempt."""
        with open(self.action_log_file, 'a') as f:
            f.write(f"{datetime.now().isoformat()},{action_type},{username},{success}\n")
    
    def get_recent_actions(self) -> List[Dict[str, str]]:
        """Get recently performed actions."""
        try:
            with open(self.action_log_file, 'r') as f:
                return list(csv.DictReader(f))
        except Exception:
            return []

class InstagramClient:
    """Thread-safe Instagram client with rate limiting and session management."""
    
    def __init__(self, session_file: Path, action_log_file: Path, followed_users_file: Path):
        self.cl = Client()
        self.session_file = session_file
        self.action_log_file = action_log_file
        self.followed_users_file = followed_users_file
        self._configure_client()
        self.action_counts = {'follow': 0, 'like': 0}
        self.last_action_time = None
        self._load_action_counts()
    
    def _configure_client(self):
        """Apply conservative client settings."""
        self.cl.delay_range = [5, 10]
        self.cl.request_timeout = REQUEST_TIMEOUT
        self.cl.max_retries = 1  # Fewer retries = less suspicious
        
        # Device simulation
        self.cl.set_device({
            'app_version': '242.0.0.0.0',
            'android_version': 13,
            'android_release': '13.0.0',
            'dpi': '480dpi',
            'resolution': '1080x1920',
            'manufacturer': 'Google',
            'device': 'Pixel 7',
            'model': 'Pixel 7',
            'cpu': 'arm64-v8a'
        })
        
        
    
    def _load_action_counts(self):
        """Load daily action counts from file."""
        try:
            if self.action_log_file.exists():
                with open(self.action_log_file, 'r') as f:
                    today = datetime.now().strftime('%Y-%m-%d')
                    reader = csv.DictReader(f)
                    self.action_counts = {
                        'follow': sum(1 for row in reader if row['action_type'] == 'follow' and row['timestamp'].startswith(today)),
                        'like': sum(1 for row in reader if row['action_type'] == 'like' and row['timestamp'].startswith(today))
                    }
        except Exception as e:
            SCREEN.print_content(f"Error loading action counts: {e}")
    
    def ensure_session(self) -> bool:
        """Ensure we have a valid session, with challenge handling."""
        with IG_SESSION_LOCK:
            if self.session_file.exists():
                try:
                    self.cl.load_settings(self.session_file)
                    # Validate session
                    self.cl.get_timeline_feed()
                    return True
                except (ClientLoginRequired, ChallengeRequired) as e:
                    SCREEN.print_content(f"Session expired: {type(e).__name__}")
                except Exception as e:
                    SCREEN.print_content(f"Session validation failed: {type(e).__name__}")
            
            return self._establish_new_session()
    
    def _establish_new_session(self) -> bool:
        """Perform fresh login with challenge handling."""
        username = os.getenv("INSTAGRAM_USERNAME")
        password = os.getenv("INSTAGRAM_PASSWORD")
        
        if not username or not password:
            SCREEN.print_content("Instagram credentials not configured")
            return False
        
        try:
            # Initial login attempt
            self.cl.login(username, password)
            self.cl.dump_settings(self.session_file)
            return True
        except ChallengeRequired:
            SCREEN.print_content("Challenge required - enter code from email/SMS")
            try:
                code = input("Verification code: ").strip()
                self.cl.challenge_resolve(username, password, code)
                self.cl.dump_settings(self.session_file)
                return True
            except Exception as e:
                SCREEN.print_content(f"Challenge failed: {type(e).__name__}")
                return False
        except Exception as e:
            SCREEN.print_content(f"Login failed: {type(e).__name__}")
            return False
    
    def safe_request(self, action_type: str, func, *args, **kwargs) -> Any:
        """
        Execute an Instagram API request with:
        - Rate limiting
        - Action counting
        - Error handling
        - Session recovery
        """
        # Check daily limits
        if action_type == 'follow' and self.action_counts['follow'] >= INSTAGRAM_MAX_DAILY_FOLLOWS:
            raise ClientThrottledError("Daily follow limit reached")
        elif action_type == 'like' and self.action_counts['like'] >= INSTAGRAM_MAX_LIKES:
            raise ClientThrottledError("Daily like limit reached")
        
        # Enforce delay between actions
        if self.last_action_time:
            elapsed = (datetime.now() - self.last_action_time).total_seconds()
            required_delay = random.uniform(MIN_DELAY_BETWEEN_ACTIONS, MAX_DELAY_BETWEEN_ACTIONS)
            if elapsed < required_delay:
                time.sleep(required_delay - elapsed)
        
        try:
            with IG_ACTION_LOCK:
                INSTAGRAM_RATE_LIMITER.wait()
                result = func(*args, **kwargs)
                self.action_counts[action_type] += 1
                self.last_action_time = datetime.now()
                return result
                
        except (ClientLoginRequired, ChallengeRequired):
            if self.ensure_session():
                return self.safe_request(action_type, func, *args, **kwargs)
            raise
        except ClientThrottledError:
            wait = random.randint(300, 600)  # 5-10 minute backoff
            SCREEN.print_content(f"Rate limited - waiting {wait//60} minutes")
            time.sleep(wait)
            return self.safe_request(action_type, func, *args, **kwargs)
        except Exception as e:
            SCREEN.print_content(f"API request failed: {type(e).__name__}")
            raise

# Initialize the manager
IG_MANAGER = InstagramManager()

def extract_etsy_username(url: str) -> Optional[str]:
    """Extract normalized Etsy shop username from URL."""
    try:
        parsed = urlparse(url)
        path = parsed.path.strip('/').lower()
        if path.startswith('shop/'):
            return path.split('/')[1]
        return None
    except Exception:
        return None

def generate_etsy_url_variants(etsy_url: str, username: str) -> Set[str]:
    """Generate all possible Etsy URL references for matching."""
    base_url = etsy_url.split('?')[0].rstrip('/')
    return {
        base_url,
        base_url.replace('https://', '').replace('http://', ''),
        f"etsy.com/shop/{username}",
        f"www.etsy.com/shop/{username}",
        f"/shop/{username}",
        username.lower()
    }

def analyze_instagram_profile(user_info: Dict[str, Any]) -> Tuple[str, str, str, int]:
    """
    Analyze Instagram profile with enhanced safety.
    Returns: (username, last_post_time, priority, followers)
    """
    username = user_info.get('username', '')
    followers = user_info.get('followers', 0)
    last_post = ''
    priority = 'LOW'
    
    if not username or not IG_MANAGER.client:
        return username, last_post, priority, followers
    
    try:
        user_id = IG_MANAGER.client.safe_request(
            'user_id',
            IG_MANAGER.client.cl.user_id_from_username,
            username
        )
        posts = IG_MANAGER.client.safe_request(
            'posts',
            IG_MANAGER.client.cl.user_medias,
            user_id,
            amount=1
        )
        
        if posts:
            post_time = posts[0].taken_at
            last_post = post_time.isoformat()
            hours_since = (datetime.now(post_time.tzinfo) - post_time).total_seconds() / 3600
            
            if hours_since < 24:
                priority = 'HIGH'
            elif hours_since < 72:
                priority = 'MEDIUM'
                
    except Exception as e:
        SCREEN.print_content(f"Profile analysis failed for @{username}: {type(e).__name__}")
    
    return username, last_post, priority, followers

def engage_with_profile(username: str) -> bool:
    """Follow and like posts with comprehensive safety checks."""
    if DRY_RUN:
        SCREEN.print_content(f"DRY RUN: Would engage with @{username}")
        return True
    
    if not IG_MANAGER.can_perform_actions():
        SCREEN.print_content("Insufficient time between sessions - skipping")
        return False
    
    try:
        # Follow
        user_id = IG_MANAGER.client.safe_request(
            'follow',
            IG_MANAGER.client.cl.user_id_from_username,
            username
        )
        IG_MANAGER.client.safe_request(
            'follow',
            IG_MANAGER.client.cl.user_follow,
            user_id
        )
        IG_MANAGER.record_action('follow', username, True)
        
        # Like posts (conservative)
        like_count = min(MAX_LIKES_PER_PROFILE, random.randint(1, 2))
        posts = IG_MANAGER.client.safe_request(
            'posts',
            IG_MANAGER.client.cl.user_medias,
            user_id,
            amount=like_count
        )
        
        for post in posts:
            try:
                IG_MANAGER.client.safe_request(
                    'like',
                    IG_MANAGER.client.cl.media_like,
                    post.id
                )
                IG_MANAGER.record_action('like', username, True)
                time.sleep(random.uniform(8, 15))  # Conservative spacing
            except Exception as e:
                IG_MANAGER.record_action('like', username, False)
        
        return True
        
    except Exception as e:
        IG_MANAGER.record_action('follow', username, False)
        SCREEN.print_content(f"Engagement failed with @{username}: {type(e).__name__}")
        return False

def process_etsy_shop(etsy_url: str) -> Tuple[str, str, str, int]:
    """
    Main workflow:
    1. Find matching Instagram profiles
    2. Analyze and engage with relevant ones
    3. Return engagement results
    """
    if not INSTAGRAM_ENABLED or not IG_MANAGER.client:
        return '', '', 'LOW', 0
    
    # Extract Etsy username and generate URL variants
    etsy_username = extract_etsy_username(etsy_url)
    if not etsy_username:
        SCREEN.print_content(f"Invalid Etsy URL: {etsy_url}")
        return '', '', 'LOW', 0
    
    url_variants = generate_etsy_url_variants(etsy_url, etsy_username)
    
    # Search for matching Instagram profiles
    try:
        candidates = IG_MANAGER.client.safe_request(
            'search',
            IG_MANAGER.client.cl.search_users,
            etsy_username
        )[:15]  # Limit candidates
        
        if not candidates:
            SCREEN.print_content("No matching profiles found")
            return '', '', 'LOW', 0
            
        # Process candidates with thread pool (limited concurrency)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = {}
            for user in candidates:
                if user.is_private:
                    continue  # Skip private accounts
                    
                futures[executor.submit(
                    _process_candidate,
                    user.username,
                    url_variants
                )] = user.username
            
            # Wait for first successful match or timeout
            done, _ = concurrent.futures.wait(
                futures,
                timeout=120,
                return_when=concurrent.futures.FIRST_COMPLETED
            )
            
            for future in done:
                result = future.result()
                if result:
                    executor.shutdown(cancel_futures=True)
                    return result
                    
        SCREEN.print_content("No qualifying profiles found")
        return '', '', 'LOW', 0
        
    except Exception as e:
        SCREEN.print_content(f"Shop processing failed: {type(e).__name__}")
        traceback.print_exc()
        return '', '', 'LOW', 0

def _process_candidate(username: str, etsy_urls: Set[str]) -> Optional[Tuple[str, str, str, int]]:
    """Process a single candidate profile (thread-safe)."""
    try:
        # Get full profile info
        profile = IG_MANAGER.client.safe_request(
            'profile',
            IG_MANAGER.client.cl.user_info_by_username,
            username
        )
        
        # Check for Etsy links
        bio = (profile.biography or '').lower()
        external = (profile.external_url or '').lower()
        has_link = any(url in text for url in etsy_urls for text in [bio, external])
        
        if has_link:
            analysis = analyze_instagram_profile({
                'username': profile.username,
                'followers': profile.follower_count
            })
            
            # Only engage with HIGH/MEDIUM priority
            if analysis[2] in ['HIGH', 'MEDIUM']:
                if engage_with_profile(profile.username):
                    if analysis[2] == 'HIGH':
                        FEEDBACK.detect_problem(
                            f"Engaged HIGH-priority: @{profile.username} "
                            f"(Followers: {profile.follower_count})"
                        )
                    return analysis
                    
    except Exception as e:
        SCREEN.print_content(f"Candidate processing failed: {type(e).__name__}")
    
    return None
