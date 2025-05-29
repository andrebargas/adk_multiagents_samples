"""
Copyright 2025 Google LLC. This software is provided as-is, without warranty
or representation for any use or purpose. Your use of it is subject to your
agreement with Google.

Converts a .env file to a YAML file.

This script reads key-value pairs from a .env file, skipping comments
and empty lines, and writes them into a YAML formatted file.

Usage:
  python env_to_yaml.py <path_to_env_file> <path_to_output_yaml_file>

Example:
  python env_to_yaml.py .env config.yaml
"""

import argparse
import yaml
import os

def parse_env_value(value_str):
    """
    Cleans and parses a value string from an .env file.
    Removes surrounding quotes (single or double) and strips whitespace.
    """
    stripped_value = value_str.strip()
    if (stripped_value.startswith('"') and stripped_value.endswith('"')) or \
       (stripped_value.startswith("'") and stripped_value.endswith("'")):
        return stripped_value[1:-1]
    return stripped_value

def env_to_dict(env_file_path):
    """
    Reads a .env file and returns its contents as a dictionary.
    Skips lines starting with '#' (comments) and empty lines.
    """
    if not os.path.exists(env_file_path):
        raise FileNotFoundError(f"Error: Input file '{env_file_path}' not found.")
    
    config_vars = {}
    with open(env_file_path, 'r', encoding='utf-8') as f:
        for line_number, line_content in enumerate(f, 1):
            line = line_content.strip()
            
            if not line or line.startswith('#'):
                continue
            
            if '=' not in line:
                print(f"Warning: Line {line_number} in '{env_file_path}' does not contain '='. Skipping.")
                continue
                
            key, value_str = line.split('=', 1)
            key = key.strip()
            
            # Ensure key is not empty after stripping
            if not key:
                print(f"Warning: Line {line_number} in '{env_file_path}' has an empty key. Skipping.")
                continue

            value = parse_env_value(value_str)
            config_vars[key] = value
            
    return config_vars

def dict_to_yaml(data_dict, yaml_file_path, input_filename):
    """
    Writes a dictionary to a YAML file.
    """
    try:
        output_dir = os.path.dirname(yaml_file_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            print(f"Created output directory: {output_dir}")

        with open(yaml_file_path, 'w', encoding='utf-8') as f:
            yaml.dump(data_dict, f, sort_keys=False, default_flow_style=False, allow_unicode=True)
        print(f"Successfully converted '{input_filename}' to '{yaml_file_path}'")
    except IOError as e:
        print(f"Error writing YAML file '{yaml_file_path}': {e}")
    except Exception as e:
        print(f"An unexpected error occurred while writing YAML file: {e}")

def main():
    """
    Main function to parse arguments and orchestrate the conversion.
    """
    parser = argparse.ArgumentParser(
        description="Convert .env file to YAML format.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="Example:\n  python env_to_yaml.py .env config.yaml"
    )
    parser.add_argument("env_file", help="Path to the input .env file.")
    parser.add_argument("yaml_file", help="Path to the output YAML file.")
    
    args = parser.parse_args()
    
    try:
        env_data = env_to_dict(args.env_file)
        if env_data:
            dict_to_yaml(env_data, args.yaml_file, os.path.basename(args.env_file))
        else:
            print(f"No data found or parsed from '{args.env_file}'. YAML file not created.")
    except FileNotFoundError as e:
        print(e)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()