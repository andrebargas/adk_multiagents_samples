#  Copyright 2025 Google LLC. This software is provided as-is, without warranty
#  or representation for any use or purpose. Your use of it is subject to your
#  agreement with Google.
import os


def get_env_var(var_name:str, default:str=None) -> str:
  """Retrieves the value of an environment variable.

  Args:
    var_name: The name of the environment variable.

  Returns:
    The value of the environment variable, or throws a ValueError if it is not
    set.

  Raises:
    ValueError: If the environment variable is not set.
  """
  try:
    value = os.environ[var_name]
    # Strip leading/trailing single and double quotes
    return value.strip('\'"')
  except KeyError:
    if default is not None:
      # Also strip quotes from the default value if it's a string
      if isinstance(default, str):
        return default.strip('\'"')
      return default
    raise ValueError(f'Missing environment variable: {var_name}')


def get_image_bytes(filepath):
  """Reads an image file and returns its bytes.

  Args:
    filepath: The path to the image file.

  Returns:
    The bytes of the image file, or None if the file does not exist or cannot be
    read.
  """
  try:
    with open(filepath, 'rb') as f:  # "rb" mode for reading in binary
      image_bytes = f.read()
    return image_bytes
  except FileNotFoundError:
    print(f'Error: File not found at {filepath}')
    return None
  except Exception as e:
    print(f'Error reading file: {e}')
    return None
  

def check_runtime_environment():
  # Cloud Run specific check
  if "K_SERVICE" in os.environ:
      return True
  # General Docker container check
  if os.path.exists('/.dockerenv'):
      return True
  # General Linux container (cgroup) check
  try:
      with open('/proc/self/cgroup', 'rt') as f:
          for line in f:
              if 'docker' in line or 'kubepods' in line or 'containerd' in line:
                  return True, "Linux container (cgroup info found)"
  except FileNotFoundError:
      pass 
  return False


def get_db_connection_string():
   
  connection_name = f"{get_env_var("DB_PROJECT_ID")}:{get_env_var("DB_REGION")}:{get_env_var("DB_INSTANCE_NAME")}"
  db_user = get_env_var("DB_USER")
  db_pass = get_env_var("DB_PASSWORD")
  db_name = get_env_var("DB_SESSIONS_NAME")

  if check_runtime_environment():
    return f"postgresql+psycopg2://{db_user}:{db_pass}@/{db_name}?host=/cloudsql/{connection_name}"
  else:
    return f"postgresql+psycopg2://{db_user}:{db_pass}@127.0.0.1:5433/{db_name}"