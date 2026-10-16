from fastapi import FastAPI

from api.routes import artifacts, characters, enka, planner, queue, sessions

app = FastAPI(title="Genshin Planner")
app.include_router(characters.router, prefix="/api")
app.include_router(artifacts.router, prefix="/api")
app.include_router(planner.router, prefix="/api")
app.include_router(queue.router, prefix="/api")
app.include_router(enka.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
