"""Prefect worker entry point — placeholder for Phase 2+."""

import asyncio
import structlog

logger = structlog.get_logger()


async def main():
    """Worker main loop — will be populated with Prefect flows in Phase 2."""
    logger.info("Market Platform worker starting")
    logger.info("Worker is idle — scheduled jobs will be added in Phase 2")

    # Keep the worker alive
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
