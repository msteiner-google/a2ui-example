"""Utility to validate A2UI JSON files in the data folder."""

import json
import sys
from pathlib import Path

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.common_modifiers import remove_strict_validation
from a2ui.schema.manager import A2uiSchemaManager
from loguru import logger


def validate_data_folder() -> None:
    """Validates all JSON files in the data directory."""
    # 1. Initialize Schema Manager (consistent with agent.py)
    schema_manager = A2uiSchemaManager(
        version="0.8",
        catalogs=[BasicCatalog.get_config(version="0.8")],
        schema_modifiers=[remove_strict_validation],
    )

    # 2. Get the validator
    catalog = schema_manager.get_selected_catalog()
    validator = catalog.validator

    data_dir = Path("data")
    if not data_dir.exists():
        logger.error(f"Error: Data directory '{data_dir}' not found.")
        sys.exit(1)

    json_files = list(data_dir.glob("*.json"))
    if not json_files:
        logger.info(f"No JSON files found in '{data_dir}'.")
        return

    logger.info(f"Validating {len(json_files)} files in '{data_dir}'...")
    logger.info("-" * 40)

    all_passed = True
    for file_path in json_files:
        try:
            with file_path.open("r") as f:
                data = json.load(f)

            # Validate
            validator.validate(data)
            logger.info(f"✅ {file_path.name}: Valid")

        except json.JSONDecodeError as e:
            logger.error(f"❌ {file_path.name}: Invalid JSON - {e}")
            all_passed = False
        except ValueError as e:
            logger.error(f"❌ {file_path.name}: Validation Failed")
            logger.error(f"   Error: {e}")
            all_passed = False
        except Exception:  # noqa: BLE001
            logger.exception(f"❌ {file_path.name}: Unexpected Error")
            all_passed = False

    logger.info("-" * 40)
    if all_passed:
        logger.info("All files validated successfully! 🎉")
    else:
        logger.error("Some files failed validation. Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    validate_data_folder()
