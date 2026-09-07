"""ClaimLens root entrypoint for Hugging Face Spaces & local serving."""

import uvicorn

from claimlens.api import app

# Export ASGI app object for uvicorn app:app
__all__ = ["app"]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
