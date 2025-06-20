#!/data/data/com.termux/files/usr/bin/bash
echo "Setting up Etsy Social Scraper in Termux..."

# Grant storage permissions
termux-setup-storage
sleep 2

# Update package lists and install dependencies
pkg update -y && pkg upgrade -y
pkg install python git -y

# Install Python dependencies
pip install --upgrade pip
pip install requests beautifulsoup4 instagrapi fake-useragent python-dotenv tqdm tenacity

# Create project directory
PROJECT_DIR="/storage/emulated/0/etsy_social_ig_v01"
mkdir -p "$PROJECT_DIR/user_files"
cd "$PROJECT_DIR" || exit 1

# Clone or update repository (assumed public repo)
REPO_URL="https://github.com/yourusername/etsy-social-scraper.git"
if [ -d ".git" ]; then
    echo "Updating existing repository..."
    git pull
else
    echo "Cloning repository..."
    git clone "$REPO_URL" .
fi

# Create .env file if not exists
ENV_FILE="$PROJECT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    cp .env.example "$ENV_FILE"
    echo "Created .env file. Please edit $ENV_FILE with your credentials."
else
    echo ".env file already exists."
fi

# Ensure user_files is writable
chmod -R 777 "$PROJECT_DIR/user_files"

echo "Setup complete! Edit $ENV_FILE and run 'python main.py' to start."
