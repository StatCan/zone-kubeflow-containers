import hashlib
import os
from notebook.services.contents.filemanager import FileContentsManager

class CentralizedCheckpoints(FileContentsManager):
    def get_hashed_path(self, path):
        # Create a unique hash based on the full path
        hash_object = hashlib.sha256(path.encode())
        hash_path = hash_object.hexdigest()
        # Store checkpoints in subdirectories based on the hash
        return os.path.join('/opt/checkpoints', hash_path)

    def create_checkpoint(self, path):
        checkpoint_dir = self.get_hashed_path(path)
        if not os.path.exists(checkpoint_dir):
            os.makedirs(checkpoint_dir)

        # Save checkpoint in the hashed directory
        return super().create_checkpoint(path)

    def delete_checkpoint(self, checkpoint_id, path):
        return super().delete_checkpoint(checkpoint_id, path)

    def list_checkpoints(self, path):
        checkpoint_dir = self.get_hashed_path(path)
        return super().list_checkpoints(path)
