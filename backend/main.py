import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine
from app.scheduler import start_scheduler, shutdown_scheduler
from app.routers.stocks import router as stocks_router
from app.cache import populate_indian_market_cache

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup lifecycle
    # Create DB tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # Start APScheduler
    start_scheduler()
    
    # Trigger background cache builder
    asyncio.create_task(populate_indian_market_cache())
    
    yield
    
    # Shutdown lifecycle
    shutdown_scheduler()

app = FastAPI(
    title="AI-Driven Stock Intelligence Platform API", 
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for local frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(stocks_router, prefix="/api")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
