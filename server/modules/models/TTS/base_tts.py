from abc import ABC, abstractmethod

class BaseTTS(ABC):
    @abstractmethod
    async def stream(self, text: str):
        """Generator that yields audio chunks for the given text."""
        pass

    @abstractmethod
    async def close(self):
        """Close any resources if necessary."""
        pass
