#    ╔════════════════════════════════════════════════════════════════════╗
#    ║                                                                    ║
#    ║    News Reader Application                                         ║
#    ║                                                                    ║
#    ║    It all starts here!                                             ║
#    ║                                                                    ║
#    ║    Built with Flask, Jinja2, and Bootstrap 5.  Just the bare       ║
#    ║    minimum.                                                        ║
#    ║                                                                    ║
#    ╚════════════════════════════════════════════════════════════════════╝
from flask import Flask, render_template, request, redirect, jsonify
import socket
import os
import cnnlite
from tags import Tags
from threading import Thread
from datamodel import DataModel
import utilities

app = Flask(__name__)


#    ┌──────────────────────────────────────────────────────────┐
#    │                   Pages in Application                   │
#    └──────────────────────────────────────────────────────────┘

llama_message = "Just a moment while our trained Llamas read the headlines for you."

@app.route('/')
def index():
    global llama_message
    return render_template('startup.html', message=llama_message, links=False)


@app.route('/home')
def home():
    global llama_message
    cnn = cnnlite.CNNLite()
    # If we're going to fetch and tag more articles, back to the llama page
    if cnn.time_for_refresh():
        llama_message = "Our llamas are looking for news updates, just a moment"
        return redirect('/')

    stories = cnn.get_top_stories()
    return render_template('home.html', stories=stories, links=True)


@app.route('/help')
def help_page():
    return render_template('help.html', links=True)


@app.route('/open')
def open_story():
    cnn = cnnlite.CNNLite()

    story_id = request.args.get('id')
    cnn.mark_article_read(story_id)

    like_dislike(story_id, 1)

    url = cnn.get_article_url(story_id)

    print(f'Opening story {story_id} at {url}')

    # Redirect to the actual story URL
    return redirect(url)

#    ┌──────────────────────────────────────────────────────────┐
#    │               API Endpoints in Application               │
#    └──────────────────────────────────────────────────────────┘


#   This kicks off an initial fetch or refresh
@app.route('/api/start', methods=['POST'])
def start_task():
    print('Starting fetch', flush=True)

    global status
    status = {"status": "started", "message": "The Llamas are working hard to fetch the articles. Please wait..."}
    thread = Thread(target=first_fetch)
    thread.start()
    return jsonify(status)


#   Used to retrieve status of asynchronous processes
@app.route('/api/status', methods=['GET', 'POST'])
def get_status():
    return jsonify(status)


#   User likes a story
@app.route('/api/like')
def like_story():
    story_id = request.args.get('id')
    like_dislike(story_id, 1)
    return jsonify({"status": "success", "story_id": story_id})


#   User dislikes a story
@app.route('/api/dislike')
def dislike_story():
    story_id = request.args.get('id')
    like_dislike(story_id, -1)
    return jsonify({"status": "success", "story_id": story_id})


#    ┌──────────────────────────────────────────────────────────┐
#    │          Supporting Functions for Pages & APIs           │
#    └──────────────────────────────────────────────────────────┘

#   Update tags based on the user liking/disliking a story
def like_dislike(story_id, increment):
    tags = get_article_tags(story_id)
    tag_hist = Tags()
    if increment == 1:
        tag_hist.like_tags(tags)
        print(f'Liked story {story_id} with tags {tags}')
    else:
        tag_hist.dislike_tags(tags)
        print(f'Disliked story {story_id} with tags {tags}')


#   Get the tags for a story
def get_article_tags(article_id):
    db = DataModel()
    story = db.get_story_by_id(article_id)
    if story is not None:
        return story['tags']
    return []


#   This keeps track of the current application status
status = {
    "status": "idle",
    "message": ""
}


#   A callback function for others who wish to update the status
def status_callback(state, message):
    global status
    status["status"] = state
    status["message"] = message


#   Fetch new articles.  It is in a separate function so that we can run this in a thread
#   without locking up the browser waiting for some that may be very time-consuming
def first_fetch():
    global status
    u = utilities.Utilities()
    u.set_callback(status_callback)
    try:
        status["status"] = "working"
        status["message"] = "Starting to fetch articles"
        cnn = cnnlite.CNNLite()
        cnn.refresh_list()

        status["status"] = "done"
        status["message"] = "Task completed successfully"
    except Exception as e:
        status["status"] = "error"
        status["message"] = str(e)
        raise


#    ┌──────────────────────────────────────────────────────────┐
#    │                       Startup Code                       │
#    └──────────────────────────────────────────────────────────┘

#    ┌──────────────────────────────────────────────────────────┐
#    │                                                          │
#    │    On the Mac, port 5000, which is the default port,     │
#    │    is often busy.  So the first thing I need to do is    │
#    │    find a free port and use it instead.                  │
#    │                                                          │
#    └──────────────────────────────────────────────────────────┘

def find_free_port():
    # This is just some sort of magic incantation that works
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))  # Bind to an available port provided by the host.
        return s.getsockname()[1]  # Return the port number assigned.


#    ┌──────────────────────────────────────────────────────────┐
#    │                                                          │
#    │    This version of the Flask launch code will            │
#    │    automatically open a browser, saving you from         │
#    │    having to click.                                      │
#    └──────────────────────────────────────────────────────────┘
if __name__ == '__main__':
    port = find_free_port()
    if os.name == 'nt':
        os.system(f'explorer "http:/127.0.0.1:{port}"')
    else:
        os.system(f'open http://127.0.0.1:{port}')
    app.run(port=port, debug=False)
