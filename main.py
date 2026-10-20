from fastapi  import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()


posts: list[dict] = [
    {
        "id": 1,
        "author": "Corey Schafer",
        "title": "FastAPI is Awesome",
        "content": "This framework is really easy to use and super fast.",
        "date_posted": "Oct 20, 2026",
    },
    {
        "id": 2,
        "author": "Jane Doe",
        "title": "Python is Great for Web Development",
        "content": "Python is a great language for web development, and FastAPI makes it even better.",
        "date_posted": "Oct 20, 2026",
    },
    {
        "id": 3,
        "author": "Umfo",
        "title": "Python is Great for Web Development",
        "content": "this is a temp solution for database just to test api endpoint.",
        "date_posted": "Oct 20, 2026",
    },
]



@app.get("/", response_class=HTMLResponse)
def home():
  return f"<h1>{posts[2]['title']}</h1>"
  

@app.get("/posts")
def get_posts():
    return posts