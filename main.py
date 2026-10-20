from fastapi  import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates") #template objects to look for this in the templates folder



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



@app.get("/", include_in_schema=False, name="home")
@app.get("/posts", include_in_schema=False, name="posts")

def home(request: Request):
  return templates.TemplateResponse(request, "home.html", 
  {"posts": posts, "title": "Home"})

@app.get("/api/posts")
def get_posts():
    return posts