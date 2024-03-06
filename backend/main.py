import uvicorn
import os

if __name__ == '__main__':
    branch = os.getenv("BRANCH_ENV", "local")
    print(f"Current branch: {branch}")

    uvicorn.run(
        app='app.app:app',
        host='0.0.0.0',
        port=8000,
        reload=True
    )
