"""ClaimLens root entrypoint for Hugging Face Spaces & local serving."""

from claimlens.app import create_app

demo = create_app()

if __name__ == "__main__":
    demo.launch()
