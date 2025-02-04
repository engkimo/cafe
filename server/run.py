import logging
import os
import sys
import uvicorn

# ロギングの設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def main():
    try:
        logger.info("Starting server...")
        logger.debug(f"PYTHONPATH: {os.getenv('PYTHONPATH')}")
        logger.debug(f"Current directory: {os.getcwd()}")
        
        # Uvicornの設定
        config = uvicorn.Config(
            "server.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="debug",
            access_log=True
        )
        
        server = uvicorn.Server(config)
        server.run()
    except Exception as e:
        logger.error(f"Failed to start server: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()