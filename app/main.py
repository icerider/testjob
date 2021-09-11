from fastapi import FastAPI

app = FastAPI()

router = APIRouter()



app.include_router(router)
