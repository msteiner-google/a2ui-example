"""Utility to validate A2UI JSON files in the data folder."""

import json
import sys
from pathlib import Path

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.common_modifiers import remove_strict_validation
from a2ui.schema.manager import A2uiSchemaManager


def validate_data_folder():
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
        print(f"Error: Data directory '{data_dir}' not found.")
        sys.exit(1)

    json_files = list(data_dir.glob("*.json"))
    if not json_files:
        print(f"No JSON files found in '{data_dir}'.")
        return

    print(f"Validating {len(json_files)} files in '{data_dir}'...")
    print("-" * 40)

    all_passed = True
    for file_path in json_files:
        try:
            with file_path.open("r") as f:
                data = json.load(f)

            # Validate
            validator.validate(data)
            print(f"✅ {file_path.name}: Valid")

        except json.JSONDecodeError as e:
            print(f"❌ {file_path.name}: Invalid JSON - {e}")
            all_passed = False
        except ValueError as e:
            print(f"❌ {file_path.name}: Validation Failed")
            print(f"   Error: {e}")
            all_passed = False
        except Exception as e:
            print(f"❌ {file_path.name}: Unexpected Error - {e}")
            all_passed = False

    print("-" * 40)
    if all_passed:
        print("All files validated successfully! 🎉")
    else:
        print("Some files failed validation. Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    validate_data_folder()
