from fastapi import FastAPI, Query
from checker import check_tee_times
import uvicorn

app = FastAPI()

@app.get("/check")
def check(
    date: str = Query(..., description="Format: MM/DD/YYYY"),
    start: str = Query(..., description="Format: HH:MM AM/PM"),
    end: str = Query(..., description="Format: HH:MM AM/PM")
):
    try:
        results = check_tee_times(date, start, end)
        return {"results": results}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
