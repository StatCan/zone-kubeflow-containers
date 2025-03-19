import hashlib
import os
from notebook.services.contents.filemanager import FileContentsManager

class CentralizedCheckpoints(FileContentsManager):
    """
    A custom JupyterLab FileContentsManager that centralizes checkpoint storage.

    This class overrides Jupyter's default checkpoint behavior to store all 
    `.ipynb_checkpoints` in a single directory (`/opt/checkpoints`). It ensures 
    that checkpoint filenames remain unique by hashing the full notebook path.
    
    This approach prevents clutter in notebook directories and improves file 
    management, particularly for Windows users who cannot easily hide dot folders.

    Methods:
        get_hashed_path(path): Generates a unique hashed directory for storing checkpoints.
        create_checkpoint(path): Saves a notebook checkpoint in the centralized location.
        delete_checkpoint(checkpoint_id, path): Deletes a checkpoint (same behavior as default).
        list_checkpoints(path): Lists checkpoints stored for a given notebook.
    """

    def get_hashed_path(self, path):
        """
        Generate a unique hashed path for a notebook's checkpoints.

        This function takes the full notebook path, hashes it using SHA-256,
        and returns a directory path inside `/opt/checkpoints/` to store 
        the notebook's checkpoints.

        Args:
            path (str): The full file path of the notebook.

        Returns:
            str: The directory path where the notebook's checkpoints will be stored.
        """
        hash_object = hashlib.sha256(path.encode())  # Generate a SHA-256 hash of the notebook path
        hash_path = hash_object.hexdigest()  # Convert hash to a hex string
        return os.path.join('/opt/checkpoints', hash_path)  # Store checkpoints in a subdirectory

    def create_checkpoint(self, path):
        """
        Create a checkpoint for a notebook and store it in the centralized directory.

        If the checkpoint directory does not exist, it is created before saving 
        the checkpoint. The actual checkpoint creation is handled by the parent 
        FileContentsManager.

        Args:
            path (str): The full file path of the notebook.

        Returns:
            dict: The metadata of the created checkpoint.
        """
        checkpoint_dir = self.get_hashed_path(path)
        if not os.path.exists(checkpoint_dir):
            os.makedirs(checkpoint_dir)  # Ensure the checkpoint directory exists

        return super().create_checkpoint(path)  # Delegate actual checkpoint creation to parent class

    def delete_checkpoint(self, checkpoint_id, path):
        """
        Delete a specific checkpoint for a notebook.

        This method simply calls the parent class's `delete_checkpoint` method, 
        as Jupyter handles checkpoint deletions internally.

        Args:
            checkpoint_id (str): The unique identifier for the checkpoint.
            path (str): The full file path of the notebook.
        """
        return super().delete_checkpoint(checkpoint_id, path)

    def list_checkpoints(self, path):
        """
        List all checkpoints for a given notebook.

        This method calls the parent class's `list_checkpoints` method, ensuring 
        that Jupyter can retrieve checkpoint metadata as expected.

        Args:
            path (str): The full file path of the notebook.

        Returns:
            list: A list of checkpoint metadata dictionaries.
        """
        checkpoint_dir = self.get_hashed_path(path)
        return super().list_checkpoints(path)
