#  Copyright 2025 Google LLC. This software is provided as-is, without warranty
#  or representation for any use or purpose. Your use of it is subject to your
#  agreement with Google.


import argparse
import google.auth
import os
import logging
from dotenv import dotenv_values
from data_explorer_agent.utils.exceptions import EnvFileNotFoundError, EnvFileFormatError, GoogleProjectNotSetError


def load_env_vars(env_file_path: str) -> dict:
    """
    Loads environment variables from a specified .env file.

    Args:
        env_file_path: The path to the .env file.

    Returns:
        A dictionary containing the loaded environment variables.
        Returns an empty dictionary if the file is not found (and it's the default .env)
        or if the file is empty or malformed.

    Raises:
        EnvFileNotFoundError: If a specifically provided env_file_path is not found.
        EnvFileFormatError: If there's an issue parsing the .env file.
        IOError: For other file reading issues.
    """
    env_vars = {}
    if not os.path.exists(env_file_path):
        if env_file_path != ".env":  # Only raise if a specific, non-default file was given and not found
            print(f"Error: Specified environment variables file not found: {env_file_path}.")
            raise EnvFileNotFoundError(f"Specified environment variables file not found: {env_file_path}")
        else:
            print("Info: Default environment variables file '.env' not found. No environment variables loaded from file.")
            raise EnvFileNotFoundError(f"Specified environment variables file not found: {env_file_path}")
    try:
        loaded_vars = dotenv_values(dotenv_path=env_file_path)
        if loaded_vars is None: # dotenv_values can return None if file is malformed or unreadable by it
            logging.error(f"Warning: Could not parse environment variables from file: {env_file_path}. The file might be empty or malformed.")
            raise EnvFileFormatError(f"Could not parse environment variables from file: {env_file_path}")
        elif not loaded_vars:
            print(f"Info: Environment variables file '{env_file_path}' is empty.")
        else:
            env_vars = loaded_vars
            print(f"Successfully loaded environment variables from {env_file_path}")

    except IOError as e:
        print(f"IOError: Could not read environment variables file: {env_file_path}. Error: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error loading environment variables from {env_file_path}: {e}")
        raise EnvFileFormatError(f"Unexpected error processing environment variables file: {env_file_path}. Details: {e}")
    
    return env_vars

def parse_args():

    parser = argparse.ArgumentParser(description="Deploy agent engine app to Vertex AI")
    parser.add_argument(
        "--project",
        default=None,
        help="GCP project ID (defaults to application default credentials)",
    )
    parser.add_argument(
        "--location",
        default="us-central1",
        help="GCP region (defaults to us-central1)",
    )
    parser.add_argument(
        "--agent-name",
        default="data-explorer-agent",
        help="Name for the agent engine",
    )
    parser.add_argument(
        "--requirements-file",
        default=".requirements.txt",
        help="Path to requirements.txt file",
    )
    parser.add_argument(
        "--extra-packages",
        nargs="+",
        default=["./app"],
        help="Additional packages to include",
    )
    parser.add_argument(
        "--env-vars-file",
        default=".env",
        help="Path to environment variables file in KEY=VALUE format (defaults to .env)",
    )
    parser.add_argument(
        "--set-env-vars",
        help="Comma-separated list of environment variables in KEY=VALUE format",
    )
    args = parser.parse_args()
    args = parser.parse_args()

    file_env_vars = load_env_vars(args.env_vars_file)

    cli_env_vars = {}
    if args.set_env_vars:
        try:
            for pair in args.set_env_vars.split(","):
                if "=" not in pair:
                    logging.warning(f"Skipping malformed env var from command line: {pair}")
                    continue
                key, value = pair.split("=", 1)
                cli_env_vars[key] = value
        except Exception as e:
            logging.error(f"Error parsing --set-env-vars: {e}")

    # CLI takes precedence over file
    final_env_vars = {**file_env_vars, **cli_env_vars}

    if not args.project:
        try:
            _, args.project = google.auth.default()
            if not args.project:
                print("GCP project ID could not be determined from application default credentials.")
                raise GoogleProjectNotSetError
        except google.auth.exceptions.DefaultCredentialsError as e:
            print(f"Could not get default GCP credentials. Please specify --project or configure ADC. Error: {e}")
            raise

    return args, final_env_vars