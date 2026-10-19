from fastapi import FastAPI

app = FastAPI(title="slot-flow")


@app.get("/health")
def health():
    return {"status": "ok"}
