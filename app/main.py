from fastapi import FastAPI

# Import the model before create_all so SQLAlchemy knows which table to create.
from app import models
from app.database import Base, engine
from app.routers import tasks

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Builders' Tribe Task API",
    description="Simple task management REST API for the Engineering Intern case study.",
    version="0.1.0",
)


@app.get("/", summary="Health check")
def read_root():
    return {"status": "ok"}


app.include_router(tasks.router)
