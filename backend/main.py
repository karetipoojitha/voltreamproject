from config import load_dotenv
from app import create_app
from routes import include_routers
from rag import build_db
from database import init_db, get_dashboard

load_dotenv()

app = create_app()
include_routers(app)

@app.on_event("startup")
def startup():
    init_db()
    build_db()

@app.get("/")
def home():
    return {"message": "VoltStream Backend Running"}

@app.get("/dashboard")
def dashboard():
    return get_dashboard()
