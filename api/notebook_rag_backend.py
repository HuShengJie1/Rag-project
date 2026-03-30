from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import api_manager
import api_chat
import kimi_direct

app = FastAPI(title="NotebookLM-style RAG Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载两个模块
app.include_router(api_manager.router)
app.include_router(api_chat.router)
app.include_router(kimi_direct.router)

if __name__ == "__main__":
    import uvicorn
    # 4070 建议开启单 worker 保证显存不冲突
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=1)
