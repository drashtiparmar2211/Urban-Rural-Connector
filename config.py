import os

class Config:
    # This is fine as is for now
    SECRET_KEY = 'your_very_secret_key_here'
    
    # Email Settings
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False 
    
    # YOUR ACTUAL GMAIL DETAILS
    MAIL_USERNAME = 'YOUR_MAIL'
    MAIL_PASSWORD = 'YOUR_16-CHARACTER_PASSWORD' # Your 16-character App Password
    MAIL_DEFAULT_SENDER = 'YOUR_MAIL'
