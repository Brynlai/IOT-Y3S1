# FILE: /home/pi/image_server.py
from flask import Flask, send_from_directory
import os

IMAGE_DIR = os.path.join(os.path.expanduser('~'), 'captures')
app = Flask(__name__)

@app.route('/captures/<path:filename>')
def serve_image(filename):
    return send_from_directory(IMAGE_DIR, filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False)
