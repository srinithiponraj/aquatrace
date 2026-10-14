from database.connection import init_db, get_database_status
from utils.logger import logger

if __name__ == "__main__":
    status = get_database_status()
    logger.info(f"Setting up database using {status['engine']} ({status['url_masked']})...")
    init_db()
    logger.info("Database schema initialized and sample lakes seeded successfully!")
