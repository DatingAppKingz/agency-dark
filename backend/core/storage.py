"""Storage service placeholder."""

class StorageService:
    """Placeholder storage service."""
    
    async def upload_file(self, file_path: str, file_content: bytes) -> str:
        """Upload file placeholder."""
        return f"uploaded://{file_path}"
    
    async def delete_file(self, file_path: str) -> bool:
        """Delete file placeholder."""
        return True
    
    async def get_file_url(self, file_path: str) -> str:
        """Get file URL placeholder."""
        return f"https://storage.example.com/{file_path}"

# Global instance
storage_service = StorageService()