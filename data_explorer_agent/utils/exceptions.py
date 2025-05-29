#  Copyright 2025 Google LLC. This software is provided as-is, without warranty
#  or representation for any use or purpose. Your use of it is subject to your
#  agreement with Google.


class EnvFileNotFoundError(Exception):
    """Custom exception for when a specified .env file is not found."""
    def __init__(self, message="Specified environment variables file not found"):
        self.message = message
        super().__init__(self.message)


class EnvFileFormatError(Exception):
    """Custom exception for errors in .env file format."""
    def __init__(self, message="Malformed line in environment variables file. Expected KEY=VALUE format."):
        self.message = message
        super().__init__(self.message)

class GoogleProjectNotSetError(Exception):
    """Custom exception for when the Google Cloud Project ID is not set."""
    def __init__(self, message="Google Cloud Project ID is not set. Please specify --project or configure Application Default Credentials."):
        self.message = message
        super().__init__(self.message)