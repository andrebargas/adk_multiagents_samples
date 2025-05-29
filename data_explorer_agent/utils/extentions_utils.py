#  Copyright 2025 Google LLC. This software is provided as-is, without warranty
#  or representation for any use or purpose. Your use of it is subject to your
#  agreement with Google.

from vertexai.preview.extensions import Extension
import google.cloud.aiplatform as aiplatform
from google.api_core import exceptions as google_exceptions
from typing import Optional 
from data_explorer_agent.utils.utils import get_env_var

aiplatform.init(project=get_env_var("GOOGLE_CLOUD_PROJECT"), 
                location=get_env_var("GOOGLE_CLOUD_LOCATION"))


def list_extensions(filter: Optional[str] = None, order_by: Optional[str] = None,):
    try:
        all_extensions = Extension.list(filter=filter, order_by=order_by)
        if not all_extensions:
            print("No extensions found in this project and location.")
            return []  # Return an empty list if no extensions are found
        return all_extensions
    except google_exceptions.PermissionDenied as e:
        print(f"Permission denied when trying to list extensions. Please check IAM permissions. Error: {e}")
        return None
    except AttributeError as e:
        print(f"Vertex AI SDK may not be properly initialized. Error: {e}")
        return None
    except Exception as e:
        print(f"An error occurred while listing extensions: {e}")
        return None

def get_lastest_code_interpreter():

    code_interpreter_only_filter = 'display_name="Code Interpreter"'
    lastest_order_by = "create_time desc"

    extensions = list_extensions(filter=code_interpreter_only_filter, 
                                 order_by=lastest_order_by)
    return extensions[-1] if extensions else None
    

def get_or_create_code_interpreter():

    lastest_code_interpreter = get_lastest_code_interpreter()
    if lastest_code_interpreter:
        return lastest_code_interpreter.resource_name
    else:
        try:
            print('No CODE_INTERPRETER_ID found in the environment. Create a new one.')
            new_code_interpreter = Extension.from_hub('code_interpreter')
        except (google_exceptions.PermissionDenied, google_exceptions.ClientError) as e:
            print(f"Error when trying to get extension from hub. Please check IAM permissions or if the extension exists. Error: {e}")
            return None
        return new_code_interpreter.resource_name
    